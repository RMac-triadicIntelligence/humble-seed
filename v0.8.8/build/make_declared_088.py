#!/usr/bin/env python3
"""Writes and freezes DECLARED_v0_8_8.json. Run once, before the harness exists."""
import copy
import datetime
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(sys.argv[1]).resolve()
PREV = json.loads((HERE / "v0_8_7_record" / "DECLARED_v0_8_7.json").read_text(encoding="utf-8"))
CAND = HERE / "humble_seed_v0_8_8_candidate.py"
src = CAND.read_text(encoding="utf-8")
LINES = src.splitlines()
if (HERE / "falsify_v0_8_8.py").exists() or (HERE / "DECLARED_v0_8_8.json").exists():
    raise SystemExit("harness or declaration already exists; refusing to freeze")


def check(name, edits):
    mutated = src
    for old, new in edits:
        n = src.count(old)
        if n != 1:
            raise SystemExit(f"{name}: anchor occurs {n} times")
        mutated = mutated.replace(old, new)
    compile(mutated, name, "exec")          # construction check only: the mutant must compile


def _one(prefix, start=0):
    hits = [i + 1 for i, line in enumerate(LINES) if i >= start and line.startswith(prefix)]
    return hits


def ln(prefix):
    """The one line that starts with `prefix` (indentation included). A cited refusal is its raise line."""
    hits = _one(prefix)
    if len(hits) != 1:
        raise SystemExit(f"trace anchor {prefix!r} starts {len(hits)} lines")
    if prefix.lstrip().startswith("raise") and not LINES[hits[0] - 1].lstrip().startswith("raise"):
        raise SystemExit(f"trace anchor {prefix!r} is not a raise line")
    return f"L{hits[0]}"


def ln_after(anchor, prefix):
    """v0.8.8: the first line starting with `prefix` after the one line containing `anchor`
    (two raise lines may share their text, e.g. the currency check's and the save's)."""
    at = [i for i, line in enumerate(LINES) if anchor in line]
    if len(at) != 1:
        raise SystemExit(f"trace anchor {anchor!r} is on {len(at)} lines")
    hits = _one(prefix, at[0] + 1)
    if not hits:
        raise SystemExit(f"no {prefix!r} after {anchor!r}")
    return f"L{hits[0]}"


NEW_TESTS = [
    "T82_restore_resolves_a_failed_commit_followed_by_a_crossing",
    "T83_a_save_cannot_be_reentered_in_the_same_thread",
    "T84_restore_refuses_an_attest_nested_in_its_save",
    "T85_interrupt_during_the_reread_still_leaves_the_object_unusable",
    "T86_restore_keeps_the_owners_answers",
    "T87_owner_operation_inside_an_organism_operation_is_refused",
    "T88_a_symlinked_path_shares_the_organism_lock",
]
TEST_NAMES = list(PREV["tests"]) + NEW_TESTS
T = lambda *ns: [t for t in TEST_NAMES if t.split("_")[0] in ns]  # noqa: E731

M = {}
REANCHOR = {
    "XO1_save_skips_generation_check": [[
        "        if saved != self._generation:                    # [SAVE-CAS]\n", "        if False:\n"]],
    "XU1_unconfirmed_save_not_marked_unusable": [[
        "                self._generation = _UNUSABLE                 # [SAVE-INDETERMINATE]\n", "                pass\n"]],
    "XG1_landed_save_not_recorded": [[
        "                    self._generation = new_gen               # [SAVE-LANDED]\n", "                    pass\n"]],
    "XO4_organism_lock_is_a_no_op": [[
        '        return _OwnerLock(self.data_dir / "organism.lock", kind="organism")      # [ORGANISM-LOCK]\n',
        "        return contextlib.nullcontext()\n"]],
    "XT2_restore_skips_pending_recovery": [[
        "            self._recover(seed, oid, allow_prefix=True)  # [RESTORE-RECOVERS] v0.8.8: the prefix route (E1)\n",
        "            pass\n"]],
}
REANCHOR_NOTE = {
    "XO1_save_skips_generation_check": "v0.8.8: the save's body moved into _save_locked (one indent shallower); same mutation.",
    "XU1_unconfirmed_save_not_marked_unusable": "v0.8.8: _save_locked, one indent shallower; same mutation.",
    "XG1_landed_save_not_recorded": "v0.8.8: _save_locked; the landed branch is now the re-read's else clause; same mutation.",
    "XO4_organism_lock_is_a_no_op": "v0.8.8: the organism lock now names its kind; same mutation.",
    "XT2_restore_skips_pending_recovery": "v0.8.8: restore's recovery now allows the prefix route; same mutation.",
}
for name, spec in PREV["mutants"].items():
    spec = copy.deepcopy(spec)
    if name in REANCHOR:
        spec["edits"] = REANCHOR[name]
        spec["re_anchored"] = REANCHOR_NOTE[name]
    check(name, spec["edits"])
    spec["carried_from"] = spec.get("carried_from", "v0.8.7")
    M[name] = spec


