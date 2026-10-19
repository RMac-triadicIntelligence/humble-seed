# Humble Seed v0.8.5 — independent blind review

2026-10-19. Work restricted to the supplied archive. No other reviews or external sources were retrieved. The included v0.8.4 source was inspected as part of this pack. The candidate and declaration remain unchanged. Sealed commitments were retained; salts and sealed findings were not available, so their contents and chronology were not independently verified.

## Assessment

The frozen battery returns exit **1**, with **60/61 candidate tests passing** and **four declared mismatches**. T57 is the only failing candidate test. Its expected error is wrong: the owner refuses the unattested state on checkpoint category sequences before reaching the unattested-tail check. This is a harness expectation defect, not evidence that checkpoint rollback failed.

The independent work found an additional persistence problem: a stale organism object can overwrite a newer saved checkpoint through an ordinary public operation. The external witness detects the resulting rollback, but the latest signed-off state has already been overwritten. An interleaving during sign-off can even make `attest` return True while the saved organism is behind the witness. This deserves repair before treating the candidate as robust across multiple organism sessions.

A second, narrower failure boundary is a directory-fsync error after replacement. Memory is rolled back while the new checkpoint is already visible on disk. Recovery correctly completes from disk, but retrying with the original object fails until it is reloaded. This is a recoverable partial-write outcome, not a demonstrated authorization bypass or a proof of actual power-loss durability.

Within the explicit veto, expiration, foreign-signature, history-rewrite and replay-input cases exercised below, the owner refused the prohibited result. These observations are bounded to the runnable cases; they do not establish universal safety, life, intelligence or emergence.

## Exact frozen execution

- Command: `python3 -I falsify_v0_8_5.py`
- Python: `3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]`
- cryptography: `50.0.2`
- Platform: `Linux-6.18.55-x86_64-with-glibc2.39`
- Exit code: `1`
- Elapsed: `62.528` seconds
- Candidate SHA-256: `e505d432db249276a7caea7f84ba97ca0d9bb3daab7fbbe8db6416b42071ddfe`
- Declaration SHA-256: `ddd6fbd20585974c1f04301d0daafd4fc4f1d91f64088d593bca918724946e14`
- Original ZIP SHA-256: `9f317d6fb0ec03025525439cbd97de09207338d768ebc1c32083b88bb9cae593`
- All 11 manifest entries and the two separate candidate/declaration hash checks matched. This establishes internal byte consistency, not independent proof of when a preregistration was frozen.

Verbatim final receipt:

```text
receipt (statuses only, run-independent): 22d9e8eb964fdf7860e8c6f909bc9cd78c5b3d178105bf8e2a675fe7ce35ad36
```

Frozen candidate results: 60 PASS, 1 FAIL, 0 ERROR. Frozen mutants: 58 KILLED, 2 SURVIVES (null copy and XR4), 1 CRASHED (the intentionally crashing XH). Mutants with errors retain their error lists in the results JSON; crashes are never counted as kills. In particular XL7 is killed by failing tests and also has three newly erroring tests.

## Every mismatch and its diagnosis

| Frozen row | Declared | Measured | Diagnosis |
|---|---|---|---|
| T57_failed_checkpoint_save_changes_nothing | PASS | FAIL | Actual refusal: `IntegrityError: Category sequences do not match the attested checkpoint`. Apply already advanced category sequences, while the failed checkpoint save leaves checkpoint 0 installed. `_verify_attestation` checks gates before the unattested tail. T57 expects `Unattested authorizing event`, so it stops before its later recovery/retry assertions. |
| X10_unattested_tail_check_removed | KILLED, exact T22 + T57 | KILLED by T22 only | T57 does not pass on the frozen candidate, so it cannot contribute a new failure. More importantly, even after correcting T57, gates still refuse first; removing the tail check does not make T57 fail. Its declared exact kill set remains wrong. T22 is the actual tail-check probe. |
| XR2_recovery_never_abandons | KILLED, exact T55 + T57 | KILLED by T55 only | T57's baseline failure excludes it from the original passing set. After the narrow expectation correction, T57 passes the candidate and fails XR2 at recovery, restoring this declared kill set. |
| XR4_install_keeps_memory_on_failed_save | KILLED by T57 | SURVIVES | Its only declared detector, T57, is already nonpassing on the candidate and is excluded. After correcting the expectation, T57 passes the candidate and fails this mutant because memory is at 1 while disk remains 0. The diagnostic shows a missing effective test result in the frozen run, not a surviving exploit in the candidate. |

The exact lines are reproduced in the full frozen stdout appendix. No mismatch was suppressed or reclassified in the original results.

## Separate diagnostic, not a replacement receipt

`independent/falsify_diagnostic.py` changes only T57's expected refusal substring to the actual earlier guard. It uses the original candidate and original frozen declaration. It writes a separate result file.

The diagnostic executes the full battery again: **61/61 PASS**, **59 mutants KILLED**, null copy SURVIVES, intentional XH CRASHED. Exit **1** with **1 mismatch**, X10's incorrect exact kill set. Its measured set is T22 alone. T57 should not be added to X10's expected killers.

Diagnostic receipt, explicitly not the frozen receipt:

```text
receipt (statuses only, run-independent): e72f4c9a27b69e0532a104d6f2646c461e97026d98060ef47eea29ba5d02ba47
```

The targeted corrected-T57 experiment additionally demonstrates that XR5 (recovery trusts object) is not detected by T57 when memory and disk agree; T58 remains the detector for that control.

## F1 — stale public writes can erase newer saved state

Priority: high for persistence and availability. No owner-file editing, private-key access, candidate mutation, clock manipulation or concurrent thread is required for the basic reproduction.

Procedure in `stale_public_write`:

