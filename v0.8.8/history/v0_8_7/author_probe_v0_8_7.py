#!/usr/bin/env python3
"""Author's post-freeze probes on v0.8.7 (not scored). Each probe tests a claim in its docstring.
Run: python3 -I author_probe_v0_8_7.py"""
import hashlib, importlib.util, json, os, subprocess, sys, tempfile, threading, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
CAND = HERE / "humble_seed_v0_8_7_candidate.py"
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m
K = load(CAND, "ap_candidate")
H = load(HERE / "falsify_v0_8_7.py", "ap_harness")
PREF, CASUAL = H.PREF, H.CASUAL
def outcome(fn):
    try: return f"returned {fn()!r}"[:240]
    except Exception as e: return f"{type(e).__name__}: {e}"[:240]
def wseq(d, s): return K.OwnerWitness(d / "witness.json").ledger[s.organism_id]["sequence"]


def P1_restore_forgets_answers_the_owner_still_holds(d):
    """R36/R18 interaction. Restore discards every event after the attested checkpoint, including the
    organism's copy of owner answers given since. The owner's ledger keeps them. Question: after a restore,
    can the organism apply a crossing that the owner's attestation then refuses on an answer the organism
    no longer sees?"""
    s, o = H.born(K, d)
    y = H.propose(s, "verbosity")
    o.answer(s, y["proposal_id"], "no")                     # the owner says no to reading Y
    x = H.propose(s, "formality", CASUAL)                    # something unattested to discard
    s.authorize_and_apply(x["proposal_id"], o.sign_proposal(x["payload_to_sign"]))
    restored = outcome(lambda: o.restore(s))
    organism_answers = [e.get("answer") for e in s.trace if e.get("event") == "owner_answer"]
    z = H.propose(s, "verbosity")                            # a new verbosity reading
    applied = s.authorize_and_apply(z["proposal_id"], o.sign_proposal(z["payload_to_sign"]))
    att = outcome(lambda: o.attest(s))
    answer_y_again = outcome(lambda: o.answer(s, y["proposal_id"], "yes"))
    return {"restore": restored, "organism_answers_after_restore": organism_answers,
            "owner_ledger_answers_to_Y": o.ledger.answers_to(s.organism_id, y["proposal_id"]),
            "new_verbosity_crossing_applied_by_organism": applied is not None, "attest": att,
            "owner_can_answer_Y_again": answer_y_again}


def P2_restore_twice_and_from_a_stale_or_unusable_object(d):
    """R: restore works from disk. (a) Restoring twice in a row; (b) restoring through a stale object;
    (c) after restore, an object loaded before it is stale."""
    s, o = H.born(K, d)
    early = H.expect_loads(K, s.data_dir)
    H.dwell(s, "formality", "hmm ok")
    first = outcome(lambda: o.restore(s))
    second = outcome(lambda: o.restore(s))
    via_stale = outcome(lambda: o.restore(early))
    early_after = outcome(lambda: early.dwell_or_propose("formality", "evt", "hmm ok")["status"])
    s_after = outcome(lambda: s.dwell_or_propose("formality", "evt", "hmm ok")["status"])
    f = H.expect_loads(K, s.data_dir)
    kept = sorted(p.name for p in s.data_dir.glob("pre_restore_*"))
    return {"first": first, "second": second, "restore_via_stale_object": via_stale,
            "early_object_after_its_own_restore": early_after, "s_after": s_after,
            "fresh_audit": outcome(lambda: o.audit(f)), "kept_files": kept}


def P3_cross_process_contention(d):
    """Q across processes (v0.8.6 P3 repeated): 4 processes dwell 50 times each, reloading on StaleOrganism,
    while a 5th attests 10 times. 200 dwellings saved, witness 10, fresh audit."""
    spec = importlib.util.spec_from_file_location("ap086", HERE / "v0_8_6_record" / "author_probe_v0_8_6.py")
    src = (HERE / "v0_8_6_record" / "author_probe_v0_8_6.py").read_text()
    worker_src = src.split("WORKER = r'''", 1)[1].split("'''", 1)[0]
    s, o = H.born(K, d)
    base = sum(1 for e in s.trace if e.get("event") == "dwelling")
    pem = d / "owner.pem"; pem.write_text(o._pem)
    worker = d / "worker.py"; worker.write_text(worker_src)
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


def P4_threads_mixed_operations(d, seconds=6.0):
    """Q under a wider mix than S1: three threads on one object (dwell; propose-sign-apply-attest;
    owner answers to fresh readings), plus a fourth that audits through another owner session."""
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
    st = json.loads(s._state_path().read_text())
    return {"counts": counts, "errors": errs[:6], "saved_checkpoint": st["checkpoint"]["sequence"],
            "witness": wseq(d, s), "fresh_audit": outcome(lambda: o.audit(f))}


