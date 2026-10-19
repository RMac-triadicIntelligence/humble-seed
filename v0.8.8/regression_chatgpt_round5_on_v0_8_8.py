#!/usr/bin/env python3
"""ChatGPT round-5 probe sequences (independent/probes.py), same steps, run against v0.8.8.
Its asserts encoded v0.8.4's behaviour; here each step's outcome is reported instead."""
import importlib.util, json, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m
K = load(HERE / "humble_seed_v0_8_8_candidate.py", "r5_candidate")
H = load(HERE / "falsify_v0_8_8.py", "r5_harness")
def born(d): return H.born(K, d)
def apply(s, o, r, **kw):
    return s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]), **kw)
def outcome(fn):
    try: return {"returned": fn()}
    except Exception as e: return {"exception": type(e).__name__, "message": str(e)}
def disk_seq(s): return json.loads(s._state_path().read_text())["checkpoint"]["sequence"]
def witness_seq(o, s): return K.OwnerWitness(o.witness.path).ledger[s.organism_id]["sequence"]

def failed_install_then_ram_recovery(d):
    s, o = born(d); apply(s, o, H.propose(s, "verbosity"))
    real = s._save
    def fail(): raise OSError("injected state-save failure before durable write")
    s._save = fail; interrupted = outcome(lambda: o.attest(s)); s._save = real
    before = {"ram": s.checkpoint.sequence, "disk": disk_seq(s), "witness": witness_seq(o, s)}
    audit = outcome(lambda: o.audit(s))
    after = {"ram": s.checkpoint.sequence, "disk": disk_seq(s), "witness": witness_seq(o, s)}
    fresh = K.HumbleSeed(s.data_dir); reload_ = outcome(fresh.load)
    retry = outcome(lambda: o.attest(s))
    f2 = K.HumbleSeed(s.data_dir); reload2 = outcome(f2.load); audit2 = outcome(lambda: o.audit(f2))
    return dict(interruption=interrupted, before_recovery=before, audit_same_object=audit, after_recovery=after,
                restart_load_before_retry=reload_, retry_attest_same_object=retry,
                restart_load_after_retry=reload2, restart_audit_after_retry=audit2)

def stale_object_abandons_installed_intent(d):
    s, o = born(d); stale = K.HumbleSeed(s.data_dir); stale.load(); apply(s, o, H.propose(s, "verbosity"))
    real = o.witness.commit
    def fail(cp): raise OSError("injected interruption after durable organism install")
    o.witness.commit = fail; interrupted = outcome(lambda: o.attest(s)); o.witness.commit = real
    before = {"disk": disk_seq(s), "witness": witness_seq(o, s), "pending": o.witness.pending_for(s.organism_id) is not None}
    audit_stale = outcome(lambda: o.audit(stale))
    after = {"disk": disk_seq(s), "witness": witness_seq(o, s), "pending": o.witness.pending_for(s.organism_id) is not None}
    fresh = K.HumbleSeed(s.data_dir); fresh.load()
    audit_fresh = outcome(lambda: o.audit(fresh))
    return dict(interruption=interrupted, before=before, audit_stale=audit_stale, after=after, audit_actual_disk_state=audit_fresh)

def long_annotation_strands_valid_crossing(d):
    s, o = born(d); r = H.propose(s, "verbosity"); res = apply(s, o, r, annotation="a" * 2001)
    return dict(apply=None if res is None else res["status"], last_event=s.trace[-1].get("event"),
                reason=s.trace[-1].get("reason"), proposal_still_pending=r["proposal_id"] in s.pending,
                attest=outcome(lambda: o.attest(s)), restart_load=outcome(K.HumbleSeed(s.data_dir).load))

def pre_sign_category_no_bypass(d):
    s, o = born(d); x = H.propose(s, "verbosity"); y = H.propose(s, "verbosity")
    o.answer(s, y["proposal_id"], "no")
    s.record_owner_answer(y["proposal_id"], "yes", "organism forged correction")
    res = apply(s, o, x); attest = outcome(lambda: o.attest(s))
    return dict(authoritative_owner_answers_to_Y=o.ledger.answers_to(s.organism_id, y["proposal_id"]),
                apply_X=None if res is None else res["status"], attest=attest, witness=witness_seq(o, s))

if __name__ == "__main__":
    out = {}
    for f in (failed_install_then_ram_recovery, stale_object_abandons_installed_intent,
              long_annotation_strands_valid_crossing, pre_sign_category_no_bypass):
        with tempfile.TemporaryDirectory(prefix="hs088_r5_") as t:
            out[f.__name__] = f(Path(t) / "case")
    print(json.dumps(out, indent=2, sort_keys=True))