1. Hatch and attest checkpoint 0; load a second organism object from that same path.
2. On the first object, sign, apply and attest a verbosity change: saved checkpoint 1, verbosity 0.25, witness 1.
3. On the older object, call `dwell_or_propose` with ordinary non-proposing text. Its `_save` unconditionally writes its entire stale snapshot.
4. A fresh load now reads checkpoint 0 and verbosity 0.50. Local verification succeeds, but owner audit reports rollback and owner attestation reports a non-successor checkpoint.

Selected actual output:

```json
{
  "after": {
    "saved_sequence": 0,
    "verbosity": 0.5,
    "witness_sequence": 1
  },
  "before": {
    "saved_sequence": 1,
    "verbosity": 0.25,
    "witness_sequence": 1
  },
  "fresh_attest": {
    "exception": "RollbackDetected",
    "message": "Non-successor checkpoint: organism presents sequence 1, expected 2"
  },
  "fresh_audit": {
    "exception": "RollbackDetected",
    "message": "Rollback: organism presents sequence 0, witness holds 1"
  },
  "latest_object_retained_can_repair": {
    "returned": true
  },
  "ordinary_response": "dwelling"
}
```

Root cause: `HumbleSeed._save` has no disk-generation comparison or organism write lock. The owner lock serializes owner operations; ordinary organism operations do not participate. Reading the saved checkpoint during recovery fixes the trust source for an intent, but it does not prevent stale writes to that source.

Two related schedules were also executed:

- `advanced_memory_save_during_attest` inserts that same ordinary public write after the current object's checkpoint install and before witness commit. It uses a deterministic hook at the commit boundary to model scheduling, without changing the commit logic. Attest returns True; disk is at 0 and witness at 1; fresh audit refuses.
- `interrupted_commit_stale_write` interrupts witness commit after checkpoint 1 is saved. A stale ordinary write then puts checkpoint 0 back. Recovery sees the witness head on disk, abandons the intent and accepts the old state. Audit returns True at checkpoint 0; the saved signed-off character change is lost. The witness has not finalized checkpoint 1 in this schedule, so this is loss of a saved approved intent, not acceptance of a fabricated mutation.

The outputs for both schedules are in the independent appendix. The sequential reproduction is sufficient to establish the stale-write defect; the hook is only evidence for the specified interleaving, not a broad concurrency stress test.

Impact: a detected rollback can still destroy availability. If the newer in-memory object or a valid snapshot is retained, this experiment can restore progress by attesting it; the code does not reconstruct that overwritten state from its retained witness metadata alone. Do not call this cryptographic forgery, a key bypass, or unconditional permanent loss.

Suggested repair: define and enforce one organism persistence protocol across every writer. Compare the expected saved revision under a shared lock before replacing, and reject or explicitly reconcile stale objects. Coordinate checkpoint install/witness commit with the same protocol. Simply reloading immediately before an unlocked save does not close the race. If multiple organism sessions are intentionally unsupported, enforce that constraint rather than silently accepting stale saves.

## F2 — failure after replacement leaves memory behind disk

Priority: medium for recovery ergonomics; bounded error-injection observation.

`post_replace_fsync_failure` patches only `os.fsync` to raise on the directory descriptor after the new organism checkpoint has already been replaced into its state path. It does not patch replay, signatures, witness logic or `_save`. Before-replacement failures are covered separately by corrected T57.

Actual output:

```json
{
  "after_failure": {
    "memory_sequence": 0,
    "saved_sequence": 1,
    "witness_sequence": 0
  },
  "after_retry": {
    "memory_sequence": 0,
    "saved_sequence": 1,
    "witness_sequence": 1
  },
  "fault_reached": [
    "organism replacement visible before directory fsync"
  ],
  "first_attest": {
    "exception": "OSError",
    "message": "injected directory fsync failure AFTER organism os.replace"
  },
  "reloaded_attest": {
    "returned": true
  },
  "reloaded_audit": {
    "returned": true
  },
  "same_object_retry": {
    "exception": "RollbackDetected",
    "message": "Non-successor checkpoint: organism presents sequence 1, expected 2"
  }
}
```

`install_checkpoint` restores checkpoint 0 in RAM on any save exception, although this exception occurs after checkpoint 1 becomes visible on disk. The next attest recovers the approved saved checkpoint to witness 1, then builds a successor from the stale object at 0 and refuses it. Reloading the saved checkpoint succeeds and allows further attestation. The approved intent recovery works; the stale caller is not reconciled.

Suggested repair: represent the post-replacement outcome explicitly. After an indeterminate save, resolve from the saved generation and either synchronize the object or require a reload before further writes. Exercise failures before replacement, after replacement, and on witness persistence. This probe does not establish what survives an actual power loss.

## Executed authority and liveness controls

Each claim here has runnable code and actual output in `independent/review_probes.py` and `evidence/independent_results.json`. Some controls deliberately rerun named shipped tests so their evidence can be compared directly.

| Case exercised | Measured behavior |
|---|---|
| Normal four-crossing session across three categories | All four applied and attested; reload/audit succeeded; mutation sequence 4. |
| Different owner's key at verify_consequence | Refused: organism is not keyed to this owner. This isolates the key guard; it does not exercise a different witness's enrollment guard. |
| Rewritten already-attested history, rehashed chain | Refused: attested history was rewritten. |
| Owner's recorded no; reader disabled | Attestation refused (T41). |
| Forged yes only on organism after genuine owner no | Attestation refused (T47). |
| Expired on owner's clock; re-sign from stale owner session | Attestation refused (T42, T53). |
| Organism recorded expiry, then its clock was wound back | Attestation refused (T43). |
| Signature made outside owner tool, even with correct key | Attestation refused (T46). |
| Saved installed intent, stale object handed to audit | Recovery completes from disk; stale object is refused; fresh object audits and advances (T58). |
| Invalid annotation and clock before issuance | Apply refuses before crossing; valid 2000-character annotation applies and attests (T59). |
| Category no before signing, first and later crossings | Authoritative attestation refused despite organism-only forged yes (T60, T61). |
| Genuine no before a fresh reading is issued, then genuine yes on the original pending reading | Fresh reading applies but initially cannot attest; genuine owner correction releases the veto and reload/audit succeeds (`window_orderings`). This records the intentionally wider owner window, not a bypass. |
| Pending recovery with unreadable state; with unrelated saved checkpoint | Both refuse as RollbackDetected (`pending_recovery_refusals`). |

