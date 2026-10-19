#!/usr/bin/env python3
"""Author's post-freeze probes on v0.8.8 (not scored). Run once, after the scored run.
v0.8.8 is the final revision before publication, so there is no further review round to seal these
for: the findings are published openly in AUTHOR_FINDINGS_v0_8_8.md.
Each probe tests a claim in its docstring.
Run from hs088/: python3 -I author_probe_v0_8_8.py"""
import importlib.util, json, os, signal, subprocess, sys, tempfile, threading, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
CAND = HERE / "humble_seed_v0_8_8_candidate.py"
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m
K = load(CAND, "ap_candidate")
H = load(HERE / "falsify_v0_8_8.py", "ap_harness")
PREF, CASUAL = H.PREF, H.CASUAL
def outcome(fn):
    try: return f"returned {fn()!r}"[:260]
    except BaseException as e: return f"{type(e).__name__}: {e}"[:260]
def wseq(d, s): return K.OwnerWitness(d / "witness.json").ledger[s.organism_id]["sequence"]
def pending(d, s): return K.OwnerWitness(d / "witness.json").pending_for(s.organism_id) is not None
def disk(s): return json.loads(s._state_path().read_text())

WORKER = r'''
import importlib.util, json, sys, time
from pathlib import Path
spec = importlib.util.spec_from_file_location("w", sys.argv[1]); K = importlib.util.module_from_spec(spec)
sys.modules["w"] = K; spec.loader.exec_module(K)
data_dir, n, role = Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
done = stale = 0
if role == "dweller":
    o = K.HumbleSeed(data_dir); o.load()
    while done < n:
        try:
            r = o.dwell_or_propose("formality", "evt", "hmm ok"); assert r["status"] == "dwelling"; done += 1
        except K.StaleOrganism:
            stale += 1; o = K.HumbleSeed(data_dir); o.load()
else:
    pem = Path(sys.argv[5]).read_text()
    owner = K.OwnerTool(pem, K.OwnerWitness(data_dir.parent / "witness.json"))
    while done < n:
        s = K.HumbleSeed(data_dir); s.load()
        try:
            assert owner.attest(s) is True; done += 1
        except K.StaleOrganism:
            stale += 1
        time.sleep(0.01)
print(json.dumps({"role": role, "done": done, "stale_retries": stale}))
'''


def _signal_in_save(s, handler_body, catch):
    """Deliver a real SIGUSR1 from inside the outer save's write call (between its generation check and its
    write); the handler runs handler_body() in the same thread."""
    seen = {}
    def handler(signum, frame):
        try:
            seen["handler"] = outcome(handler_body)
            if not catch and seen["handler"].startswith("ReentryRefused"):
                raise K.ReentryRefused("re-raised by the handler")
        finally:
            seen["ran"] = True
    old = signal.signal(signal.SIGUSR1, handler)
    real = K._durable_write
    def write(path, text):
        if Path(path) == s._state_path() and "fired" not in seen:
            seen["fired"] = True
            os.kill(os.getpid(), signal.SIGUSR1)       # delivered at the next bytecode boundary, in this thread
            time.sleep(0.01)
        return real(path, text)
    K._durable_write = write
    return seen, lambda: (setattr(K, "_durable_write", real), signal.signal(signal.SIGUSR1, old))


def P1_real_signal_reentry(d):
    """E2 with a real signal (ChatGPT round 8 used SIGUSR1). The handler runs another object's dwell during the
    outer save. (a) The handler catches the refusal: the outer dwell completes and nothing is lost. (b) The
    handler lets it propagate: the outer save is interrupted before its write, as any exception would be (R31),
    and nothing saved is lost."""
    out = {}
    for case, catch in (("handler_catches", True), ("handler_propagates", False)):
        sub = d / case; sub.mkdir()
        s, o = H.born(K, sub)
        other = H.expect_loads(K, s.data_dir)
        g0 = disk(s)["generation"]
        seen, undo = _signal_in_save(s, lambda: other.dwell_or_propose("curiosity", "evt", "hmm ok")["status"], catch)
        try:
            outer = outcome(lambda: s.dwell_or_propose("formality", "evt", "hmm ok")["status"])
        finally:
            undo()
        st = disk(s)
        out[case] = {"outer": outer, "handler": seen.get("handler"), "generation_delta": st["generation"] - g0,
                     "saved_dwellings": [e.get("category") for e in st["trace"] if e.get("event") == "dwelling"],
                     "outer_object_next_dwell": outcome(lambda: s.dwell_or_propose("formality", "evt", "hmm ok")["status"]),
                     "fresh_audit": outcome(lambda: o.audit(H.expect_loads(K, s.data_dir)))}
    return out


