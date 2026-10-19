# Deviations from DECLARED_v0_8_8.json (scored as frozen; not re-scored)

**Scored run:**
- Tests: 87/88 MATCH.
- Candidate-only stress check S1: MATCH (183 dwellings, 53 sign-offs, all saved, checkpoint = witness).
- Mutants: 85/87 MATCH.
- **3 mismatches, all from one test-setup error of mine (E1).**
- Receipt `3d3b3d1a…4224`. Runtime 5 m 29 s (18:44:24Z to 18:49:53Z). Exit code 1.

## E1: T88 loaded `b` before the reading was issued, so `b` was stale

- **Declared:**
  - T88 asserts: "A symlink to the organism's directory is made; `b` is loaded through it
    (current). A verbosity reading is issued on the live object and signed."
  - The harness followed that order.
- **What happened:**
  - Issuing a reading saves the organism (generation +1), so `b` was one generation behind
    when the reader ran.
  - `b`'s dwell raised `StaleOrganism` inside the reader. The organism treats a failing
    reader as a hold (D1: a reader that fails holds), so it recorded `reading_held` and apply
    returned None.
  - T88 FAILED on the candidate: "expected StaleOrganism, but the call returned None".
- **The candidate behaved as designed.** T88 was modelled on the frozen T76, which loads its
  `b` after issuing and signing. I moved the load ahead of them when adding the symlink.
- **Consequences** (the same cause, counted three times):

  | Item | Declared | Measured | Why |
  |---|---|---|---|
  | T88 | PASS | FAIL | the setup above |
  | XO1 | KILLED by {T76, T88} | KILLED by {T76} | T88 does not pass on the candidate, so it cannot count as a kill |
  | XE7 | KILLED by {T88} | SURVIVES | the same: T88 was its only declared killer |

- **The static trace missed it.** It traced the candidate's path for a current `b`, and the
  asserts called `b` current without checking that the setup made it so. The refusal-trace
  check shows the real origin: `_check_current` (L996), raised for `b` inside the reader, not
  the save's generation check (L1018) that was cited.
- **Diagnostic, not scored** (`diagnostic_T88_v0_8_8.py` → `DIAGNOSTIC_T88_v0_8_8.txt`):
  - `T88_corrected` differs only in loading `b` after the issue and signing.
  - On the candidate: PASS (`StaleOrganism` from the save's generation check; `b`'s dwelling
    saved; a fresh load audits).
  - Run against all 87 declared mutants, it fails on exactly two, XO1 and XE7. Those are the
    two mutants that name T88 in their declared exact sets. Under XE7 the apply deadlocks
    (5 s limit), which is author A3's finding.
  - XH errors on it, as a crash should.
- **Correction:** none in v0.8.8, which is final. For any later version, T88 is
  `T88_corrected`.

## Scope note (not a scored item)

The round-8 scope listed "F1–F4: deterministic schedules (re-entry by a call inside the
write, plus ChatGPT's real signal)". The frozen tests T83 and T84 use the call inside the
write. The real-signal case is covered outside the score instead:
- the author's post-freeze probe P1 (a real SIGUSR1 delivered between the save's check and its
  write);
- ChatGPT's own round-8 battery, re-run unchanged on v0.8.8 (`regression_round8/`).

## What was checked

- **Candidate and declaration unchanged since the freeze.**
  - Candidate `71fa4844…152d` = `CANDIDATE_v0_8_8_AT_FREEZE.sha256`.
  - Declaration `21626b3f…824d`, frozen 2026-10-19T18:41:24Z.
  - Both are read-only, and the harness checks both before running
    (`HARNESS_v0_8_8_AT_RUN.sha256` records the four hashes at the start of the run).
- **Before the freeze**, as declared in `frozen_before`, with the records in `dev_prefreeze/`:
  - a compile check;
  - the v0.8.7 suite (T1–T81) and S1 run on v0.8.8 through a development runner: 81 PASS,
    S1 PASS;
  - the round-8 author reproduction: F1 restored at checkpoint 1, F2 and F3 refused with
    `ReentryRefused`, F4 unusable after the interrupt, and Grok's G1 case fine;
  - both development runs made twice: once on a build that differed only in its module
    docstring, and once on this candidate;
  - exact-once and compile checks of every mutant, and the static refusal traces. The
    generator was dry-run once in a scratch copy, and that draft was deleted.
  - No v0.8.8 test (T82–T88) and no mutant had been run.
- **The harness was written after the freeze**, by `make_harness_088.py` from
  `falsify_v0_8_7.py`, with exact-once replacements:
  - the version renames;
  - helpers: `_record_outcome`, `judge_outcome`, `witness_state`;
  - T82–T88.
- **The run was single:** `python3 -I falsify_v0_8_8.py > STDOUT_v0_8_8_run.txt`.

## The v0.8.7 correction, done as recorded

**`killer` is inside `exact_kill_set` for every KILLED mutant**, and the freeze checks it.
- XO1's killer is now T76.
- All 15 re-predicted mutants and 7 new ones passed the check at the freeze.
- No mutant scored MISMATCH because of its `killer` field.

## Refusal traces (check, not scored)

`refusal_trace_check_v0_8_8.py` → `REFUSAL_TRACE_CHECK_v0_8_8.txt`. It traces threads too.

| Test | Raise lines cited (v0.8.8) | Measured |
|---|---|---|
| T82 | L920, L2188; commit L2191 | exact |
| T83 | L309 | exact |
| T84 | L309; rollback L894; abandon L2198 | exact |
| T85 | L247; unusable L1048; re-raise L1050; L992 | exact |
| T87 | L273 | exact |
| T88 | L1018 | **not reached** (E1: L996, for `b`, inside the reader) |

- Carried traces (T57–T80) keep their text, which cites v0.8.6 or v0.8.7 line numbers. The
  declaration labels each (`refusal_trace_lines`), and the check shows the same raise
  statements at their v0.8.8 lines.
- **No check-order error, for the third freeze running. One setup-order error (E1).**

## Noted, not deviations

- **The author's post-freeze findings are published openly** (`AUTHOR_FINDINGS_v0_8_8.md`).
  There is no further review round to seal them for.
- **XQ1 survives, as declared.**
- **XH crashes 76 tests, as declared, and no test FAILS.**
- **Every new mutant except XE7 died on exactly its declared set:**

  | Mutants | Killed by |
  |---|---|
  | XE1 | T82 |
  | XE2 | T83, T84 |
  | XE3 | T85 |
  | XE4, XE5 | T86 |
  | XE6 | T87 |

- **Every re-predicted carried set matched, except XO1** (E1). These were XR1, XR3, XC1,
  XT2, XR2, XU1, XI1, XU2, XD2a, XL6, XD2c, XO4, XQ2 and XG1.