def setk(name, tests, note=None):
    """v0.8.8 (v0.8.7 DEVIATIONS E1): the killer is set with the exact set, and stays inside it."""
    tests = sorted(tests)
    M[name]["exact_kill_set"] = tests
    if M[name].get("killer") not in tests:
        M[name]["killer"] = tests[0]
    if note:
        M[name]["note"] = note


setk("XO1_save_skips_generation_check", T("T76", "T88"),
     "v0.8.8: T88's write through the symlinked object lands during the operation, like T76's. Killer corrected "
     "to T76 (v0.8.7 DEVIATIONS E1: it named T62, outside its own exact set).")
setk("XO4_organism_lock_is_a_no_op", T("T69", "T70", "T71", "T72", "T87"),
     "v0.8.8: without the organism lock, thread A holds nothing in T87, so its owner call is not refused; it "
     "waits for B's attest and returns.")
setk("XQ2_operation_lock_not_taken", T("T72", "T87"),
     "v0.8.8: in T87 the reader then runs outside any organism lock, so its owner call is not refused.")
setk("XR1_recovery_never_completes", T("T54", "T58", "T64", "T65", "T73", "T81", "T82", "T85"),
     "v0.8.8: T82's restore must complete the pending commit by the prefix route; T85's audit, like T73's, "
     "must complete an installed intent.")
setk("XR3_no_write_ahead_intent", T("T54", "T58", "T63", "T64", "T65", "T66", "T73", "T81", "T82", "T85"),
     "v0.8.8: in T82 the injected commit failure is never reached (this mutant records instead), so the setup "
     "attest succeeds; in T85, as in T73, no intent exists and the audit meets an unwitnessed advance.")
setk("XC1_recovery_completes_without_verifying", T("T66", "T82"),
     "v0.8.8: in T82 attest then completes the pending commit from a saved state that does not verify, and "
     "signs off the later crossing; T82 requires attest and audit to refuse.")
setk("XT2_restore_skips_pending_recovery", T("T81", "T82"),
     "v0.8.8: in T82 the saved checkpoint is then not the witness head.")
setk("XR2_recovery_never_abandons", T("T55", "T57", "T66", "T84"),
     "v0.8.8: T84's fresh audit must abandon the intent left by the attest refused inside restore (R39).")
setk("XU1_unconfirmed_save_not_marked_unusable", T("T73", "T85"))
setk("XI1_install_rolls_back_even_when_saved", T("T65", "T73", "T85"),
     "v0.8.8: in T85, as in T73, the object is marked unusable and keeps the checkpoint on disk; this mutant "
     "rolls it back.")
setk("XU2_unusable_object_not_named", T("T73", "T85"), "T73 and T85 require the refusal to say 'unusable'.")
setk("XD2a_owner_answer_counted_as_authorizing", M["XD2a_owner_answer_counted_as_authorizing"]["exact_kill_set"] + T("T86"),
     "v0.8.8: T86 records an owner answer on the organism, so the next crossing's apply-time replay meets an "
     "'authorizing' answer.")
setk("XL6_answer_not_recorded_by_owner", T("T41", "T47", "T49", "T60", "T61", "T75", "T86"),
     "v0.8.8: T86's restore report comes from the owner's ledger.")
