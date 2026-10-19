#!/usr/bin/env python3
"""Author's independent reproduction of ChatGPT's round-7 Q1 and I2 on the frozen v0.8.6 candidate.
Q1a uses a different pause point from ChatGPT's (it pauses at the organism-lock call rather than in
_canonical_json). Q1c uses no instrumentation at all: two real threads share one organism object.
Run from hs086/: python3 -I review_round7_chatgpt/author_repro_round7.py"""
import importlib.util, json, os, stat, sys, tempfile, threading, time
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m
K = load(HERE / "humble_seed_v0_8_6_candidate.py", "rp_candidate")
PREF, PLAIN = "I always prefer shorter answers", "hmm ok"
def born(d):
    s = K.HumbleSeed(d / "org"); _, pem, _ = s.hatch(); o = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json"))
    assert o.attest(s); return s, o
def outcome(fn):
    try: return {"returned": fn()}
    except Exception as e: return {"exception": type(e).__name__, "message": str(e)[:160]}
def disk(s): return json.loads(s._state_path().read_text())
def wseq(d, s): return K.OwnerWitness(d / "witness.json").ledger[s.organism_id]["sequence"]


def Q1a_paused_at_lock(d, checkpoint):
    """Thread A's save has built its snapshot and is about to take the organism lock; thread B, on the
    same object, saves (or the owner attests it). Then A continues."""
    s, o = born(d)
    real_lock = s._organism_lock
    at_lock, go = threading.Event(), threading.Event()
    def lock_pausing_A():
        if threading.current_thread().name == "A" and not at_lock.is_set():
            at_lock.set(); go.wait(10)
        return real_lock()
    s._organism_lock = lock_pausing_A
    res = {}
    t = threading.Thread(target=lambda: res.update(A=outcome(lambda: s.dwell_or_propose("curiosity", "evt", PLAIN)["status"])), name="A")
    t.start(); assert at_lock.wait(10)
    if checkpoint:
        r = s.dwell_or_propose("verbosity", "evt", PREF)
        s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
        res["B"] = outcome(lambda: o.attest(s))
    else:
        res["B"] = outcome(lambda: s.dwell_or_propose("formality", "evt", PLAIN)["status"])
    middle = disk(s)
    go.set(); t.join(10); s._organism_lock = real_lock
    final = disk(s)
    f = K.HumbleSeed(s.data_dir); loaded = outcome(f.load)
    return {"A": res["A"], "B": res["B"],
            "middle": {"generation": middle["generation"], "checkpoint": middle["checkpoint"]["sequence"],
                       "dwellings": [e.get("category") for e in middle["trace"] if e.get("event") == "dwelling"]},
            "final": {"generation": final["generation"], "checkpoint": final["checkpoint"]["sequence"],
                      "dwellings": [e.get("category") for e in final["trace"] if e.get("event") == "dwelling"]},
            "witness": wseq(d, s), "fresh_load": loaded,
            "fresh_audit": outcome(lambda: K.OwnerTool(o._pem, K.OwnerWitness(d / "witness.json")).audit(f)) if "returned" in loaded else None}


def Q1c_two_real_threads(d, seconds=20):
    """No patching. Thread A dwells in a loop on object s; thread B applies and attests crossings on the
    same object s. Afterwards, check the saved file against the witness and count the dwellings."""
    s, o = born(d)
    stop = time.time() + seconds
    a_ok, a_err, b_ok, b_err = [0], [], [0], []
    def A():
        while time.time() < stop:
            try: s.dwell_or_propose("formality", "evt", PLAIN); a_ok[0] += 1
            except Exception as e: a_err.append(f"{type(e).__name__}: {str(e)[:100]}")
    def B():
        while time.time() < stop:
            try:
                r = s.dwell_or_propose("verbosity", "evt", PREF)
                if r["status"] == "proposal":
                    s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
                o.attest(s); b_ok[0] += 1
            except Exception as e: b_err.append(f"{type(e).__name__}: {str(e)[:100]}")
    ta, tb = threading.Thread(target=A), threading.Thread(target=B)
    ta.start(); tb.start(); ta.join(); tb.join()
    final = disk(s)
    f = K.HumbleSeed(s.data_dir); loaded = outcome(f.load)
    saved_dwellings = sum(1 for e in final["trace"] if e.get("event") == "dwelling" and e.get("category") == "formality")
    from collections import Counter
    return {"A_dwells_returned": a_ok[0], "A_errors": dict(Counter(a_err).most_common(4)),
            "B_attests_returned": b_ok[0], "B_errors": dict(Counter(b_err).most_common(4)),
            "formality_dwellings_saved": saved_dwellings, "lost_dwellings": a_ok[0] - saved_dwellings,
            "saved_checkpoint": final["checkpoint"]["sequence"], "witness": wseq(d, s),
            "fresh_load": loaded,
            "fresh_audit": outcome(lambda: K.OwnerTool(o._pem, K.OwnerWitness(d / "witness.json")).audit(f)) if "returned" in loaded else None}


def I2_double_fault(d):
    """Checkpoint save: the replace lands, the directory fsync fails, and the generation re-read fails too."""
    s, o = born(d)
    r = s.dwell_or_propose("verbosity", "evt", PREF); s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
    real_fsync, real_gen = K.os.fsync, s._saved_generation
    phase = {"replaced": False}
    def fsync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode) and disk(s)["checkpoint"]["sequence"] == 1 and not phase["replaced"]:
            phase["replaced"] = True; raise OSError("injected: directory fsync failed after replace")
        return real_fsync(fd)
    def gen():
        if phase["replaced"]: raise OSError("injected: re-read failed")
        return real_gen()
    K.os.fsync, s._saved_generation = fsync, gen
    try: first = outcome(lambda: o.attest(s))
    finally: K.os.fsync = real_fsync; s._saved_generation = real_gen
    after = {"memory_checkpoint": s.checkpoint.sequence, "disk_checkpoint": disk(s)["checkpoint"]["sequence"],
             "memory_generation": s._generation, "disk_generation": disk(s)["generation"]}
    return {"attest": first, "after": after, "same_object_next_dwell": outcome(lambda: s.dwell_or_propose("formality", "evt", PLAIN)["status"]),
            "same_object_retry_attest": outcome(lambda: o.attest(s)), "witness_after_retry": wseq(d, s),
            "fresh_audit": outcome(lambda: o.audit((lambda f: (f.load(), f)[1])(K.HumbleSeed(s.data_dir))))}


if __name__ == "__main__":
    out = {}
    for name, fn in (("Q1a_dwell_vs_dwell", lambda d: Q1a_paused_at_lock(d, False)),
                     ("Q1a_dwell_vs_attest", lambda d: Q1a_paused_at_lock(d, True)),
                     ("Q1c_two_real_threads", Q1c_two_real_threads),
                     ("I2_double_fault", I2_double_fault)):
        with tempfile.TemporaryDirectory() as t:
            dd = Path(t) / "c"; dd.mkdir()
            try: out[name] = fn(dd)
            except Exception as e:
                import traceback; out[name] = {"ERROR": traceback.format_exc()[-900:]}
        print(name, "done", file=sys.stderr, flush=True)
    print(json.dumps(out, indent=2, default=str))
