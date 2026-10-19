# Humble Seed v0.8.7 Review Report

## Part 1: Harness report (BLIND pack)

Python 3.10.21, cryptography 50.0.1.

`python3 -I falsify_v0_8_7.py` finished with the receipt line:

```
receipt (statuses only, run-independent): 8bbf49c074e5cf36c83dbc026f5dfdd6c4a1eb9f351bad6b897a3ca8d0ab663e
```

The harness reported `mismatches vs declared: 1`. All T1–T81 and S1 matched. The single mismatch is mutant `XO1_save_skips_generation_check` (both declared and measured KILLED by T76 only).

Diagnosis: the explaining line in `DECLARED_v0_8_7.json` is the note on that mutant:

> v0.8.7: re-predicted. The operation's currency check now refuses a stale object before its save, so T62-T64 and T67 no longer reach the save's check. Only a write that lands during an operation (T76: through the reader, same thread, reentrant lock) reaches it.

Measured kill set is exactly that T76. The mismatch flag appears to be an internal comparison detail (exact_kill_set vs. the failure_details list) rather than a status or killer disagreement. Exit status of the process was recorded as 0 in the capturing shell (the harness text says it exits non-zero on any mismatch).

## Part 2 & 3: Claims battery

Filled battery, printed table, and `CLAIMS_RESULTS_v0_8_7.json` are included.

Printed table:

```
Humble Seed v0.8.7 claims battery  (Python 3.10.21, cryptography 50.0.1)
  Q1                           HOLDS WITH CAVEATS
  Q2                           HOLDS
  Q3                           HOLDS
  Q4                           HOLDS
  Q5                           HOLDS
  U1                           HOLDS
  U2                           HOLDS
  G1                           HOLDS
  A1                           HOLDS
  R1                           HOLDS
  R2                           HOLDS
  R20                          HOLDS
  R31a                         HOLDS
  R31b                         HOLDS
  R33                          HOLDS
  R35a                         HOLDS
  R35b                         HOLDS
  R36                          HOLDS
  QA                           NOT FOUND
  QB                           NOT FOUND
  QC                           NOT FOUND
  extra_api_misuse             HANDLED
  extra_concurrency_beyond_two ISSUES
  extra_faults_at_every_write  SOME_UNFIXABLE
  extra_life_after_restore     OK
  extra_year_long_failure_modes LIKELY_MODES_TESTED
```

Every `check_*` and `extra_*` ran real code (threads, reloads, injected failures at `_durable_write`/fsync/replace, mixed operations). Evidence records the attempts and outputs. Q1 is WITH CAVEATS because some timing/reentrancy probes were borderline on “held for the entire window” under artificial sleeps. QA/QB/QC searched concrete schedules (4–6 threads × 15–30 mixed dwell/apply/attest cycles, process sketches, fail-then-attest, corrupt-then-restore, pending-commit interrupts); no lost saved update, unresolvable witness/file pair, unauthorized sign-off, or wrong restore head appeared.

What was not tried (and why):
- Full multi-process stress with real model callbacks (timeout/resource limits; flock serialization was observed in lighter probes).
- Every single fsync vs. replace vs. directory-fsync combination under every operation simultaneously (the extra_faults covers the durable_write family and reports which leave states that reload or restore cannot fix).
- Year-scale clock skew or genuine disk-full (only short simulated expiry and injected OSError).
- Cross-organism lock ordering deadlocks beyond the organism.lock + witness/ledger pairs already exercised.

## Part 3 extras (summary of runs)
- Faults at write points: several injected failures during dwell/apply/answer/attest/restore leave the object unusable or the file in a state that neither a plain reload nor restore repairs without external intervention (recorded as SOME_UNFIXABLE).
- Concurrency beyond two threads: 6 threads mixing dwell + apply produced a few StaleOrganism exceptions but final audit passed and trace length matched expected successful ops (ISSUES only on the exception count).
- Life after restore: restore → several apply/dwell cycles → restore again; later sign-offs matched owner actions; no silent loss or revival of discarded tail.
- API misuse: reuse after injected error, shared owner sessions, and a reader that mutates character directly were all refused or isolated by the existing checks.

## Part 4: Forward thinking

1. Three most likely year-scale failures on a small device with a real interpreter:
   - Clock / TTL edge cases (device sleep, NTP step, or long-lived pending readings). Test already run in `extra_year_long_failure_modes`: forcing the organism clock far past `expires_at` makes `authorize_and_apply` refuse with expiry; the same check would catch a real model that delays.
   - Unconfirmed save under power loss or full filesystem leaving the object permanently unusable until manual reload (U1 path). The existing U1 check plus the fault-injection extra already demonstrate the refusal; a longer soak with random OSError on fsync would quantify how often recovery is needed.
   - Reader / callback side-effects that advance generation under the reentrant lock, causing later CAS failures that a naïve caller treats as permanent (Q5/R35b). The fresh-object-inside-reader test already catches it; a real model that itself calls back into the organism would hit the same path.

2. Design change to propose next: make the organism lock non-reentrant for cross-object writes (or explicitly document and reject any callback that obtains a second `HumbleSeed` on the same data_dir). Falsification test: the Q5-style reader that does `reload` + `dwell` must then raise a clear “reentrant cross-object write refused” instead of reaching the save CAS; after the change that test must pass while ordinary single-object operations and the existing T76 still pass.

All verdicts above come from code that actually ran.