setk("XD2c_answer_is_a_permanent_event", T("T45", "T47", "T49", "T60", "T61", "T86"),
     "v0.8.8: in T86 the earlier 'no' to Y would hold Z at attestation despite the owner's 'yes' to Z.")
setk("XG1_landed_save_not_recorded", T("T65"))

mut_specs = [
    ("XE1_restore_has_no_prefix_route",
     [('                prefix_why = self._saved_prefix_refusal(seed, pending_cp, p["signature_b64"]) if allow_prefix else why  # [RECOVER-PREFIX]\n',
       "                prefix_why = why\n")],
     "Restore's recovery is as strict as attest's: a pending checkpoint whose saved state does not verify as a "
     "whole cannot be completed (v0.8.7 behaviour).", T("T82"), "ChatGPT round 8 F1"),
    ("XE2_save_reentry_allowed",
     [("    if key in saving:                                    # [SAVE-REENTRY]\n", "    if False:\n")],
     "A save may be re-entered in the same thread (v0.8.7 behaviour).", T("T83", "T84"),
     "ChatGPT round 8 F2, F3"),
    ("XE3_interrupt_in_reread_escapes",
     [("            except BaseException as why:                     # v0.8.8 (ChatGPT r8 F4): an interrupt too\n",
       "            except Exception as why:\n")],
     "Only an Exception in the re-read marks the object unusable; an interrupt escapes (v0.8.7 behaviour).",
     T("T85"), "ChatGPT round 8 F4"),
    ("XE4_restore_drops_owner_answers",
     [("            for e in carried:                                                                   # [RESTORE-ANSWERS] v0.8.8 (author A1)\n",
       "            for e in []:\n")],
     "Restore does not carry the owner's answers into the restored trace (v0.8.7 behaviour).", T("T86"),
     "author A1 (v0.8.7, sealed)"),
    ("XE5_restore_reports_nothing",
     [('            result["owner_no_outstanding"] = self._outstanding_no(seed)         # [RESTORE-REPORT] v0.8.8 (author A1)\n',
       '            result["owner_no_outstanding"] = []\n')],
     "Restore does not report the owner's outstanding 'no'.", T("T86"), "author A1 (v0.8.7, sealed)"),
    ("XE6_lock_order_unchecked",
     [('        if (self.kind == "owner" and getattr(_THREAD, "organism_held", 0) > 0    # [LOCK-ORDER]\n',
       "        if (False\n")],
     "An owner operation may be started while holding an organism lock (v0.8.7 behaviour): T87 deadlocks.",
     T("T87"), "author A2 (v0.8.7, sealed); ChatGPT round 8, independently"),
    ("XE7_lock_keyed_by_abspath",
     [("        self.path = os.path.realpath(str(path))          # [LOCK-KEY] v0.8.8 (author A3): one lock per real path\n",
       "        self.path = os.path.abspath(str(path))\n")],
     "Locks are keyed by the absolute path, not the real path (v0.8.7 behaviour): T88 deadlocks.", T("T88"),
     "author A3 (v0.8.7, sealed)"),
]
for name, edits, desc, exact, credit in mut_specs:
    check(name, edits)
    M[name] = {"expect": "KILLED", "mutation": desc, "edits": [[o, n] for o, n in edits], "new_in": "v0.8.8",
               "killer": sorted(exact)[0], "exact_kill_set": sorted(exact), "credit": credit}

bad = [n for n, m in M.items() if m["expect"] == "KILLED" and "exact_kill_set" in m
       and m.get("killer") not in m["exact_kill_set"]]
if bad:
    raise SystemExit(f"killer outside its exact kill set: {bad}")       # v0.8.7 DEVIATIONS E1