def P2_prefix_route_refuses_what_it_should(d):
    """R37: the prefix route completes a pending commit only for a checkpoint this owner signed whose prefix
    replays exactly. Set up F1's state (failed commit, then a crossing), then rewrite one dwelling inside the
    attested prefix (rechained, resealed). Restore must refuse and leave the intent pending; the file is
    untouched."""
    s, o = H.born(K, d)
    H.dwell(s, "curiosity", "hmm ok")
    H.apply_ok(K, s, o, H.propose(s, "verbosity"), attest=False)
    real = o.witness.commit
    o.witness.commit = lambda cp: (_ for _ in ()).throw(OSError("injected"))
    first = outcome(lambda: o.attest(s))
    o.witness.commit = real
    H.apply_ok(K, s, o, H.propose(s, "formality", CASUAL), attest=False)
    def rewrite(st):
        for e in st["trace"]:
            if e.get("event") == "dwelling":
                e["reason"] = "rewritten inside the attested prefix"; break
    K._reseal_attack(s, rewrite, rechain=True)
    before = s._state_path().read_bytes()
    r = outcome(lambda: o.restore(K.HumbleSeed(s.data_dir)))
    return {"setup_attest": first, "restore": r, "file_unchanged": s._state_path().read_bytes() == before,
            "witness": wseq(d, s), "still_pending": pending(d, s)}


def P3_outstanding_no_window(d):
    """E4: the report uses the owner's own window (since it signed the last attested crossing in the category).
    (a) A 'no' to a sibling given BEFORE the owner signed an attested verbosity crossing is outside the window:
    not reported. (b) A 'no' given AFTER it is reported."""
    s, o = H.born(K, d)
    y = H.propose(s, "verbosity")
    o.answer(s, y["proposal_id"], "no")
    x = H.propose(s, "verbosity")
    o.answer(s, x["proposal_id"], "yes")                  # the latest in-category answer is now 'yes'
    H.apply_ok(K, s, o, x)                                 # signed after the 'no'; attested
    H.apply_ok(K, s, o, H.propose(s, "formality", CASUAL), attest=False)
    a = outcome(lambda: o.restore(s)["owner_no_outstanding"])
    z = H.propose(s, "verbosity")
    o.answer(s, z["proposal_id"], "no")                    # after the owner signed x
    H.apply_ok(K, s, o, H.propose(s, "formality", CASUAL), attest=False)
    b = outcome(lambda: o.restore(s)["owner_no_outstanding"])
    return {"no_before_last_attested_signing": a, "no_after_it": b}


