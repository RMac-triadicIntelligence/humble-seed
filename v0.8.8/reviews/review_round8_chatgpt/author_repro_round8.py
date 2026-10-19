#!/usr/bin/env python3
"""Author's independent reproduction of round-8 findings on the frozen v0.8.7 candidate (not scored).
Each case uses the author's own code. The re-entry cases call a public operation from inside the outer
save's write call, standing in for ChatGPT's real same-thread signal (its own battery, re-run unchanged,
uses a real SIGUSR1).
Run from hs087/: python3 -I review_round8_chatgpt/author_repro_round8.py"""
import importlib.util, json, os, stat, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m
K = load(HERE / "humble_seed_v0_8_7_candidate.py", "r8_candidate")
H = load(HERE / "falsify_v0_8_7.py", "r8_harness")
def outcome(fn):
    try: return {"returned": fn()}
    except BaseException as e: return {"exception": type(e).__name__, "message": str(e)[:200]}
def disk(s): return json.loads(s._state_path().read_text())
def wseq(d, s): return K.OwnerWitness(d / "witness.json").ledger[s.organism_id]["sequence"]
def pend(d, s): return K.OwnerWitness(d / "witness.json").pending_for(s.organism_id) is not None


def F1_failed_commit_then_crossing(d):
    """ChatGPT r8 (QB/R20/R1): the witness commit fails after install; an ordinary crossing follows."""
    s, o = H.born(K, d)
    H.apply_ok(K, s, o, H.propose(s, "verbosity"), attest=False)
    real = o.witness.commit
    o.witness.commit = lambda cp: (_ for _ in ()).throw(OSError("injected witness commit failure"))
    first = outcome(lambda: o.attest(s))
    o.witness.commit = real
    second = outcome(lambda: s.authorize_and_apply(*(lambda r: (r["proposal_id"], o.sign_proposal(r["payload_to_sign"])))(H.propose(s, "formality", H.CASUAL)))["status"])
    o2 = K.OwnerTool(o._pem, K.OwnerWitness(d / "witness.json"))
    return {"attest": first, "second_crossing": second, "saved_checkpoint": disk(s)["checkpoint"]["sequence"],
            "witness": wseq(d, s), "pending": pend(d, s),
            "attest_after": outcome(lambda: o2.attest(s)), "audit_after": outcome(lambda: o2.audit(s)),
            "restore_after": outcome(lambda: o2.restore(K.HumbleSeed(s.data_dir))),
            "still_pending": pend(d, s)}


def F2_reentry_between_check_and_write(d):
    """ChatGPT r8 (R31b/QA): a same-thread operation lands between the outer save's generation check and its write."""
    s, o = H.born(K, d)
    other = H.expect_loads(K, s.data_dir)
    real = K._durable_write
    fired = []
    def write(path, text):
        if Path(path) == s._state_path() and not fired:
            fired.append(1)
            other.dwell_or_propose("curiosity", "evt", "hmm ok")      # nested, same thread
            nested = disk(s)
            fired.append({"nested_generation": nested["generation"],
                          "nested_dwellings": [e.get("category") for e in nested["trace"] if e.get("event") == "dwelling"]})
        return real(path, text)
    K._durable_write = write
    try:
        outer = outcome(lambda: s.dwell_or_propose("formality", "evt", "hmm ok")["status"])
    finally:
        K._durable_write = real
    final = disk(s)
    return {"outer": outer, "nested": fired[1] if len(fired) > 1 else None, "final_generation": final["generation"],
            "final_dwellings": [e.get("category") for e in final["trace"] if e.get("event") == "dwelling"],
            "fresh_audit": outcome(lambda: o.audit(H.expect_loads(K, s.data_dir)))}