STALE_RAISE = '            raise StaleOrganism(f"stale organism object'
TRACE = {
    "T82_restore_resolves_a_failed_commit_followed_by_a_crossing": (
        f"attest -> organism lock -> _recover: the saved checkpoint is the pending one -> _saved_state_refusal -> "
        f"load -> verify: the category-sequence check raises IntegrityError "
        f"({ln('            raise IntegrityError(\"Category sequences do not match the attested checkpoint')}) -> "
        f"strict route (allow_prefix False) -> RollbackDetected 'claims it but does not verify' "
        f"({ln('                    raise RollbackDetected(\"A pending checkpoint commit cannot be completed')}). "
        f"audit: the same path and raise. restore -> _recover(allow_prefix=True) -> _saved_prefix_refusal returns "
        f"None -> the witness commits ({ln('            self.witness.commit(pending_cp)')}) -> _restore_attested "
        f"at checkpoint 1."),
    "T83_a_save_cannot_be_reentered_in_the_same_thread": (
        f"the live object's dwell -> _save -> organism lock -> _save_mark (marked) -> _save_locked -> "
        f"_durable_write (the test's wrapper) -> other.dwell_or_propose -> _organism_op (reentrant lock; other is "
        f"current) -> other's _save -> _save_mark raises ReentryRefused "
        f"({ln('        raise ReentryRefused(\"a save re-entered')}) before its checks or write."),
    "T84_restore_refuses_an_attest_nested_in_its_save": (
        f"restore -> _restore_attested -> r._save -> _save_mark (marked) -> _durable_write (the test's wrapper) -> "
        f"owner.attest: owner lock re-entered by the thread that holds it (LOCK-ORDER allows it), organism lock "
        f"reentrant, nothing pending, the live object current -> witness.begin -> install_checkpoint -> _save -> "
        f"_save_mark raises ReentryRefused ({ln('        raise ReentryRefused(\"a save re-entered')}) -> install "
        f"rolls back ({ln('                self.checkpoint, self.checkpoint_sig, n, self._trace_head = kept')}). The "
        f"fresh audit -> _recover: not installed; the saved checkpoint is the witness head -> abandon "
        f"({ln('            self.witness.abandon(oid)')})."),
    "T85_interrupt_during_the_reread_still_leaves_the_object_unusable": (
        f"attest -> install_checkpoint -> _save -> _save_locked -> _durable_write: the injected directory fsync "
        f"raises after os.replace ({ln('        os.fsync(dfd)')}) -> the re-read raises KeyboardInterrupt (injected) "
        f"-> object marked unusable ({ln('                self._generation = _UNUSABLE')}) -> the interrupt is "
        f"re-raised ({ln('                    raise                                    # the interrupt')}); install "
        f"does not roll back. The next dwell -> _organism_op -> _check_current raises StaleOrganism 'unusable' "
        f"({ln_after('# [UNUSABLE]', '            raise StaleOrganism(\"organism object is unusable')})."),
    "T87_owner_operation_inside_an_organism_operation_is_refused": (
        f"thread A: authorize_and_apply -> _organism_op (organism lock held) -> the reader -> owner.sign_proposal -> "
        f"_owner_locked -> _OwnerLock.__enter__: the thread holds an organism lock and the owner lock is held by "
        f"thread B -> LockOrderRefused ({ln('            raise LockOrderRefused(')})."),
    "T88_a_symlinked_path_shares_the_organism_lock": (
        f"the live object's apply -> _organism_op (lock keyed by the real path, {ln('        self.path = os.path.realpath(str(path))')}) "
        f"-> the reader -> b.dwell_or_propose: b's lock path resolves to the same key, so the RLock is reentrant "
        f"and no second flock is taken -> b saves -> the live object's _save -> _save_locked's generation check "
        f"raises StaleOrganism 'stale organism object' ({ln_after('[SAVE-CAS]', STALE_RAISE)})."),
}

C, O = "carried", "new"
TRACE_LINES = {"T57": "v0.8.6", "T62": "v0.8.6", "T63": "v0.8.6", "T64": "v0.8.6", "T65": "v0.8.6", "T66": "v0.8.6",
               "T67": "v0.8.6", "T68": "v0.8.6", "T73": "v0.8.7", "T74": "v0.8.7", "T75": "v0.8.7", "T76": "v0.8.7",
               "T77": "v0.8.7", "T78": "v0.8.7", "T79": "v0.8.7", "T80": "v0.8.7"}
tests = {}
for name, spec in PREV["tests"].items():
    spec = copy.deepcopy(spec)
    spec["status"] = C
    if "refusal_trace" in spec:
        spec["refusal_trace_lines"] = TRACE_LINES[name.split("_")[0]] + " candidate"
    tests[name] = spec