Apply/replay equality covers the new mutation record, not the owner's separate ledger, expiry and answer checks. Existing T41–T48 intentionally demonstrate that apply can occur before owner attestation refuses it. These are established architectural boundaries, not additional new findings here. No new bypass of those owner checks was demonstrated in the enumerated cases.

## Test validity and scope

The material testing issue is T57's unreachable expected refusal. It also hid XR4's removal of the in-memory rollback and overstated X10 coverage. The full diagnostic and the targeted mutant runs expose this explicitly. Other refusal-message-sensitive kills remain mechanism checks; for example XP1 is accurately renamed and documented as a changed refusal mechanism, while XP1b removes both the finite and window checks. A KILLED label alone should not be read as proof that an unsafe mutation was accepted by the mutant.

The reviewer initially tried to isolate the foreign-key check through a different owner's attest call. That call was stopped earlier by its unrelated witness enrollment rules. The probe setup was corrected to call verify_consequence directly; both the initial failed reviewer assertion and final output are retained. No candidate behavior was modified for that correction.

This review did not build a repair or edit the candidate. The main recommended next work is the shared organism persistence boundary, plus correcting T57 and X10's declared exact kill set. Retain the repaired veto and replay controls while doing so.

## Evidence index

- `input/Claudehumble_seed_v0_8_5_candidate_BLIND.zip`: original input bytes.
- `humble_seed_v0_8_5_candidate_BLIND/`: supplied source, declaration, commitments and unchanged original frozen RESULTS file generated here.
- `evidence/baseline.stdout.txt`, `.stderr.txt`, `baseline_run.json`: exact frozen execution.
- `evidence/environment_integrity.json`: versions, platform, input and manifest hashes.
- `independent/review_probes.py`: reproducible attacks, recovery probes and controls.
- `evidence/independent_results.json`, `independent.stdout.txt`, `independent.stderr.txt`: final independent results.
- `evidence/independent_initial*`: initial reviewer probe setup error, retained transparently.
- `evidence/probes/`: organism, ledger and witness states, plus the before/after stale-write snapshots. Corrected-T57 mutants generated from declaration are retained there. Test keys were ephemeral and not saved.
- `independent/falsify_diagnostic.py`, `evidence/diagnostic*`, `evidence/DIAGNOSTIC_RESULTS_v0_8_5.json`: separately labeled full diagnostic run.
- `independent/build_report.py`: builds this report from saved results.
- `SHA256SUMS`: archive inventory with hashes, excluding itself.

## Appendix A — full frozen tables and verbatim stdout