def F3_restore_overwrites_a_signoff_made_inside_it(d):
    """ChatGPT r8 (QC): during restore's save, a same-thread attestation completes; restore then writes the old head."""
    s, o = H.born(K, d)
    H.dwell(s, "formality", "hmm ok")
    real = K._durable_write
    fired = []
    def write(path, text):
        if Path(path) == s._state_path() and not fired and '"restored"' in text:
            fired.append(1)
            fired.append(outcome(lambda: o.attest(s)))                  # nested, same thread
            fired.append(wseq(d, s))
        return real(path, text)
    K._durable_write = write
    try:
        res = outcome(lambda: o.restore(K.HumbleSeed(s.data_dir)))
    finally:
        K._durable_write = real
    f = outcome(lambda: H.expect_loads(K, s.data_dir).checkpoint.sequence)
    return {"restore": res, "nested_attest": fired[1] if fired else None, "witness_after_nested": fired[2] if fired else None,
            "saved_checkpoint": disk(s)["checkpoint"]["sequence"], "witness": wseq(d, s), "pending": pend(d, s),
            "fresh_load_checkpoint": f,
            "fresh_audit": outcome(lambda: K.OwnerTool(o._pem, K.OwnerWitness(d / "witness.json")).audit(H.expect_loads(K, s.data_dir)))}


def F4_interrupt_during_reread(d):
    """ChatGPT r8 (U2): the directory fsync fails after the replace, and a KeyboardInterrupt arrives during the re-read."""
    s, o = H.born(K, d)
    real_fsync, real_gen = K.os.fsync, s._saved_generation
    ph = {"f": False, "g": False}
    def fsync(fd):
        if not ph["f"] and stat.S_ISDIR(os.fstat(fd).st_mode) and disk(s)["checkpoint"]["sequence"] == 1:
            ph["f"] = True; raise OSError("injected directory fsync failure")
        return real_fsync(fd)
    def gen():
        if ph["f"] and not ph["g"]:
            ph["g"] = True; raise KeyboardInterrupt("injected interrupt during re-read")
        return real_gen()
    K.os.fsync, s._saved_generation = fsync, gen
    try:
        first = outcome(lambda: o.attest(s))
    finally:
        K.os.fsync = real_fsync; del s._saved_generation
    return {"attest": first, "memory_checkpoint": s.checkpoint.sequence, "disk_checkpoint": disk(s)["checkpoint"]["sequence"],
            "memory_generation": s._generation, "disk_generation": disk(s)["generation"],
            "next_dwell": outcome(lambda: s.dwell_or_propose("formality", "evt", "hmm ok")["status"])}


def G1_grok_unfixable_case(d):
    """Grok r8 extra_faults 'attest' case: every _durable_write fails during attest. Grok's check tried restore only
    after a reload, and an unattested state does not load by design. Does restore work from an unloaded object?"""
    s, o = H.born(K, d)
    H.apply_ok(K, s, o, H.propose(s, "verbosity"), attest=False)
    real = K._durable_write
    K._durable_write = lambda p, t: (_ for _ in ()).throw(OSError("injected"))
    try:
        first = outcome(lambda: o.attest(s))
    finally:
        K._durable_write = real
    reload_ = outcome(lambda: H.expect_loads(K, s.data_dir))
    o2 = K.OwnerTool(o._pem, K.OwnerWitness(d / "witness.json"))
    res = outcome(lambda: o2.restore(K.HumbleSeed(s.data_dir)))
    return {"attest": first, "reload": {k: (v if k != "returned" else "loaded") for k, v in reload_.items()},
            "restore_from_unloaded_object": res,
            "fresh_audit_after": outcome(lambda: o2.audit(H.expect_loads(K, s.data_dir)))}


if __name__ == "__main__":
    out = {}
    for fn in (F1_failed_commit_then_crossing, F2_reentry_between_check_and_write,
               F3_restore_overwrites_a_signoff_made_inside_it, F4_interrupt_during_reread, G1_grok_unfixable_case):
        with tempfile.TemporaryDirectory() as t:
            dd = Path(t) / "c"; dd.mkdir()
            try: out[fn.__name__] = fn(dd)
            except BaseException as e:
                import traceback; out[fn.__name__] = {"ERROR": traceback.format_exc()[-900:]}
    print(json.dumps(out, indent=2, default=str))