assert all(("refusal_trace" in s) == ("refusal_trace_lines" in s) for s in tests.values())

NESTED = ("The nested call's outcome is recorded and judged by type: the expected refusal passes; a return, or "
          "another of the system's declared refusal types, is a FAIL; any other exception is re-raised unchanged "
          "(an ERROR).")
THREADED = ("Exceptions raised in the threads are re-raised unchanged (an ERROR), after the finish and outcome "
            "checks.")
NEW = {
    "T82_restore_resolves_a_failed_commit_followed_by_a_crossing": ("ChatGPT round 8 F1",
        "Genesis attested. A verbosity crossing is applied, unattested; the object's verbosity (v1) is noted. attest "
        "is interrupted (OSError injected at witness.commit) after the organism installed checkpoint 1: the witness "
        "is at 0 with an intent pending and the saved checkpoint is 1. A formality crossing (CASUAL) is then applied "
        "on the same object, unattested. owner.attest(live object) and owner.audit(live object) each raise "
        "RollbackDetected containing 'claims it but does not verify'. owner.restore(live object), through restore_ok, "
        "returns status 'restored' with checkpoint_sequence 1. The witness is at 1 with no intent pending. The object "
        "is at checkpoint 1 with verbosity v1, formality at its genesis value and mutation_sequence 1. A fresh load "
        "audits."),
    "T83_a_save_cannot_be_reentered_in_the_same_thread": ("ChatGPT round 8 F2",
        "Genesis attested; `other` is loaded (current). K._durable_write is replaced by a wrapper that, on its first "
        "write of the state file, calls other.dwell_or_propose('curiosity', 'evt', 'hmm ok'), records the outcome, "
        "and then performs the write. The live object dwells (formality, 'hmm ok') and returns 'dwelling'. The "
        "recorded outcome is ReentryRefused. The saved generation is one above its value before the dwell; the saved "
        "trace holds the formality dwelling and no curiosity dwelling; a fresh load audits. " + NESTED),
    "T84_restore_refuses_an_attest_nested_in_its_save": ("ChatGPT round 8 F3",
        "Genesis attested; the live object dwells (formality, 'hmm ok'). K._durable_write is replaced by a wrapper "
        "that, on its first write of the state file whose text contains '\"restored\"', calls owner.attest(live "
        "object), records the outcome, and then performs the write. owner.restore(a new, unloaded HumbleSeed for the "
        "same directory), through restore_ok, returns status 'restored' with checkpoint_sequence 0. The recorded "
        "outcome is ReentryRefused. The saved checkpoint is 0. A fresh load audits; the witness is then at 0 with no "
        "intent pending. " + NESTED),
    "T85_interrupt_during_the_reread_still_leaves_the_object_unusable": ("ChatGPT round 8 F4",
        "As T73, with a KeyboardInterrupt in place of the re-read's OSError. Genesis attested. During attest, after "
        "the organism's replace has landed (saved checkpoint 1), the directory fsync raises OSError (once) and the "
        "re-read of the saved generation then raises KeyboardInterrupt (once). attest raises KeyboardInterrupt, which "
        "the test catches (if attest returns: FAIL, 'injected failure did not happen'; any other exception propagates "
        "unchanged). The object's checkpoint sequence equals the saved one, 1. The next dwell on the "
        "object raises StaleOrganism containing 'unusable'. A fresh load audits (completing the pending intent), and "
        "the witness is then at 1."),
    "T86_restore_keeps_the_owners_answers": ("author A1 (v0.8.7, sealed)",
        "Genesis attested. A verbosity reading Y is issued; owner.answer(live object, Y, 'no'). A formality crossing "
        "(CASUAL) is applied, unattested. owner.restore(live object), through restore_ok, returns status 'restored', "
        "checkpoint_sequence 0 and owner_no_outstanding == ['verbosity']. The saved trace ends with the 'restored' "
        "event, whose carried_owner_answers is 1, immediately preceded by an owner_answer event for Y with answer "
        "'no'. A new verbosity reading Z is issued on the restored object; owner.answer(Z, 'yes'); Z is signed and "
        "applied (apply_ok); attest succeeds; the witness is at 1; a fresh load audits."),
    "T87_owner_operation_inside_an_organism_operation_is_refused": ("author A2 (v0.8.7, sealed); ChatGPT round 8",
        "Genesis attested. A verbosity reading is issued and signed. The live object's _organism_lock is wrapped on "
        "the instance so that a call from thread B sets an event. Its reader is replaced by one that, on its first "
        "call: waits up to 3 s for that event (B is then inside owner.attest, holding the owner lock, at the organism "
        "lock); calls owner.sign_proposal on the same reading's payload and records the outcome; returns None. "
        "Thread A runs authorize_and_apply on the live object; once A is inside its reader, thread B runs "
        "owner.attest(live object). Both threads must finish within 5 s (FAIL otherwise: a deadlock). B's event must "
        "have been seen (FAIL otherwise). The recorded outcome is LockOrderRefused. A's apply returns non-None; B's "
        "attest returns True; the witness is at 1; a fresh load audits. " + NESTED + " " + THREADED),
    "T88_a_symlinked_path_shares_the_organism_lock": ("author A3 (v0.8.7, sealed)",
        "Genesis attested. A symlink to the organism's directory is made; `b` is loaded through it (current). A "
        "verbosity reading is issued on the live object and signed. The live object's reader is replaced by one "
        "that, on its first call, has `b` dwell (formality, 'hmm ok') and returns None. authorize_and_apply on the "
        "live object runs in a thread and must finish within 5 s (FAIL otherwise: a deadlock), raising StaleOrganism "
        "containing 'stale organism object' (a return or another declared refusal type is a FAIL; any other exception "
        "is re-raised). The reader's dwell returned 'dwelling'. The saved file (read directly) holds b's formality "
        "dwelling and mutation_sequence 0; a fresh load audits."),
}
for name, (credit, asserts) in NEW.items():
    spec = {"expect": "PASS", "status": O, "asserts": asserts, "credit": credit}
    tests[name] = spec
