#!/usr/bin/env python3
"""Author's post-freeze probes on v0.8.6 (not scored). Each probe tests a claim in its docstring.
Run: python3 -I author_probe_v0_8_6.py"""
import importlib.util, json, subprocess, sys, tempfile, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
CAND = HERE / "humble_seed_v0_8_6_candidate.py"
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m
K = load(CAND, "ap_candidate")
H = load(HERE / "falsify_v0_8_6.py", "ap_harness")
def outcome(fn):
    try: return f"returned {fn()!r}"
    except Exception as e: return f"{type(e).__name__}: {e}"
def wseq(d, s): return K.OwnerWitness(d / "witness.json").ledger[s.organism_id]["sequence"]
def pending(d, s): return K.OwnerWitness(d / "witness.json").pending_for(s.organism_id) is not None


def P1_hatch_over_a_state_without_generation(d):
    """Claim O: 'A new hatch cannot overwrite an existing organism.' Case (a) is T67 (a v0.8.6 file).
    Case (b): the saved file has no generation field (a v0.8.5-era file, or one edited by hand)."""
    out = {}
    for case in ("a_v086_file", "b_file_without_generation"):
        s, o = H.born(K, d / case)
        if case.startswith("b"):
            st = json.loads(s._state_path().read_text()); del st["generation"]
            s._state_path().write_text(json.dumps(st, sort_keys=True, separators=(",", ":")))
        before = s._state_path().read_bytes()
        second = K.HumbleSeed(s.data_dir)
        r = outcome(lambda: second.hatch()[0])
        after = s._state_path().read_bytes()
        out[case] = {"second_hatch": r[:140], "saved_file_unchanged": before == after,
                     "saved_organism_id_now": json.loads(after)["organism_id"] == s.organism_id and "original" or "replaced"}
    return out


def P2_resealed_forgery_claiming_the_pending_checkpoint(d):
    """Claim C: recovery completes only from a saved state that loads and verifies on its own.
    After an interrupted install, a current object writes through the protocol (CAS passes) a state
    carrying the pending checkpoint and signature: (a) with the approved content, (b) with the
    character changed. The seal is recomputed by the save, so only the owner checkpoint can object."""
    out = {}
    for case in ("a_content_as_approved", "b_character_forged"):
        dd = d / case
        s, o = H.born(K, dd)
        H.apply_ok(K, s, o, H.propose(s, "verbosity"), attest=False)
        real = s.install_checkpoint
        def crash_before(cp, sig): raise OSError("interrupted before install")
        s.install_checkpoint = crash_before
        try: o.attest(s)
        except OSError: pass
        finally: s.install_checkpoint = real
        p = K.OwnerWitness(dd / "witness.json").pending_for(s.organism_id)
        f = H.expect_loads(K, s.data_dir)
        f.checkpoint, f.checkpoint_sig = K.Checkpoint(**p["checkpoint"]), p["signature_b64"]
        if case.startswith("b"):
            f.character["formality"] = 0.99
        saved = outcome(f._save)
        aud = outcome(lambda: o.audit(H.expect_loads(K, s.data_dir)) if case.startswith("a") else o.audit(s))
        out[case] = {"protocol_save": saved, "audit": aud[:220], "witness": wseq(dd, s), "intent_pending": pending(dd, s)}
    return out


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


def P3_concurrent_writers_and_attester(d):
    """Claim O under real contention: 4 processes each dwell 50 times (reloading when refused as stale)
    while a 5th process attests 10 times. No update may be lost: the saved trace must hold exactly
    200 new dwelling events, the witness must sit at 10 attestations past genesis, and a fresh load
    must audit."""
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
    dwellings = sum(1 for e in f.trace if e.get("event") == "dwelling") - base
    return {"workers": results, "new_dwelling_events_saved": dwellings, "expected": 200,
            "witness": wseq(d, s), "expected_witness": 10, "fresh_audit": outcome(lambda: o.audit(f)),
            "seconds": round(time.time() - t0, 1)}


def P4_owner_refusal_wording_names_the_right_answer(d):
    """Claim M: the refusal names the owner answer that holds the crossing. (a) the owner said 'no'
    to this reading; (b) the owner said 'no' to another reading in the category. In both the organism
    holds a forged 'yes', so it applies and only the owner's attestation objects."""
    out = {}
    for case in ("a_this_reading", "b_other_reading"):
        dd = d / case
        s, o = H.born(K, dd)
        x = H.propose(s, "verbosity")
        target = x if case.startswith("a") else H.propose(s, "verbosity")
        o.answer(s, target["proposal_id"], "no")
        s.record_owner_answer(target["proposal_id"], "yes", "organism forged correction")
        applied = s.authorize_and_apply(x["proposal_id"], o.sign_proposal(x["payload_to_sign"]))
        out[case] = {"applied": applied is not None, "attest": outcome(lambda: o.attest(s))}
    return out


