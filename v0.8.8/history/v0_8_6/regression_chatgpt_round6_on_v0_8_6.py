#!/usr/bin/env python3
"""ChatGPT round-6 probe sequences (independent/review_probes.py), same steps, run against v0.8.6.
Its asserts encoded v0.8.5's behaviour. Here each step's outcome is recorded instead.
Omitted: corrected_T57 and repaired_paths_controls. The frozen v0.8.6 harness already runs
both (T57 corrected in the declaration; the listed tests are T41-T61).
Run: python3 -I regression_chatgpt_round6_on_v0_8_6.py"""
import importlib.util, json, os, stat, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent


def load(path, alias):
    spec = importlib.util.spec_from_file_location(alias, path); m = importlib.util.module_from_spec(spec)
    sys.modules[alias] = m; spec.loader.exec_module(m); return m


K = load(HERE / "humble_seed_v0_8_6_candidate.py", "r6_candidate")
PREF = "I always prefer shorter answers"


def born(d):
    s = K.HumbleSeed(d / "org"); _, pem, _ = s.hatch(); o = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json"))
    assert o.attest(s); return s, o
def prop(s, cat="verbosity"):
    r = s.dwell_or_propose(cat, "probe", PREF); assert r["status"] == "proposal"; return r
def apply(s, o, r):
    a = s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"])); assert a is not None; return a
def fresh(s):
    f = K.HumbleSeed(s.data_dir); f.load(); return f
def result(fn):
    try: return {"returned": fn()}
    except Exception as e: return {"exception": type(e).__name__, "message": str(e)}
def witness(o, s): return K.OwnerWitness(o.witness.path).ledger[s.organism_id]["sequence"]
def pending(o, s): return K.OwnerWitness(o.witness.path).pending_for(s.organism_id) is not None
def disk(s): return json.loads(s._state_path().read_text())


def stale_public_write(d):
    s, o = born(d); stale = fresh(s)
    apply(s, o, prop(s)); assert o.attest(s)
    before = {"saved_sequence": disk(s)["checkpoint"]["sequence"], "witness_sequence": witness(o, s),
              "verbosity": disk(s)["character"]["verbosity"]}
    response = result(lambda: stale.dwell_or_propose("curiosity", "ordinary", "hmm ok")["status"])
    f = fresh(s)
    after = {"saved_sequence": f.checkpoint.sequence, "witness_sequence": witness(o, s), "verbosity": f.character["verbosity"]}
    return {"before": before, "stale_ordinary_write": response, "after": after,
            "fresh_audit": result(lambda: o.audit(f)), "fresh_attest": result(lambda: o.attest(f))}


def post_replace_fsync_failure(d):
    s, o = born(d); apply(s, o, prop(s))
    original = K.os.fsync; seen = []
    def fail_directory(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode) and disk(s)["checkpoint"]["sequence"] == 1 and not seen:
            seen.append("organism replacement visible before directory fsync")
            raise OSError("injected directory fsync failure AFTER organism os.replace")
        return original(fd)
    K.os.fsync = fail_directory
    try: first = result(lambda: o.attest(s))
    finally: K.os.fsync = original
    state = {"memory_sequence": s.checkpoint.sequence, "saved_sequence": disk(s)["checkpoint"]["sequence"],
             "witness_sequence": witness(o, s), "intent_pending": pending(o, s)}
    retry = result(lambda: o.attest(s))
    after = {"memory_sequence": s.checkpoint.sequence, "saved_sequence": disk(s)["checkpoint"]["sequence"],
             "witness_sequence": witness(o, s), "intent_pending": pending(o, s)}
    f = fresh(s)
    return {"fault_reached": seen, "first_attest": first, "after_failure": state, "same_object_retry": retry,
            "after_retry": after, "reloaded_audit": result(lambda: o.audit(f)), "reloaded_attest": result(lambda: o.attest(f))}