for name, trace in TRACE.items():
    tests[name]["refusal_trace"] = trace
    tests[name]["refusal_trace_lines"] = "v0.8.8 candidate"
assert list(tests) == TEST_NAMES

rules = []
for r in PREV["rules"]:
    r = r.replace("differs from DECLARED_v0_8_7.sha256", "differs from DECLARED_v0_8_8.sha256")
    r = r.replace("applied as exact-once anchors on v0.8.7 (build_mutant",
                  "applied as exact-once anchors on v0.8.8 (build_mutant")
    rules.append(r)
assert not any("v0_8_7.sha256" in r or "anchors on v0.8.7" in r for r in rules), rules
rules += [
    "v0.8.8 (v0.8.7 DEVIATIONS E1): a KILLED mutant's killer is inside its exact kill set; the freeze refuses "
    "otherwise. Re-predicted sets set the killer with the set.",
    "v0.8.8: each refusal_trace names, in refusal_trace_lines, the candidate whose line numbers it cites. Carried "
    "traces keep their text; the post-run refusal-trace check reports the raise lines measured on v0.8.8.",
    "v0.8.8: tests that record the outcome of a nested call (T83, T84, T87) judge it by type: the expected refusal "
    "passes; a return or another declared refusal type is a FAIL; any other exception is re-raised (an ERROR). The "
    "declared refusal types are StaleOrganism, ReentryRefused, LockOrderRefused, RollbackDetected, IntegrityError, "
    "AttestationRefused and ValueError.",
    "v0.8.8: T87 and T88 run the operation under test in threads with a 5 s limit; a thread that does not finish is "
    "a FAIL (a deadlock is the failure they test for). A thread left blocked by a mutant stays blocked for the rest "
    "of that mutant's run; it holds only locks on its own test's temporary paths.",
]

