#!/usr/bin/env python3
"""Derives falsify_v0_8_8.py from falsify_v0_8_7.py. Written after DECLARED_v0_8_8 was frozen."""
import sys
from pathlib import Path

src_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
src = src_path.read_text(encoding="utf-8")


def once(old, new):
    global src
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"anchor occurs {n} times:\n{old[:200]}")
    src = src.replace(old, new)


def every(old, new, expect):
    global src
    n = src.count(old)
    if n != expect:
        raise SystemExit(f"expected {expect} occurrences, found {n}: {old}")
    src = src.replace(old, new)


once('Falsification harness for humble_seed_v0_8_7_candidate.py  (v0.8.7)\n\nWritten AFTER DECLARED_v0_8_7.json was frozen.',
     'Falsification harness for humble_seed_v0_8_8_candidate.py  (v0.8.8)\n\nWritten AFTER DECLARED_v0_8_8.json was frozen.')
once("Run:  python3 -I falsify_v0_8_7.py", "Run:  python3 -I falsify_v0_8_8.py")
once('CANDIDATE = HERE / "humble_seed_v0_8_7_candidate.py"', 'CANDIDATE = HERE / "humble_seed_v0_8_8_candidate.py"')
once('DECL = HERE / "DECLARED_v0_8_7.json"', 'DECL = HERE / "DECLARED_v0_8_8.json"')
once('DECL_SHA = HERE / "DECLARED_v0_8_7.sha256"', 'DECL_SHA = HERE / "DECLARED_v0_8_8.sha256"')
once('DECL_AT = HERE / "DECLARED_v0_8_7.frozen_at"', 'DECL_AT = HERE / "DECLARED_v0_8_8.frozen_at"')
once('raise SystemExit("DECLARED_v0_8_7.json differs', 'raise SystemExit("DECLARED_v0_8_8.json differs')
once('print("Humble Seed v0.8.7 CANDIDATE — falsification harness")',
     'print("Humble Seed v0.8.8 CANDIDATE — falsification harness")')
once('K = load_module(CANDIDATE, "hs087_candidate")', 'K = load_module(CANDIDATE, "hs088_candidate")')
every('prefix="hs087_', 'prefix="hs088_', 3)
once('(HERE / "RESULTS_v0_8_7.json")', '(HERE / "RESULTS_v0_8_8.json")')
once('print("RESULTS_v0_8_7.json written.', 'print("RESULTS_v0_8_8.json written.')
once('    s, o = born(K, d / "v087")', '    s, o = born(K, d / "v088")')
once('return (f"v0.8.7 applied {applied}/4', 'return (f"v0.8.8 applied {applied}/4')

