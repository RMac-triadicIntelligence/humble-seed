#!/usr/bin/env python3
"""Author's post-freeze probes on v0.8.5 (not scored). Each probe tests a claim in the docstring."""
import importlib.util, json, sys, tempfile, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m
K = load(HERE / "humble_seed_v0_8_5_candidate.py", "ap_candidate")
H = load(HERE / "falsify_v0_8_5.py", "ap_harness")
def outcome(fn):
    try: return f"returned {fn()!r}"
    except Exception as e: return f"{type(e).__name__}: {e}"
def wseq(d, s): return K.OwnerWitness(d / "witness.json").ledger[s.organism_id]["sequence"]

def P1_earlier_no_blocks_first_crossing(d):
    """R18 (revised): an owner 'no' to another reading in the category, given before this reading
    was issued, blocks the category's first crossing at attestation (the organism applies it) until
    the owner answers again. The owner's window does not read expiry, so Y's age is irrelevant."""
    s, o = H.born(K, d)
    y = H.propose(s, "verbosity"); o.answer(s, y["proposal_id"], "no")
    x = H.propose(s, "verbosity")
    applied = s.authorize_and_apply(x["proposal_id"], o.sign_proposal(x["payload_to_sign"]))
    first = outcome(lambda: o.attest(s))
    o.answer(s, y["proposal_id"], "yes")
    second = outcome(lambda: o.attest(s))
    return {"organism_applied": applied is not None, "attest_with_earlier_no": first, "after_owner_answers_yes": second}

def P2_forged_saved_file_during_recovery(d):
    """R30: a forged saved file can at worst advance the witness to the owner-approved checkpoint;
    the organism then loads only if its content matches it. (a) pending checkpoint copied into a file
    whose content is the approved state; (b) the same with the character also changed."""
    out = {}
    for case in ("a_content_as_approved", "b_content_tampered"):
        dd = d / case
        s, o = H.born(K, dd)
        held = H.expect_loads(K, s.data_dir) if case.startswith("b") else None   # loaded at checkpoint 0
        H.apply_ok(K, s, o, H.propose(s, "verbosity"), attest=False)
        real = s.install_checkpoint
        def crash_before(cp, sig): raise OSError("interrupted before install")
        s.install_checkpoint = crash_before
        outcome(lambda: o.attest(s)); s.install_checkpoint = real
        p = o.witness.pending_for(s.organism_id)
        st = json.loads(s._state_path().read_text())
        st["checkpoint"], st["checkpoint_sig"] = p["checkpoint"], p["signature_b64"]
        if case.startswith("b"):
            st["character"]["formality"] = 0.99
        s._state_path().write_text(json.dumps(st))
        fresh = K.HumbleSeed(s.data_dir); load_ = outcome(fresh.load)
        target = held if held is not None else fresh
        audit = outcome(lambda: o.audit(target))
        out[case] = {"organism_load_of_forged_file": load_, "audit": audit, "witness_after": wseq(dd, s),
                     "pending_after": o.witness.pending_for(s.organism_id) is not None}
    return out

def P3_batch_attest_window(d):
    """W in a batch: X1 and X2 (same category) both unattested. Owner 'no' to Y given after X1 is
    signed and before X2 is issued; organism-only 'yes' to Y. Does one attest catch it?"""
    s, o = H.born(K, d)
    x1 = H.propose(s, "verbosity")
    sig1 = o.sign_proposal(x1["payload_to_sign"])
    y = H.propose(s, "verbosity")
    assert s.authorize_and_apply(x1["proposal_id"], sig1) is not None
    x2 = H.propose(s, "verbosity")
    o.answer(s, y["proposal_id"], "no") if y["proposal_id"] in s.pending else None
    s.record_owner_answer(y["proposal_id"], "yes", "forged") if y["proposal_id"] in s.pending else None
    r2 = s.authorize_and_apply(x2["proposal_id"], o.sign_proposal(x2["payload_to_sign"]))
    return {"y_pending_when_answered": y["proposal_id"] in s.pending, "x2_applied": r2 is not None,
            "batch_attest": outcome(lambda: o.attest(s)), "witness": wseq(d, s)}

def P4_apply_check_cost(d):
    """A runs the replay's chain check over the whole trace on every apply: cost as the trace grows."""
    s, o = H.born(K, d)
    out = {}
    for n in (0, 500, 2000):
        while len(s.trace) < n:
            s._dwell("formality", "padding"); 
        r = H.propose(s, "curiosity", H.FEWER) if s.category_sequence["curiosity"] < 3 else None
        if r is None: break
        p = s.pending[r["proposal_id"]]
        entry = {"event": "authorized_mutation", "record": {}, "timestamp": 0.0}
        t = time.perf_counter(); s._replay_refusal(entry); out[f"trace_len_{len(s.trace)}"] = f"{(time.perf_counter()-t)*1000:.1f} ms"
    return out

if __name__ == "__main__":
    res = {}
    for f in (P1_earlier_no_blocks_first_crossing, P2_forged_saved_file_during_recovery, P3_batch_attest_window, P4_apply_check_cost):
        with tempfile.TemporaryDirectory(prefix="hs085_ap_") as t:
            try: res[f.__name__] = f(Path(t) / "case")
            except Exception as e:
                import traceback; res[f.__name__] = {"PROBE_ERROR": repr(e), "tb": traceback.format_exc()[-600:]}
    print(json.dumps(res, indent=2))