def P5_callback_calls_owner_while_another_thread_attests(d):
    """R35: lock order is owner -> organism. A reader callback runs inside an organism operation (organism lock
    held). If it calls an owner operation while another thread holds the owner lock and waits for the organism
    lock, the two wait on each other. Run in a subprocess with a timeout."""
    code = r'''
import importlib.util, sys, threading, time, json
from pathlib import Path
spec = importlib.util.spec_from_file_location("k", sys.argv[1]); K = importlib.util.module_from_spec(spec)
sys.modules["k"] = K; spec.loader.exec_module(K)
d = Path(sys.argv[2])
s = K.HumbleSeed(d / "org"); _, pem, _ = s.hatch(); o = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json")); o.attest(s)
r = s.dwell_or_propose("verbosity", "evt", "I always prefer shorter answers"); sig = o.sign_proposal(r["payload_to_sign"])
inside = threading.Event()
def reader(reading, terrain, events):
    inside.set(); time.sleep(0.3)
    o.sign_proposal(reading["payload_to_sign"])        # an owner operation from inside the organism lock
    return None
s.reader = reader
t = threading.Thread(target=lambda: s.authorize_and_apply(r["proposal_id"], sig), daemon=True); t.start()
inside.wait(5)
u = threading.Thread(target=lambda: o.attest(s), daemon=True); u.start()
t.join(5); u.join(5)
print(json.dumps({"apply_thread_finished": not t.is_alive(), "attest_thread_finished": not u.is_alive()}))
'''
    p = subprocess.run([sys.executable, "-I", "-c", code, str(CAND), str(d)], capture_output=True, text=True, timeout=60)
    return {"rc": p.returncode, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()[-300:]}


def P6_same_directory_through_a_symlink(d):
    """R35: operations are serialized per data directory. The lock is keyed by os.path.abspath, which does not
    resolve symlinks. Two objects for the same directory, one through a symlink, in one thread: a callback write
    through the symlinked object inside the other's operation. Run in a subprocess with a timeout."""
    code = r'''
import importlib.util, os, sys, json
from pathlib import Path
spec = importlib.util.spec_from_file_location("k", sys.argv[1]); K = importlib.util.module_from_spec(spec)
sys.modules["k"] = K; spec.loader.exec_module(K)
d = Path(sys.argv[2])
s = K.HumbleSeed(d / "org"); _, pem, _ = s.hatch(); o = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json")); o.attest(s)
os.symlink(d / "org", d / "link")
r = s.dwell_or_propose("verbosity", "evt", "I always prefer shorter answers"); sig = o.sign_proposal(r["payload_to_sign"])
b = K.HumbleSeed(d / "link"); b.load()
def reader(reading, terrain, events):
    b.dwell_or_propose("formality", "evt", "hmm ok"); return None
s.reader = reader
try:
    s.authorize_and_apply(r["proposal_id"], sig); print(json.dumps({"apply": "returned"}))
except Exception as e:
    print(json.dumps({"apply": f"{type(e).__name__}: {e}"[:200]}))
'''
    try:
        p = subprocess.run([sys.executable, "-I", "-c", code, str(CAND), str(d)], capture_output=True, text=True, timeout=20)
        return {"rc": p.returncode, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()[-300:]}
    except subprocess.TimeoutExpired:
        return {"timed_out_after_s": 20}


def P7_operation_cost(d):
    """R34/R35: the cost of one dwell with the operation lock, v0.8.6 against v0.8.7, same machine, back to back."""
    rows = {}
    for tag, cand, harn in (("v0.8.6", HERE / "v0_8_6_record" / "humble_seed_v0_8_6_candidate.py", HERE / "v0_8_6_record" / "falsify_v0_8_6.py"),
                            ("v0.8.7", CAND, HERE / "falsify_v0_8_7.py")):
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


def P8_restore_with_a_tampered_basin_or_pending(d):
    """R36: restore keeps the basin and verifies the restored state. A basin entry edited on disk (resealed)
    is not covered by the checkpoint: does restore carry it forward, and does the result load?"""
    s, o = H.born(K, d)
    H.dwell(s, "formality", "hmm ok")
    def edit(st):
        st["basin"][0]["evidence"] = ["planted after attestation"]
    K._reseal_attack(s, edit)
    loads_before = outcome(lambda: H.expect_loads(K, s.data_dir) and "loads")
    r = outcome(lambda: o.restore(s))
    f = outcome(lambda: K.HumbleSeed(s.data_dir).load())
    basin = json.loads(s._state_path().read_text())["basin"]
    return {"tampered_file_loads_before_restore": loads_before, "restore": r, "load_after": f,
            "basin_evidence_after": [b["evidence"] for b in basin]}


if __name__ == "__main__":
    out = {}
    for fn in (P1_restore_forgets_answers_the_owner_still_holds, P2_restore_twice_and_from_a_stale_or_unusable_object,
               P3_cross_process_contention, P4_threads_mixed_operations, P5_callback_calls_owner_while_another_thread_attests,
               P6_same_directory_through_a_symlink, P7_operation_cost, P8_restore_with_a_tampered_basin_or_pending):
        with tempfile.TemporaryDirectory(prefix="hs087_ap_") as t:
            dd = Path(t) / "case"; dd.mkdir()
            try: out[fn.__name__] = fn(dd)
            except Exception as e:
                import traceback; out[fn.__name__] = {"ERROR": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-800:]}
        print(fn.__name__, "done", flush=True, file=sys.stderr)
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