```text
==============================================================================
Humble Seed v0.8.5 CANDIDATE — falsification harness
declared ddd6fbd20585974c… frozen 2026-10-19T12:27:12Z
candidate e505d432db249276…  parent v0.7 08a756043a6500fc…
==============================================================================

TEST                                             DECLARED  MEASURED  VERDICT
T1_liveness_intervening_events                   PASS      PASS      MATCH
T2_liveness_cross_category                       PASS      PASS      MATCH
T3_stale_same_category                           PASS      PASS      MATCH
T4_second_crossing_at_clamp_floor                PASS      PASS      MATCH
T5_payload_carries_no_destination_information    PASS      PASS      MATCH
T6_rule_comes_from_constitution                  PASS      PASS      MATCH
T7_constitution_pinned_at_apply                  PASS      PASS      MATCH
T8_distribution_bound                            PASS      PASS      MATCH
T9_evidence_bound                                PASS      PASS      MATCH
T10_replay                                       PASS      PASS      MATCH
T11_expiry                                       PASS      PASS      MATCH
T12_wrong_key                                    PASS      PASS      MATCH
T13_forged_first_commit                          PASS      PASS      MATCH
T14_forged_character_resealed                    PASS      PASS      MATCH
T15_category_sequences_resealed                  PASS      PASS      MATCH
T16_permissive_rule_full_birth_repair            PASS      PASS      MATCH
T17_unattested_apply_fails_closed                PASS      PASS      MATCH
T18_rollback_witness_only                        PASS      PASS      MATCH
T19_identity_replacement_audit                   PASS      PASS      MATCH
T20_realistic_session                            PASS      PASS      MATCH
T21_prior_value_detects_independent_change       PASS      PASS      MATCH
T22_unattested_tail_check_reachable              PASS      PASS      MATCH
T23_tamper_evidence_preserved                    PASS      PASS      MATCH
T24_nonfinite_reading_refused                    PASS      PASS      MATCH
T25_clamp_comes_from_constitution                PASS      PASS      MATCH
T26_attest_refuses_unsigned_change               PASS      PASS      MATCH
T27_checkpoint_built_at_signing_time             PASS      PASS      MATCH
T28_reading_survives_a_day                       PASS      PASS      MATCH
T29_allowed_fields_come_from_constitution        PASS      PASS      MATCH
T30_D1_owner_no_holds                            PASS      PASS      MATCH
T31_D1_hold_never_crosses_or_reproposes          PASS      PASS      MATCH
T32_D1_reader_failure_holds                      PASS      PASS      MATCH
T33_D1_reader_cannot_alter_reading               PASS      PASS      MATCH
T34_D1_unrelated_answers_do_not_hold             PASS      PASS      MATCH
T35_D2_answer_is_evidence_not_authority          PASS      PASS      MATCH
T36_D2_prompts_separate_and_deterministic        PASS      PASS      MATCH
T37_D3_nothing_before_signing_depends_on_rule    PASS      PASS      MATCH
T38_D3_consequence_rendered_from_record          PASS      PASS      MATCH
T39_D4_attest_refuses_forged_reading             PASS      PASS      MATCH
T40_nonfinite_never_parsed_or_written            PASS      PASS      MATCH
T41_owner_ledger_refuses_held_crossing           PASS      PASS      MATCH
T42_owner_clock_lifetime                         PASS      PASS      MATCH
T43_organism_expiry_record_honored               PASS      PASS      MATCH
T44_replay_checks_every_record_field             PASS      PASS      MATCH
T45_D2_corrected_answer_releases_hold            PASS      PASS      MATCH
T46_reading_must_be_signed_through_owner_tool    PASS      PASS      MATCH
T47_forged_yes_does_not_reach_attestation        PASS      PASS      MATCH
T48_organism_recorded_no_honored                 PASS      PASS      MATCH
T49_stale_session_cannot_bypass_owner_no         PASS      PASS      MATCH
T50_stale_session_keeps_other_sessions_records   PASS      PASS      MATCH
T51_stale_witness_cannot_fork                    PASS      PASS      MATCH
T52_record_metadata_validated                    PASS      PASS      MATCH
T53_lifetime_runs_from_first_signing             PASS      PASS      MATCH
T54_commit_recovers_after_organism_install       PASS      PASS      MATCH
T55_commit_recovers_before_organism_install      PASS      PASS      MATCH
T56_owner_lock_excludes_other_processes          PASS      PASS      MATCH
T57_failed_checkpoint_save_changes_nothing       PASS      FAIL      MISMATCH
    -> audit after the failed save: IntegrityError: Category sequences do not match the attested checkpoint
T58_stale_object_cannot_abandon_an_installed_intent PASS      PASS      MATCH
T59_apply_refuses_what_replay_would_refuse       PASS      PASS      MATCH
T60_owner_no_before_signing_holds_first_crossing PASS      PASS      MATCH
T61_owner_no_before_signing_holds_later_crossing PASS      PASS      MATCH

MUTANT                                       DECLARED  MEASURED  VERDICT   killed by (crashed)
X0_NULL_identical_copy                       SURVIVES  SURVIVES  MATCH     -
X1_K1_trace_head_staleness_restored          KILLED    KILLED    MATCH     T1, T20, T28, T2, T30, T31, T32, T34, T35, T41, T43, T45, T47, T48, T49, T50, T59, T60, T61
X2_K1_global_sequence_staleness_restored     KILLED    KILLED    MATCH     T20, T28, T2
X3_K1_category_sequence_check_removed        KILLED    KILLED    MATCH     T20, T28, T3, T4
X4_K1_prior_value_check_removed              KILLED    KILLED    MATCH     T21
X5_K2_destination_back_in_payload            KILLED    KILLED    MATCH     T5
X5b_K2_destination_alias_in_payload          KILLED    KILLED    MATCH     T5
X5c_K2_destination_digest_in_payload         KILLED    KILLED    MATCH     T5
X6_K2_rule_read_from_module_constant         KILLED    KILLED    MATCH     T6
X7_K2_constitution_pin_removed               KILLED    KILLED    MATCH     T7
X8_K2_distribution_root_not_rehashed         KILLED    KILLED    MATCH     T8
X9_C5_unknown_organism_audit_returns         KILLED    KILLED    MATCH     T19
X10_unattested_tail_check_removed            KILLED    KILLED    MISMATCH  T22
    declared exact ['T22_unattested_tail_check_reachable', 'T57_failed_checkpoint_save_changes_nothing']
    measured       ['T22_unattested_tail_check_reachable']
XF1a_validator_accepts_nonfinite             KILLED    KILLED    MATCH     T24
XF1b_strict_parse_removed                    KILLED    KILLED    MATCH     T40
XF1c_canonical_json_allows_nan               KILLED    KILLED    MATCH     T40
XF2a_clamp_read_from_module_constant         KILLED    KILLED    MATCH     T25
XF2b_fields_read_from_module_constant        KILLED    KILLED    MATCH     T29
XF2c_ttl_read_from_module_constant           KILLED    KILLED    MATCH     T28, T53
XD1a_hold_ignored                            KILLED    KILLED    MATCH     T30, T31, T32, T41, T45, T48
XD1b_reader_failure_fails_open               KILLED    KILLED    MATCH     T32
XD1c_hold_reproposes                         KILLED    KILLED    MATCH     T30, T31
XD1d_reader_gets_live_reading                KILLED    KILLED    MATCH     T33
XD2a_owner_answer_counted_as_authorizing     KILLED    KILLED    MATCH     T30, T34, T35, T41, T45, T47, T48, T49, T50, T60, T61
XD2b_answer_not_deposited_as_evidence        KILLED    KILLED    MATCH     T35
XD3a_preview_destination_returned            KILLED    KILLED    MATCH     T37
XD3b_destination_in_authorization_prompt     KILLED    KILLED    MATCH     T36, T37
XD4a_attest_without_replay                   KILLED    KILLED    MATCH     T26, T39, T41, T42, T43, T44, T46, T47, T48, T49, T52, T53, T60, T61
XD4b_replay_skips_signature_check            KILLED    KILLED    MATCH     T39
XH_unrelated_crash_injected                  CRASHED   CRASHED   MATCH     -  (55 crashed)
XD2c_answer_is_a_permanent_event             KILLED    KILLED    MATCH     T45, T47, T49, T60, T61
XD2e_per_reading_clause_removed              KILLED    KILLED    MATCH     T45
XD2f_category_clause_removed                 KILLED    KILLED    MATCH     T45, T60, T61
XL1_owner_position_check_removed             KILLED    KILLED    MATCH     T41, T47, T49, T60, T61
XL5_unknown_readings_skip_owner_checks       KILLED    KILLED    MATCH     T46
XL6_answer_not_recorded_by_owner             KILLED    KILLED    MATCH     T41, T47, T49, T60, T61
XL7_signature_not_recorded_by_owner          KILLED    KILLED    MATCH     T10, T14, T15, T18, T1, T20, T25, T27, T28, T29, T2, T33, T34, T35, T38, T3, T41, T42, T43, T45, T47, T48, T49, T4, T50, T51, T53, T56, T59, T60, T61, T6  (3 crashed)
XL8_organism_recorded_no_ignored             KILLED    KILLED    MATCH     T48
XL2_owner_clock_lifetime_check_removed       KILLED    KILLED    MATCH     T42, T53
XL3_organism_expiry_record_ignored           KILLED    KILLED    MATCH     T43
XL4_record_field_check_removed               KILLED    KILLED    MATCH     T26, T44
XS1_owner_lock_not_taken                     KILLED    KILLED    MATCH     T56
XS2_ledger_not_reread                        KILLED    KILLED    MATCH     T49, T50, T53
XS3_witness_not_reread                       KILLED    KILLED    MATCH     T51
XR1_recovery_never_completes                 KILLED    KILLED    MATCH     T54, T58
XR2_recovery_never_abandons                  KILLED    KILLED    MISMATCH  T55
    declared exact ['T55_commit_recovers_before_organism_install', 'T57_failed_checkpoint_save_changes_nothing']
    measured       ['T55_commit_recovers_before_organism_install']
XR3_no_write_ahead_intent                    KILLED    KILLED    MATCH     T54, T58
XP1_finite_check_removed_window_still_refuses KILLED    KILLED    MATCH     T52
XP2_event_timestamp_unbound                  KILLED    KILLED    MATCH     T52
XP3_annotation_type_unchecked                KILLED    KILLED    MATCH     T52, T59
XP4_authorized_at_window_unchecked           KILLED    KILLED    MATCH     T52, T59
XM1_invalid_authorized_at                    KILLED    KILLED    MATCH     T10, T14, T15, T17, T18, T1, T20, T25, T26, T27, T28, T29, T2, T33, T34, T35, T38, T3, T41, T42, T43, T44, T45, T46, T47, T48, T49, T4, T50, T51, T52, T53, T54, T55, T56, T58, T59, T60, T61, T6
XM2_forged_annotation                        KILLED    KILLED    MATCH     T10, T14, T15, T17, T18, T1, T20, T25, T26, T27, T28, T29, T2, T33, T34, T35, T38, T3, T41, T42, T43, T44, T45, T46, T47, T48, T49, T4, T50, T51, T52, T53, T54, T55, T56, T58, T59, T60, T61, T6
XM3_inconsistent_event_timestamp             KILLED    KILLED    MATCH     T10, T14, T15, T17, T18, T1, T20, T25, T26, T27, T28, T29, T2, T33, T34, T35, T38, T3, T41, T42, T43, T44, T45, T46, T47, T48, T49, T4, T50, T51, T52, T53, T54, T55, T56, T58, T59, T60, T61, T6
XR4_install_keeps_memory_on_failed_save      KILLED    SURVIVES  MISMATCH  -
    declared exact ['T57_failed_checkpoint_save_changes_nothing']
    measured       []
XR5_recovery_trusts_the_object               KILLED    KILLED    MATCH     T58
XA1_apply_skips_replay_check                 KILLED    KILLED    MATCH     T59
XP1b_finite_and_window_checks_removed        KILLED    KILLED    MATCH     T52, T59
X4b_prior_value_unchecked_at_apply           KILLED    KILLED    MATCH     T21, T23, T59
XW1a_first_crossing_window_from_own_signing  KILLED    KILLED    MATCH     T60
XW1b_later_crossing_window_from_own_signing  KILLED    KILLED    MATCH     T61

==============================================================================
mismatches vs declared: 4
receipt (statuses only, run-independent): 22d9e8eb964fdf7860e8c6f909bc9cd78c5b3d178105bf8e2a675fe7ce35ad36
RESULTS_v0_8_5.json written. Exit code is non-zero if any mismatch.

```