def P5_save_cost_grows_with_the_trace(d):
    """R34: every save re-reads the saved state to check its generation. Time per dwell vs trace length."""
    s, o = H.born(K, d)
    rows = {}
    for target in (10, 500, 2000):
        while len(s.trace) < target - 20:
            s.dwell_or_propose("formality", "evt", "hmm ok")
        t = time.perf_counter()
        for _ in range(20):
            s.dwell_or_propose("formality", "evt", "hmm ok")
        rows[f"trace_len_{len(s.trace)}"] = f"{(time.perf_counter() - t) / 20 * 1000:.2f} ms per dwell"
    return rows


def P6_failed_non_install_saves(d):
    """R31 (revised) and I. (a) A dwell whose directory fsync fails after the replace: the object records
    the landed generation and keeps writing. (b) A dwell whose replace itself fails: the object is
    ahead of its disk; its next save writes both events; no other object can overwrite in between."""
    out = {}
    s, o = H.born(K, d / "a")
    real_fsync = K.os.fsync; fired = []
    import os as _os, stat as _stat
    def fail_dir(fd):
        if not fired and _stat.S_ISDIR(_os.fstat(fd).st_mode):
            fired.append(1); raise OSError("injected directory fsync failure after replace")
        return real_fsync(fd)
    K.os.fsync = fail_dir
    try: first = outcome(lambda: s.dwell_or_propose("formality", "evt", "hmm ok")["status"])
    finally: K.os.fsync = real_fsync
    second = outcome(lambda: s.dwell_or_propose("formality", "evt", "hmm ok")["status"])
    f = H.expect_loads(K, s.data_dir)
    out["a_dir_fsync_fails"] = {"first": first, "second_same_object": second,
                                "saved_trace_len": len(f.trace), "object_trace_len": len(s.trace)}
    s, o = H.born(K, d / "b")
    other = H.expect_loads(K, s.data_dir)
    real_replace = K.os.replace; fired = []
    def fail_replace(a, b):
        if not fired: fired.append(1); raise OSError("injected replace failure")
        return real_replace(a, b)
    K.os.replace = fail_replace
    try: first = outcome(lambda: s.dwell_or_propose("formality", "evt", "hmm ok")["status"])
    finally: K.os.replace = real_replace
    between = outcome(lambda: other.dwell_or_propose("curiosity", "evt", "hmm ok")["status"])
    second = outcome(lambda: s.dwell_or_propose("formality", "evt", "hmm ok")["status"])
    f = H.expect_loads(K, s.data_dir)
    out["b_replace_fails"] = {"first": first, "other_current_object_writes_between": between,
                              "second_same_object": second[:160], "saved_trace_len": len(f.trace),
                              "object_trace_len": len(s.trace)}
    return out


def P7_owner_answer_through_a_stale_object(d):
    """R33: an answer given through a stale object reaches the owner's ledger but not the organism."""
    s, o = H.born(K, d)
    r = H.propose(s, "verbosity")
    stale = H.expect_loads(K, s.data_dir)
    H.dwell(s, "formality", "hmm ok")
    ans = outcome(lambda: o.answer(stale, r["proposal_id"], "no"))
    f = H.expect_loads(K, s.data_dir)
    in_organism = [e.get("answer") for e in f.trace if e.get("event") == "owner_answer"]
    applied = f.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
    return {"answer_via_stale_object": ans[:160],
            "owner_ledger": o.ledger.answers_to(s.organism_id, r["proposal_id"]),
            "organism_trace_answers": in_organism,
            "fresh_object_applies": applied is not None,
            "attest": outcome(lambda: o.attest(f))[:200]}


if __name__ == "__main__":
    out = {}
    for fn in (P1_hatch_over_a_state_without_generation, P2_resealed_forgery_claiming_the_pending_checkpoint,
               P3_concurrent_writers_and_attester, P4_owner_refusal_wording_names_the_right_answer,
               P5_save_cost_grows_with_the_trace, P6_failed_non_install_saves, P7_owner_answer_through_a_stale_object):
        with tempfile.TemporaryDirectory(prefix="hs086_ap_") as t:
            d = Path(t) / "case"; d.mkdir()
            try: out[fn.__name__] = fn(d)
            except Exception as e:
                import traceback; out[fn.__name__] = {"ERROR": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-800:]}
        print(fn.__name__, "done", flush=True, file=sys.stderr)
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