prefreeze = HERE / "dev_prefreeze"
decl = {
    "artifact": "humble_seed_v0_8_8_candidate falsification harness",
    "date": "2026-10-19",
    "authorship": PREV["authorship"].replace("round 7 F1-F3)", "round 7 F1-F3; round 8 F1-F4)").replace(
        "v0.8.6 A1-A3)", "v0.8.6 A1-A3; v0.8.7 A1-A3)").replace(
        " v0.8.7 built at Rusty's ruling, 2026-10-19 11:09 CT ('Build it into 8.7. Restore from last signed off state').", "")
    + " v0.8.8 built at Rusty's 'Go. Make this the final revision before publishing this current works progress.' "
      "(2026-10-19).",
    "candidate_sha256_at_freeze": hashlib.sha256(CAND.read_bytes()).hexdigest(),
    "frozen_before": ("the v0.8.8 harness was written. Before the freeze, on this candidate: a compile check; the v0.8.7 "
                      "suite (T1-T81) and its S1, run through a development runner as a regression check (81 PASS, S1 "
                      "PASS; dev_prefreeze/PREFREEZE_v0_8_7_suite_on_v0_8_8.txt); the round-8 author reproduction "
                      "(author_repro_round8.py: F1-F4 and Grok's G1; dev_prefreeze/PREFREEZE_round8_repro_on_v0_8_8.json), "
                      "which showed F1 restored at checkpoint 1, F2 and F3's nested saves refused with ReentryRefused, "
                      "F4's object unusable after the interrupt; an exact-once check of every mutant anchor; and the "
                      "static refusal traces (the generator was dry-run once in a scratch copy to check them; that draft "
                      "declaration was deleted). Both development runs were made twice: once on a build that differed "
                      "from this candidate only in its module docstring, and once on this candidate. No v0.8.8 test "
                      "(T82-T88), lock-order or symlink schedule, answer-carrying restore, or mutant had been run."),
    "status_key": {"carried": "Passed on v0.8.7; passed once on v0.8.8 in the pre-freeze regression run; predicted on v0.8.8.",
                   "new": "Not run on any version when this file was frozen. T82-T85 test the scenarios of the round-8 "
                          "reproduction; the tests themselves had not been run."},
    "rules": rules,
    "controls_without_a_mutant": PREV["controls_without_a_mutant"] + [
        "_saved_prefix_refusal's individual checks (owner key, checkpoint signature, prefix chain and head, replay, "
        "roots, mutation_sequence): no test presents an installed pending checkpoint whose prefix fails one; XE1 "
        "removes the route as a whole.",
        "_outstanding_no's window start (the ledger seq of the owner's signature of the last attested crossing in the "
        "category): T86's category has no attested crossing.",
        "LOCK-ORDER's exemption for a thread that already holds the owner lock: exercised by every attest, answer and "
        "restore (their ledger and witness calls re-enter the owner lock inside the organism lock) and by T84; "
        "removing it would refuse nearly every test, so no mutant.",
        "The interrupt's re-raise in the save's re-read: T85 requires attest to raise KeyboardInterrupt; no mutant "
        "swallows it.",
        "The save mark's key by real path: T83 and T84 use one path; no separate mutant.",
    ],
    "candidate_only_checks": PREV["candidate_only_checks"],
    "retired": PREV["retired"],
    "tests": tests,
    "mutants": M,
}
for f in ("PREFREEZE_v0_8_7_suite_on_v0_8_8.txt", "PREFREEZE_round8_repro_on_v0_8_8.json"):
    if not (prefreeze / f).exists():
        raise SystemExit(f"missing pre-freeze record {f}")
out = HERE / "DECLARED_v0_8_8.json"
out.write_text(json.dumps(decl, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
sha = hashlib.sha256(out.read_bytes()).hexdigest()
(HERE / "DECLARED_v0_8_8.sha256").write_text(f"{sha}  DECLARED_v0_8_8.json\n")
(HERE / "CANDIDATE_v0_8_8_AT_FREEZE.sha256").write_text(
    f"{decl['candidate_sha256_at_freeze']}  humble_seed_v0_8_8_candidate.py\n")
stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
(HERE / "DECLARED_v0_8_8.frozen_at").write_text(stamp + "\n")
print(len(tests), "tests;", len(M), "mutants; declared", sha, "frozen", stamp)
for k, v in TRACE.items():
    print(" ", k.split("_")[0], "->", v[:200])