## Appendix B — complete independent probe output

```text
{"corrected_T57": {"output": {"X10_unattested_tail_check_removed": {"detail": "failed save left object and disk at 0; audit refused the unattested crossing and dropped the intent; retry attested", "status": "PASS"}, "XR2_recovery_never_abandons": {"detail": "audit after the failed save: RollbackDetected: A pending checkpoint commit matches neither the organism's saved state nor the witness head", "status": "FAIL"}, "XR4_install_keeps_memory_on_failed_save": {"detail": "after the failed save: object at 1, saved state at 0", "status": "FAIL"}, "XR5_recovery_trusts_the_object": {"detail": "failed save left object and disk at 0; audit refused the unattested crossing and dropped the intent; retry attested", "status": "PASS"}, "candidate": {"detail": "failed save left object and disk at 0; audit refused the unattested crossing and dropped the intent; retry attested", "status": "PASS"}}, "status": "OBSERVED"}}
{"stale_public_write": {"output": {"after": {"saved_sequence": 0, "verbosity": 0.5, "witness_sequence": 1}, "before": {"saved_sequence": 1, "verbosity": 0.25, "witness_sequence": 1}, "fresh_attest": {"exception": "RollbackDetected", "message": "Non-successor checkpoint: organism presents sequence 1, expected 2"}, "fresh_audit": {"exception": "RollbackDetected", "message": "Rollback: organism presents sequence 0, witness holds 1"}, "latest_object_retained_can_repair": {"returned": true}, "ordinary_response": "dwelling"}, "status": "OBSERVED"}}
{"post_replace_fsync_failure": {"output": {"after_failure": {"memory_sequence": 0, "saved_sequence": 1, "witness_sequence": 0}, "after_retry": {"memory_sequence": 0, "saved_sequence": 1, "witness_sequence": 1}, "fault_reached": ["organism replacement visible before directory fsync"], "first_attest": {"exception": "OSError", "message": "injected directory fsync failure AFTER organism os.replace"}, "reloaded_attest": {"returned": true}, "reloaded_audit": {"returned": true}, "same_object_retry": {"exception": "RollbackDetected", "message": "Non-successor checkpoint: organism presents sequence 1, expected 2"}}, "status": "OBSERVED"}}
{"interrupted_commit_stale_write": {"output": {"after_stale_write_and_recovery": {"pending_intent": null, "saved_sequence": 0, "verbosity": 0.5, "witness_sequence": 0}, "before_stale_write": {"saved_sequence": 1, "witness_sequence": 0}, "fresh_audit": {"returned": true}, "injected_interruption": {"exception": "OSError", "message": "interrupted before witness advance"}}, "status": "OBSERVED"}}
{"advanced_memory_save_during_attest": {"output": {"attest": {"returned": true}, "fresh_audit": {"exception": "RollbackDetected", "message": "Rollback: organism presents sequence 0, witness holds 1"}, "saved_sequence": 0, "witness_sequence": 1}, "status": "OBSERVED"}}
{"authority_controls": {"output": {"normal_crossings": {"audit": true, "character": {"curiosity": 0.35, "formality": 0.25, "verbosity": 0.0}, "mutation_sequence": 4}, "rewritten_attested_history": {"exception": "AttestationRefused", "message": "attested history was rewritten"}, "wrong_owner": {"exception": "AttestationRefused", "message": "organism is not keyed to this owner"}}, "status": "OBSERVED"}}
{"repaired_paths_controls": {"output": {"T41_owner_ledger_refuses_held_crossing": "trace index 4: owner's position: the owner's latest answer to this reading is 'no' (owner's window: its answers in verbosity since its record began)", "T42_owner_clock_lifetime": "trace index 2: reading is past its lifetime by the owner's clock", "T43_organism_expiry_record_honored": "trace index 3: the organism recorded this reading as expired before applying it", "T46_reading_must_be_signed_through_owner_tool": "trace index 2: reading was not signed through this owner tool", "T47_forged_yes_does_not_reach_attestation": "trace index 4: owner's position: the owner's latest answer to this reading is 'no' (owner's window: its answers in verbosity since its record began)", "T53_lifetime_runs_from_first_signing": "trace index 2: reading is past its lifetime by the owner's clock", "T58_stale_object_cannot_abandon_an_installed_intent": "Rollback: organism presents sequence 0, witness holds 1", "T59_apply_refuses_what_replay_would_refuse": "refused before any change: 2001-character annotation, dict annotation, clock behind issuance; 2000 characters applies and attests", "T60_owner_no_before_signing_holds_first_crossing": "trace index 4: owner's position: the owner's latest answer in this category since the reading was taken is 'no' (owner's window: its answers in verbosity since its record began)", "T61_owner_no_before_signing_holds_later_crossing": "trace index 6: owner's position: the owner's latest answer in this category since the reading was taken is 'no' (owner's window: its answers in verbosity since it signed the previous verbosity crossing)"}, "status": "OBSERVED"}}
{"window_orderings": {"output": {"audit": true, "fresh_reading_apply": "applied", "genuine_owner_yes_releases": {"returned": true}, "owner_no_before_issuance_attest": {"exception": "AttestationRefused", "message": "trace index 3: owner's position: the owner's latest answer in this category since the reading was taken is 'no' (owner's window: its answers in verbosity since its record began)"}}, "status": "OBSERVED"}}
{"pending_recovery_refusals": {"output": {"neither": {"exception": "RollbackDetected", "message": "A pending checkpoint commit matches neither the organism's saved state nor the witness head"}, "unreadable": {"exception": "RollbackDetected", "message": "A pending checkpoint commit cannot be resolved: the organism's saved state is unreadable (JSONDecodeError)"}}, "status": "OBSERVED"}}

```