NEW = r'''

# ---------------------------------------------------------------------------
# New in v0.8.8 (T82–T88): the final revision
# ---------------------------------------------------------------------------

def _record_outcome(fn):
    """Run a nested call and keep what happened, to be judged by type afterwards."""
    try:
        return {"result": fn()}
    except BaseException as e:          # judged by judge_outcome; an undeclared type is re-raised there
        return {"error": e}


def judge_outcome(K, outcome, cls, sub=None):
    """v0.8.8 rule: the expected refusal passes; a return or another declared refusal type is a FAIL;
    any other exception is re-raised unchanged (an ERROR)."""
    if "error" not in outcome:
        raise Fail(f"expected {cls.__name__}, but the call returned {outcome.get('result')!r}")
    e = outcome["error"]
    if isinstance(e, cls):
        if sub is not None:
            need(sub in str(e), f"{cls.__name__} for a different reason: {str(e)!r}")
        return f"{type(e).__name__}: {e}"
    declared = (K.StaleOrganism, K.ReentryRefused, K.LockOrderRefused, K.RollbackDetected,
                K.IntegrityError, K.AttestationRefused, ValueError)
    if isinstance(e, declared):
        raise Fail(f"expected {cls.__name__}, got {type(e).__name__}: {e}")
    raise e


def witness_state(K, d, s):
    w = K.OwnerWitness(d / "witness.json")
    return w.ledger[s.organism_id]["sequence"], w.pending_for(s.organism_id) is not None


def T82_restore_resolves_a_failed_commit_followed_by_a_crossing(K, d):
    """ChatGPT, round 8, F1."""
    s, o = born(K, d)
    apply_ok(K, s, o, propose(s, "verbosity"), attest=False)
    v1, f0 = s.character["verbosity"], s.character["formality"]
    real = o.witness.commit

    def interrupted(cp):
        raise OSError("injected: interrupted after the organism installed, before the witness advanced")
    o.witness.commit = interrupted
    try:
        o.attest(s)
    except OSError:
        pass
    else:
        raise Fail("injected interruption did not happen")
    finally:
        o.witness.commit = real
    need(witness_state(K, d, s) == (0, True) and saved_seq(s) == 1,
         "setup: expected witness 0 with an intent pending and the organism at checkpoint 1")
    apply_ok(K, s, o, propose(s, "formality", CASUAL), attest=False)
    why = expect_rollback(K, lambda: o.attest(s), "claims it but does not verify")
    expect_rollback(K, lambda: o.audit(s), "claims it but does not verify")
    out = restore_ok(K, o, s)
    need(out.get("status") == "restored" and out.get("checkpoint_sequence") == 1, f"restore returned {out}")
    need(witness_state(K, d, s) == (1, False),
         f"witness (sequence, pending) = {witness_state(K, d, s)}, expected (1, False)")
    need(s.checkpoint.sequence == 1 and near(s.character["verbosity"], v1) and near(s.character["formality"], f0)
         and s.mutation_sequence == 1,
         f"restored to checkpoint {s.checkpoint.sequence}, verbosity {s.character['verbosity']} (expected {v1}), "
         f"formality {s.character['formality']} (expected {f0}), mutation_sequence {s.mutation_sequence}")
    audit_ok(K, o, expect_loads(K, s.data_dir))
    return why


def T83_a_save_cannot_be_reentered_in_the_same_thread(K, d):
    """ChatGPT, round 8, F2. The nested call stands in for a same-thread signal handler."""
    s, o = born(K, d)
    other = expect_loads(K, s.data_dir)
    g0 = saved_state(s)["generation"]
    real = K._durable_write
    fired, nested = [], []

    def write(path, text):
        if Path(path) == s._state_path() and not fired:
            fired.append(True)
            nested.append(_record_outcome(lambda: other.dwell_or_propose("curiosity", "evt", "hmm ok")))
        return real(path, text)
    K._durable_write = write
    try:
        r = s.dwell_or_propose("formality", "evt", "hmm ok")
    finally:
        K._durable_write = real
    need(r["status"] == "dwelling", f"the outer dwell returned {r['status']}")
    need(nested, "the nested call did not happen as set up")
    why = judge_outcome(K, nested[0], K.ReentryRefused)
    st = saved_state(s)
    need(st["generation"] == g0 + 1, f"saved generation {st['generation']}, expected {g0 + 1}")
    ds = saved_dwellings(s)
    need("formality" in ds and "curiosity" not in ds, f"saved dwellings {ds}")
    audit_ok(K, o, expect_loads(K, s.data_dir))
    return why


def T84_restore_refuses_an_attest_nested_in_its_save(K, d):
    """ChatGPT, round 8, F3."""
    s, o = born(K, d)
    dwell(s, "formality", "hmm ok")
    real = K._durable_write
    fired, nested = [], []

    def write(path, text):
        if Path(path) == s._state_path() and not fired and '"restored"' in text:
            fired.append(True)
            nested.append(_record_outcome(lambda: o.attest(s)))
        return real(path, text)
    K._durable_write = write
    try:
        out = restore_ok(K, o, K.HumbleSeed(s.data_dir))
    finally:
        K._durable_write = real
    need(out.get("status") == "restored" and out.get("checkpoint_sequence") == 0, f"restore returned {out}")
    need(nested, "the nested attest did not happen as set up")
    why = judge_outcome(K, nested[0], K.ReentryRefused)
    need(saved_seq(s) == 0, f"saved checkpoint {saved_seq(s)}, expected 0")
    audit_ok(K, o, expect_loads(K, s.data_dir))
    need(witness_state(K, d, s) == (0, False),
         f"after the audit, witness (sequence, pending) = {witness_state(K, d, s)}, expected (0, False)")
    return why


def T85_interrupt_during_the_reread_still_leaves_the_object_unusable(K, d):
    """ChatGPT, round 8, F4: T73 with an interrupt in place of the re-read's OSError."""
    s, o = born(K, d)
    real_fsync, real_gen = K.os.fsync, s._saved_generation
    phase = {"fsync": False, "reread": False}

    def fsync(fd):
        if not phase["fsync"] and stat.S_ISDIR(os.fstat(fd).st_mode) and saved_seq(s) == 1:
            phase["fsync"] = True
            raise OSError("injected: directory fsync failed after the organism's replace")
        return real_fsync(fd)

    def gen():
        if phase["fsync"] and not phase["reread"]:
            phase["reread"] = True
            raise KeyboardInterrupt("injected: interrupt while re-reading the saved generation")
        return real_gen()
    K.os.fsync, s._saved_generation = fsync, gen
    try:
        o.attest(s)
    except KeyboardInterrupt:
        pass
    else:
        raise Fail("injected failure did not happen")
    finally:
        K.os.fsync = real_fsync
        del s._saved_generation
    need(phase["fsync"] and phase["reread"], f"injection points not both reached: {phase}")
    need(s.checkpoint.sequence == 1 and saved_seq(s) == 1,
         f"memory at checkpoint {s.checkpoint.sequence}, saved state at {saved_seq(s)}")
    why = expect_stale_reason(K, lambda: s.dwell_or_propose("formality", "evt", "hmm ok"), "unusable")
    f = expect_loads(K, s.data_dir)
    audit_ok(K, o, f)
    need(fresh_witness_seq(K, d, f) == 1, f"witness at {fresh_witness_seq(K, d, f)}, expected 1")
    return why


def T86_restore_keeps_the_owners_answers(K, d):
    """Author A1 (v0.8.7, sealed)."""
    s, o = born(K, d)
    y = propose(s, "verbosity")
    o.answer(s, y["proposal_id"], "no")
    apply_ok(K, s, o, propose(s, "formality", CASUAL), attest=False)
    out = restore_ok(K, o, s)
    need(out.get("status") == "restored" and out.get("checkpoint_sequence") == 0, f"restore returned {out}")
    need(out.get("owner_no_outstanding") == ["verbosity"],
         f"owner_no_outstanding = {out.get('owner_no_outstanding')!r}, expected ['verbosity']")
    trace = saved_state(s)["trace"]
    last, before = trace[-1], trace[-2]
    need(last.get("event") == "restored" and last.get("carried_owner_answers") == 1,
         f"last saved event {last.get('event')!r}, carried_owner_answers {last.get('carried_owner_answers')!r}")
    need(before.get("event") == "owner_answer" and before.get("proposal_id") == y["proposal_id"]
         and before.get("answer") == "no",
         f"the event before 'restored' is {before.get('event')!r} ({before.get('proposal_id')!r}, {before.get('answer')!r})")
    z = propose(s, "verbosity")
    o.answer(s, z["proposal_id"], "yes")
    apply_ok(K, s, o, z)                     # signs, applies and attests
    need(fresh_witness_seq(K, d, s) == 1, f"witness at {fresh_witness_seq(K, d, s)}, expected 1")
    audit_ok(K, o, expect_loads(K, s.data_dir))
    return f"restore reported {out['owner_no_outstanding']}; the 'no' was carried; a 'yes' to a new reading crossed"


def T87_owner_operation_inside_an_organism_operation_is_refused(K, d):
    """Author A2 (v0.8.7, sealed); ChatGPT, round 8, independently."""
    s, o = born(K, d)
    r = propose(s, "verbosity")
    sig = o.sign_proposal(r["payload_to_sign"])
    a_in, b_at_lock = threading.Event(), threading.Event()
    seen, outcome = [], {}
    real_lock = s._organism_lock

    def lock_hook():
        if threading.current_thread().name == "T87-B":
            b_at_lock.set()
        return real_lock()

    def reader(reading, terrain, events_since):
        if not seen:
            seen.append(True)
            a_in.set()
            outcome["b_seen"] = b_at_lock.wait(3)
            if outcome["b_seen"]:
                outcome["sign"] = _record_outcome(lambda: o.sign_proposal(r["payload_to_sign"]))
        return None
    s.reader = reader
    s._organism_lock = lock_hook
    b = None
    try:
        a = _start(lambda: s.authorize_and_apply(r["proposal_id"], sig), "T87-A")
        while not a_in.wait(0.05):
            if a["done"].is_set():
                break
        if "error" in a:
            raise a["error"]
        need(a_in.is_set(), "thread A finished without reaching its reader")
        b = _start(lambda: o.attest(s), "T87-B")
        deadline = time.time() + 5
        finished = (a["done"].wait(max(0.0, deadline - time.time()))
                    and b["done"].wait(max(0.0, deadline - time.time())))
    finally:
        del s._organism_lock
    need(finished, "a thread did not finish within 5 s (deadlock)")
    need(outcome.get("b_seen"), "thread B did not reach the organism lock inside attest within 3 s")
    why = judge_outcome(K, outcome["sign"], K.LockOrderRefused)
    for box in (a, b):
        if "error" in box:
            raise box["error"]
    need(a.get("result") is not None, "thread A's apply did not apply")
    need(b.get("result") is True, f"thread B's attest returned {b.get('result')!r}")
    need(fresh_witness_seq(K, d, s) == 1, f"witness at {fresh_witness_seq(K, d, s)}, expected 1")
    audit_ok(K, o, expect_loads(K, s.data_dir))
    return why


def T88_a_symlinked_path_shares_the_organism_lock(K, d):
    """Author A3 (v0.8.7, sealed)."""
    s, o = born(K, d)
    link = d / "org_link"
    os.symlink(s.data_dir, link)
    b = expect_loads(K, link)
    r = propose(s, "verbosity")
    sig = o.sign_proposal(r["payload_to_sign"])
    calls = []

    def reader(reading, terrain, events_since):
        if not calls:
            calls.append(b.dwell_or_propose("formality", "evt", "hmm ok")["status"])
        return None
    s.reader = reader
    a = _start(lambda: s.authorize_and_apply(r["proposal_id"], sig), "T88-A")
    need(a["done"].wait(5), "the apply did not finish within 5 s (deadlock)")
    why = judge_outcome(K, a, K.StaleOrganism, "stale organism object")
    need(calls == ["dwelling"], f"the reader's write did not happen as set up: {calls}")
    st = saved_state(s)
    ds = [e.get("category") for e in st["trace"] if e.get("event") == "dwelling"]
    need("formality" in ds and st["mutation_sequence"] == 0,
         f"saved dwellings {ds}, mutation_sequence {st['mutation_sequence']}")
    audit_ok(K, o, expect_loads(K, s.data_dir))
    return why


TESTS = TESTS + [T82_restore_resolves_a_failed_commit_followed_by_a_crossing,
                 T83_a_save_cannot_be_reentered_in_the_same_thread,
                 T84_restore_refuses_an_attest_nested_in_its_save,
                 T85_interrupt_during_the_reread_still_leaves_the_object_unusable,
                 T86_restore_keeps_the_owners_answers,
                 T87_owner_operation_inside_an_organism_operation_is_refused,
                 T88_a_symlinked_path_shares_the_organism_lock]
'''

once('''

def S1_two_threads_stress(K, d, seconds=3.0):''', NEW + '''

def S1_two_threads_stress(K, d, seconds=3.0):''')

out_path.write_text(src, encoding="utf-8")
print("written", out_path)