def interrupted_commit_stale_write(d):
    s, o = born(d); stale = fresh(s); apply(s, o, prop(s))
    original = o.witness.commit
    def stop(cp): raise OSError("interrupted before witness advance")
    o.witness.commit = stop
    try: first = result(lambda: o.attest(s))
    finally: o.witness.commit = original
    before = {"saved_sequence": disk(s)["checkpoint"]["sequence"], "witness_sequence": witness(o, s)}
    stale_write = result(lambda: stale.dwell_or_propose("curiosity", "evt", "ordinary")["status"])
    f = fresh(s); aud = result(lambda: o.audit(f))
    after = {"saved_sequence": disk(s)["checkpoint"]["sequence"], "witness_sequence": witness(o, s),
             "verbosity": f.character["verbosity"], "intent_pending": pending(o, s)}
    return {"injected_interruption": first, "before_stale_write": before, "stale_write": stale_write,
            "fresh_audit": aud, "after_stale_write_and_recovery": after}


def advanced_memory_save_during_attest(d):
    # ChatGPT's hook lets the stale write's exception propagate out of commit; kept as written.
    s, o = born(d); stale = fresh(s); apply(s, o, prop(s)); original = o.witness.commit
    def interleave(cp):
        stale.dwell_or_propose("curiosity", "ordinary", "ordinary use")
        return original(cp)
    o.witness.commit = interleave
    try: att = result(lambda: o.attest(s))
    finally: o.witness.commit = original
    mid = {"saved_sequence": disk(s)["checkpoint"]["sequence"], "witness_sequence": witness(o, s), "intent_pending": pending(o, s)}
    f = fresh(s); aud = result(lambda: o.audit(f))
    return {"attest": att, "after_attest": mid, "fresh_audit": aud,
            "after_audit": {"saved_sequence": f.checkpoint.sequence, "witness_sequence": witness(o, s),
                            "verbosity": f.character["verbosity"], "intent_pending": pending(o, s)}}


def authority_controls(d):
    records = {}
    s, o = born(d / "wrong_owner"); s2, o2 = born(d / "other")
    records["wrong_owner"] = result(lambda: o2.verify_consequence(s, s.checkpoint_request()))
    for cat in ["verbosity", "formality", "curiosity", "verbosity"]:
        apply(s, o, prop(s, cat)); assert o.attest(s)
    f = fresh(s); records["normal_crossings"] = {"mutation_sequence": f.mutation_sequence,
                                                 "audit": result(lambda: o.audit(f)), "character": f.character}
    for e in s.trace:
        if e.get("event") == "authorized_mutation": e["record"]["unverified_annotation"] = "edited after checkpoint"; break
    bodies = [{k: v for k, v in e.items() if k not in ("entry_hash", "prev_hash")} for e in s.trace]
    s.trace = []; s._trace_head = "0" * 64
    for e in bodies: s._append_trace(e)
    records["rewrite_save"] = result(s._save)
    records["rewritten_attested_history"] = result(lambda: o.attest(s))
    return records


def window_orderings(d):
    s, o = born(d); y = prop(s); o.answer(s, y["proposal_id"], "no"); x = prop(s)
    a = apply(s, o, x); first = result(lambda: o.attest(s))
    o.answer(s, y["proposal_id"], "yes"); second = result(lambda: o.attest(s)); f = fresh(s)
    return {"fresh_reading_apply": a["status"], "owner_no_before_issuance_attest": first,
            "genuine_owner_yes_releases": second, "audit": result(lambda: o.audit(f))}


def pending_recovery_refusals(d):
    values = {}
    for name in ["unreadable", "neither"]:
        s, o = born(d / name); apply(s, o, prop(s)); original = s.install_checkpoint
        def stop(cp, sig): raise OSError("before install")
        s.install_checkpoint = stop
        try: result(lambda: o.attest(s))
        finally: s.install_checkpoint = original
        if name == "unreadable": s._state_path().write_text("{")
        else:
            data = disk(s); data["checkpoint"]["sequence"] = 999; s._state_path().write_text(json.dumps(data))
        values[name] = {"audit": result(lambda: o.audit(s)), "witness_sequence": witness(o, s), "intent_pending": pending(o, s)}
    return values


if __name__ == "__main__":
    out = {}
    for fn in (stale_public_write, post_replace_fsync_failure, interrupted_commit_stale_write,
               advanced_memory_save_during_attest, authority_controls, window_orderings, pending_recovery_refusals):
        with tempfile.TemporaryDirectory(prefix="hs086_r6_") as t:
            d = Path(t) / "case"; d.mkdir()
            out[fn.__name__] = result(lambda: fn(d))
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