## Appendix C — full diagnostic stdout

```text
==============================================================================
Humble Seed v0.8.5 CANDIDATE — falsification harness
declared ddd6fbd20585974c… frozen 2026-10-19T12:27:12Z
candidate e505d432db249276…  parent v0.7 08a756043a6500fc…
==============================================================================

TEST                                             DECLARED  MEASURED  VERDICT
T1_liveness_intervening_events                   PASS      PASS      MATCH
T2_liveness_cross_category                       PASS      PASS      MATCH
T3_stale_same_category                           PASS      PASS      MATCH
T4_second_crossing_at_clamp_floor                PASS      PASS      MATCH
T5_payload_carries_no_destination_information    PASS      PASS      MATCH
T6_rule_comes_from_constitution                  PASS      PASS      MATCH
T7_constitution_pinned_at_apply                  PASS      PASS      MATCH
T8_distribution_bound                            PASS      PASS      MATCH
T9_evidence_bound                                PASS      PASS      MATCH
T10_replay                                       PASS      PASS      MATCH
T11_expiry                                       PASS      PASS      MATCH
T12_wrong_key                                    PASS      PASS      MATCH
T13_forged_first_commit                          PASS      PASS      MATCH
T14_forged_character_resealed                    PASS      PASS      MATCH
T15_category_sequences_resealed                  PASS      PASS      MATCH
T16_permissive_rule_full_birth_repair            PASS      PASS      MATCH
T17_unattested_apply_fails_closed                PASS      PASS      MATCH
T18_rollback_witness_only                        PASS      PASS      MATCH
T19_identity_replacement_audit                   PASS      PASS      MATCH
T20_realistic_session                            PASS      PASS      MATCH
T21_prior_value_detects_independent_change       PASS      PASS      MATCH
T22_unattested_tail_check_reachable              PASS      PASS      MATCH
T23_tamper_evidence_preserved                    PASS      PASS      MATCH
T24_nonfinite_reading_refused                    PASS      PASS      MATCH
T25_clamp_comes_from_constitution                PASS      PASS      MATCH
T26_attest_refuses_unsigned_change               PASS      PASS      MATCH
T27_checkpoint_built_at_signing_time             PASS      PASS      MATCH
T28_reading_survives_a_day                       PASS      PASS      MATCH
T29_allowed_fields_come_from_constitution        PASS      PASS      MATCH
T30_D1_owner_no_holds                            PASS      PASS      MATCH
T31_D1_hold_never_crosses_or_reproposes          PASS      PASS      MATCH
T32_D1_reader_failure_holds                      PASS      PASS      MATCH
T33_D1_reader_cannot_alter_reading               PASS      PASS      MATCH
T34_D1_unrelated_answers_do_not_hold             PASS      PASS      MATCH
T35_D2_answer_is_evidence_not_authority          PASS      PASS      MATCH
T36_D2_prompts_separate_and_deterministic        PASS      PASS      MATCH
T37_D3_nothing_before_signing_depends_on_rule    PASS      PASS      MATCH
T38_D3_consequence_rendered_from_record          PASS      PASS      MATCH
T39_D4_attest_refuses_forged_reading             PASS      PASS      MATCH
T40_nonfinite_never_parsed_or_written            PASS      PASS      MATCH
T41_owner_ledger_refuses_held_crossing           PASS      PASS      MATCH
T42_owner_clock_lifetime                         PASS      PASS      MATCH
T43_organism_expiry_record_honored               PASS      PASS      MATCH
T44_replay_checks_every_record_field             PASS      PASS      MATCH
T45_D2_corrected_answer_releases_hold            PASS      PASS      MATCH
T46_reading_must_be_signed_through_owner_tool    PASS      PASS      MATCH
T47_forged_yes_does_not_reach_attestation        PASS      PASS      MATCH
T48_organism_recorded_no_honored                 PASS      PASS      MATCH
T49_stale_session_cannot_bypass_owner_no         PASS      PASS      MATCH
T50_stale_session_keeps_other_sessions_records   PASS      PASS      MATCH
T51_stale_witness_cannot_fork                    PASS      PASS      MATCH
T52_record_metadata_validated                    PASS      PASS      MATCH
T53_lifetime_runs_from_first_signing             PASS      PASS      MATCH
T54_commit_recovers_after_organism_install       PASS      PASS      MATCH
T55_commit_recovers_before_organism_install      PASS      PASS      MATCH
T56_owner_lock_excludes_other_processes          PASS      PASS      MATCH
T57_failed_checkpoint_save_changes_nothing       PASS      PASS      MATCH
T58_stale_object_cannot_abandon_an_installed_intent PASS      PASS      MATCH
T59_apply_refuses_what_replay_would_refuse       PASS      PASS      MATCH
T60_owner_no_before_signing_holds_first_crossing PASS      PASS      MATCH
T61_owner_no_before_signing_holds_later_crossing PASS      PASS      MATCH

MUTANT                                       DECLARED  MEASURED  VERDICT   killed by (crashed)
X0_NULL_identical_copy                       SURVIVES  SURVIVES  MATCH     -
X1_K1_trace_head_staleness_restored          KILLED    KILLED    MATCH     T1, T20, T28, T2, T30, T31, T32, T34, T35, T41, T43, T45, T47, T48, T49, T50, T59, T60, T61
X2_K1_global_sequence_staleness_restored     KILLED    KILLED    MATCH     T20, T28, T2
X3_K1_category_sequence_check_removed        KILLED    KILLED    MATCH     T20, T28, T3, T4
X4_K1_prior_value_check_removed              KILLED    KILLED    MATCH     T21
X5_K2_destination_back_in_payload            KILLED    KILLED    MATCH     T5
X5b_K2_destination_alias_in_payload          KILLED    KILLED    MATCH     T5
X5c_K2_destination_digest_in_payload         KILLED    KILLED    MATCH     T5
X6_K2_rule_read_from_module_constant         KILLED    KILLED    MATCH     T6
X7_K2_constitution_pin_removed               KILLED    KILLED    MATCH     T7
X8_K2_distribution_root_not_rehashed         KILLED    KILLED    MATCH     T8
X9_C5_unknown_organism_audit_returns         KILLED    KILLED    MATCH     T19
X10_unattested_tail_check_removed            KILLED    KILLED    MISMATCH  T22
    declared exact ['T22_unattested_tail_check_reachable', 'T57_failed_checkpoint_save_changes_nothing']
    measured       ['T22_unattested_tail_check_reachable']
XF1a_validator_accepts_nonfinite             KILLED    KILLED    MATCH     T24
XF1b_strict_parse_removed                    KILLED    KILLED    MATCH     T40
XF1c_canonical_json_allows_nan               KILLED    KILLED    MATCH     T40
XF2a_clamp_read_from_module_constant         KILLED    KILLED    MATCH     T25
XF2b_fields_read_from_module_constant        KILLED    KILLED    MATCH     T29
XF2c_ttl_read_from_module_constant           KILLED    KILLED    MATCH     T28, T53
XD1a_hold_ignored                            KILLED    KILLED    MATCH     T30, T31, T32, T41, T45, T48
XD1b_reader_failure_fails_open               KILLED    KILLED    MATCH     T32
XD1c_hold_reproposes                         KILLED    KILLED    MATCH     T30, T31
XD1d_reader_gets_live_reading                KILLED    KILLED    MATCH     T33
XD2a_owner_answer_counted_as_authorizing     KILLED    KILLED    MATCH     T30, T34, T35, T41, T45, T47, T48, T49, T50, T60, T61
XD2b_answer_not_deposited_as_evidence        KILLED    KILLED    MATCH     T35
XD3a_preview_destination_returned            KILLED    KILLED    MATCH     T37
XD3b_destination_in_authorization_prompt     KILLED    KILLED    MATCH     T36, T37
XD4a_attest_without_replay                   KILLED    KILLED    MATCH     T26, T39, T41, T42, T43, T44, T46, T47, T48, T49, T52, T53, T60, T61
XD4b_replay_skips_signature_check            KILLED    KILLED    MATCH     T39
XH_unrelated_crash_injected                  CRASHED   CRASHED   MATCH     -  (56 crashed)
XD2c_answer_is_a_permanent_event             KILLED    KILLED    MATCH     T45, T47, T49, T60, T61
XD2e_per_reading_clause_removed              KILLED    KILLED    MATCH     T45
XD2f_category_clause_removed                 KILLED    KILLED    MATCH     T45, T60, T61
XL1_owner_position_check_removed             KILLED    KILLED    MATCH     T41, T47, T49, T60, T61
XL5_unknown_readings_skip_owner_checks       KILLED    KILLED    MATCH     T46
XL6_answer_not_recorded_by_owner             KILLED    KILLED    MATCH     T41, T47, T49, T60, T61
XL7_signature_not_recorded_by_owner          KILLED    KILLED    MATCH     T10, T14, T15, T18, T1, T20, T25, T27, T28, T29, T2, T33, T34, T35, T38, T3, T41, T42, T43, T45, T47, T48, T49, T4, T50, T51, T53, T56, T59, T60, T61, T6  (4 crashed)
XL8_organism_recorded_no_ignored             KILLED    KILLED    MATCH     T48
XL2_owner_clock_lifetime_check_removed       KILLED    KILLED    MATCH     T42, T53
XL3_organism_expiry_record_ignored           KILLED    KILLED    MATCH     T43
XL4_record_field_check_removed               KILLED    KILLED    MATCH     T26, T44
XS1_owner_lock_not_taken                     KILLED    KILLED    MATCH     T56
XS2_ledger_not_reread                        KILLED    KILLED    MATCH     T49, T50, T53
XS3_witness_not_reread                       KILLED    KILLED    MATCH     T51
XR1_recovery_never_completes                 KILLED    KILLED    MATCH     T54, T58
XR2_recovery_never_abandons                  KILLED    KILLED    MATCH     T55, T57
XR3_no_write_ahead_intent                    KILLED    KILLED    MATCH     T54, T58
XP1_finite_check_removed_window_still_refuses KILLED    KILLED    MATCH     T52
XP2_event_timestamp_unbound                  KILLED    KILLED    MATCH     T52
XP3_annotation_type_unchecked                KILLED    KILLED    MATCH     T52, T59
XP4_authorized_at_window_unchecked           KILLED    KILLED    MATCH     T52, T59
XM1_invalid_authorized_at                    KILLED    KILLED    MATCH     T10, T14, T15, T17, T18, T1, T20, T25, T26, T27, T28, T29, T2, T33, T34, T35, T38, T3, T41, T42, T43, T44, T45, T46, T47, T48, T49, T4, T50, T51, T52, T53, T54, T55, T56, T57, T58, T59, T60, T61, T6
XM2_forged_annotation                        KILLED    KILLED    MATCH     T10, T14, T15, T17, T18, T1, T20, T25, T26, T27, T28, T29, T2, T33, T34, T35, T38, T3, T41, T42, T43, T44, T45, T46, T47, T48, T49, T4, T50, T51, T52, T53, T54, T55, T56, T57, T58, T59, T60, T61, T6
XM3_inconsistent_event_timestamp             KILLED    KILLED    MATCH     T10, T14, T15, T17, T18, T1, T20, T25, T26, T27, T28, T29, T2, T33, T34, T35, T38, T3, T41, T42, T43, T44, T45, T46, T47, T48, T49, T4, T50, T51, T52, T53, T54, T55, T56, T57, T58, T59, T60, T61, T6
XR4_install_keeps_memory_on_failed_save      KILLED    KILLED    MATCH     T57
XR5_recovery_trusts_the_object               KILLED    KILLED    MATCH     T58
XA1_apply_skips_replay_check                 KILLED    KILLED    MATCH     T59
XP1b_finite_and_window_checks_removed        KILLED    KILLED    MATCH     T52, T59
X4b_prior_value_unchecked_at_apply           KILLED    KILLED    MATCH     T21, T23, T59
XW1a_first_crossing_window_from_own_signing  KILLED    KILLED    MATCH     T60
XW1b_later_crossing_window_from_own_signing  KILLED    KILLED    MATCH     T61

==============================================================================
mismatches vs declared: 1
receipt (statuses only, run-independent): e72f4c9a27b69e0532a104d6f2646c461e97026d98060ef47eea29ba5d02ba47
RESULTS_v0_8_5.json written. Exit code is non-zero if any mismatch.

```