def P4_cross_process_contention(d):
    """Q across processes (as v0.8.6/v0.8.7 P3): 4 processes dwell 50 times each, reloading on StaleOrganism,
    while a 5th attests 10 times. 200 dwellings saved, witness 10, fresh audit."""
    s, o = H.born(K, d)
    base = sum(1 for e in s.trace if e.get("event") == "dwelling")
    pem = d / "owner.pem"; pem.write_text(o._pem)
    worker = d / "worker.py"; worker.write_text(WORKER)
    t0 = time.time()
    procs = [subprocess.Popen([sys.executable, "-I", str(worker), str(CAND), str(s.data_dir), "50", "dweller"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
    procs.append(subprocess.Popen([sys.executable, "-I", str(worker), str(CAND), str(s.data_dir), "10", "attester", str(pem)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
    results = []
    for p in procs:
        out, err = p.communicate(timeout=600)
        results.append(json.loads(out) if p.returncode == 0 else {"rc": p.returncode, "err": err[-400:]})
    f = H.expect_loads(K, s.data_dir)
    return {"workers": results, "new_dwellings_saved": sum(1 for e in f.trace if e.get("event") == "dwelling") - base,
            "expected": 200, "witness": wseq(d, s), "fresh_audit": outcome(lambda: o.audit(f)),
            "seconds": round(time.time() - t0, 1)}


def P5_threads_mixed_operations(d, seconds=6.0):
    """Q with the lock-order check in place (as v0.8.7 P4): dwell; propose-sign-apply-attest; owner answers;
    audits through a second owner session. No thread may hit LockOrderRefused, since none starts an owner
    operation inside an organism operation."""
    s, o = H.born(K, d)
    o2 = K.OwnerTool(o._pem, K.OwnerWitness(d / "witness.json"))
    stop = time.time() + seconds
    errs, counts = [], {"dwell": 0, "cross": 0, "answer": 0, "audit": 0}
    def loop(name, body):
        def run():
            while time.time() < stop:
                try:
                    body(); counts[name] += 1
                except Exception as e:
                    errs.append(f"{name}: {type(e).__name__}: {str(e)[:120]}"); return
        return threading.Thread(target=run, name=name)
    def dwell(): s.dwell_or_propose("formality", "evt", "hmm ok")
    def cross():
        r = s.dwell_or_propose("verbosity", "evt", PREF)
        s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"])); o.attest(s)
    def answer():
        r = s.dwell_or_propose("curiosity", "evt", "I always prefer you ask fewer questions")
        if r["status"] == "proposal": o.answer(s, r["proposal_id"], "unsure")
    def audit(): o2.audit(s)
    ts = [loop("dwell", dwell), loop("cross", cross), loop("answer", answer), loop("audit", audit)]
    for t in ts: t.start()
    for t in ts: t.join(120)
    f = H.expect_loads(K, s.data_dir)
    st = disk(s)
    return {"counts": counts, "errors": errs[:6], "lock_order_refusals": sum("LockOrderRefused" in e for e in errs),
            "saved_checkpoint": st["checkpoint"]["sequence"], "witness": wseq(d, s),
            "fresh_audit": outcome(lambda: o.audit(f))}


def P6_thread_state_after_refusals(d):
    """The per-thread lock count and save mark are released on every exit path. After an operation that raises
    inside the organism lock (an unknown category), a LockOrderRefused, and a ReentryRefused, the same thread can
    still sign, answer and attest."""
    s, o = H.born(K, d)
    a = outcome(lambda: s.dwell_or_propose("no_such_category", "evt", "hmm ok"))
    def reader(reading, terrain, events):
        reader.got = outcome(lambda: o.sign_proposal(reading["payload_to_sign"]))
        return None
    r = H.propose(s, "verbosity"); sig = o.sign_proposal(r["payload_to_sign"])
    s.reader = reader
    applied = outcome(lambda: s.authorize_and_apply(r["proposal_id"], sig) is not None)
    s.reader = K.contradiction_only_reader
    other = H.expect_loads(K, s.data_dir)
    real = K._durable_write; fired = []
    def write(path, text):
        if Path(path) == s._state_path() and not fired:
            fired.append(outcome(lambda: other.dwell_or_propose("curiosity", "evt", "hmm ok")))
        return real(path, text)
    K._durable_write = write
    try:
        outer = outcome(lambda: s.dwell_or_propose("formality", "evt", "hmm ok")["status"])
    finally:
        K._durable_write = real
    after = {"organism_held": getattr(K._THREAD, "organism_held", None), "saving": sorted(getattr(K._THREAD, "saving", set()))}
    z = H.propose(s, "curiosity", "I always prefer you ask fewer questions")
    ans = outcome(lambda: o.answer(s, z["proposal_id"], "unsure")["status"])
    att = outcome(lambda: o.attest(s))
    return {"unknown_category": a, "reader_owner_call": getattr(reader, "got", None), "apply_with_that_reader": applied,
            "nested_save": fired, "outer_dwell": outer, "thread_state_after": after, "answer": ans, "attest": att,
            "fresh_audit": outcome(lambda: o.audit(H.expect_loads(K, s.data_dir)))}


def P7_lock_order_with_a_second_owner_tool(d):
    """R38: the refusal is per lock path. A reader that calls an owner operation of a second OwnerTool for the
    same owner and witness (same lock file) is refused like the first. One for a different witness directory
    (a different lock file) is refused too, though it could not deadlock with this organism's attest."""
    s, o = H.born(K, d)
    o_same = K.OwnerTool(o._pem, K.OwnerWitness(d / "witness.json"))
    (d / "elsewhere").mkdir()
    o_other = K.OwnerTool(o._pem, K.OwnerWitness(d / "elsewhere" / "witness.json"))
    got = {}
    def reader(reading, terrain, events):
        got["same_lock_file"] = outcome(lambda: o_same.sign_proposal(reading["payload_to_sign"]))
        got["other_lock_file"] = outcome(lambda: o_other.sign_proposal(reading["payload_to_sign"]))
        return None
    r = H.propose(s, "verbosity"); sig = o.sign_proposal(r["payload_to_sign"])
    s.reader = reader
    applied = outcome(lambda: s.authorize_and_apply(r["proposal_id"], sig) is not None)
    return {"reader": got, "apply": applied, "attest": outcome(lambda: o.attest(s))}


def P8_interrupt_points_in_a_save(d):
    """E3 and U at other points: a KeyboardInterrupt raised (a) before the replace (inside the temp-file
    fsync) and (b) after the replace with the re-read succeeding. (a) nothing landed: install rolls back and
    the object stays usable; (b) landed: memory keeps the new checkpoint."""
    res = {}
    for case in ("before_replace", "after_replace"):
        sub = d / case; sub.mkdir()
        s, o = H.born(K, sub)
        real_fsync, real_replace = K.os.fsync, K.os.replace
        state = {"armed": True}
        def fsync(fd):
            if (case == "before_replace" and state["armed"]
                    and os.readlink(f"/proc/self/fd/{fd}").endswith("organism_state.json.tmp")):
                state["armed"] = False; raise KeyboardInterrupt("injected before the replace")
            return real_fsync(fd)
        def replace(a, b):
            real_replace(a, b)
            if case == "after_replace" and state["armed"] and str(b).endswith("organism_state.json"):
                state["armed"] = False; raise KeyboardInterrupt("injected after the replace")
        K.os.fsync, K.os.replace = fsync, replace
        try:
            att = outcome(lambda: o.attest(s))
        finally:
            K.os.fsync, K.os.replace = real_fsync, real_replace
        res[case] = {"attest": att, "memory_checkpoint": s.checkpoint.sequence, "disk_checkpoint": disk(s)["checkpoint"]["sequence"],
                     "next_dwell": outcome(lambda: s.dwell_or_propose("formality", "evt", "hmm ok")["status"]),
                     "fresh_audit": outcome(lambda: o.audit(H.expect_loads(K, s.data_dir))), "witness": wseq(sub, s)}
    return res


def P9_operation_cost(d):
    """Cost of one dwell, v0.8.7 against v0.8.8, same machine, back to back."""
    rows = {}
    for tag, cand, harn in (("v0.8.7", HERE / "v0_8_7_record" / "humble_seed_v0_8_7_candidate.py", HERE / "v0_8_7_record" / "falsify_v0_8_7.py"),
                            ("v0.8.8", CAND, HERE / "falsify_v0_8_8.py")):
        KK = load(cand, "cost" + tag.replace(".", "")); HH = load(harn, "costh" + tag.replace(".", ""))
        with tempfile.TemporaryDirectory() as t:
            s, o = HH.born(KK, Path(t)); out = []
            for target in (10, 500, 2000):
                while len(s.trace) < target - 20: s.dwell_or_propose("formality", "evt", "hmm ok")
                t0 = time.perf_counter()
                for _ in range(20): s.dwell_or_propose("formality", "evt", "hmm ok")
                out.append(f"len {len(s.trace)}: {(time.perf_counter() - t0) / 20 * 1000:.2f} ms")
            rows[tag] = out
    return rows


if __name__ == "__main__":
    out = {}
    for fn in (P1_real_signal_reentry, P2_prefix_route_refuses_what_it_should, P3_outstanding_no_window,
               P4_cross_process_contention, P5_threads_mixed_operations, P6_thread_state_after_refusals,
               P7_lock_order_with_a_second_owner_tool, P8_interrupt_points_in_a_save, P9_operation_cost):
        with tempfile.TemporaryDirectory(prefix="hs088_ap_") as t:
            dd = Path(t) / "case"; dd.mkdir()
            try: out[fn.__name__] = fn(dd)
            except BaseException as e:
                import traceback; out[fn.__name__] = {"ERROR": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-800:]}
        print(fn.__name__, "done", flush=True, file=sys.stderr)
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
