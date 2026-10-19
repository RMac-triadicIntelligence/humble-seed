# Deviations from DECLARED_v0_8_7.json (scored as frozen; not re-scored)

**Scored run:**
- Tests: 81/81 MATCH.
- Candidate-only stress check S1: MATCH.
- Mutants: 79/80 MATCH.
- **1 mismatch, a declaration error (E1).**
- Receipt `8bbf49c0…663e`. Runtime 4 m 37 s. Exit code 1.

## E1: XO1's `killer` field was not updated when its kill set was re-predicted

- **Declared:**
  - XO1_save_skips_generation_check `exact_kill_set` = {T76}, re-predicted for v0.8.7 with its
    rationale recorded.
  - But its `killer` field still named T62, carried unchanged from v0.8.6.
- **Measured:** KILLED, by exactly {T76}. The kill set prediction was right.
- **Why it counts:** the harness requires the declared `killer` to be among the new failures,
  so XO1 scores MISMATCH. The declaration contradicted itself: T62 was named as the killer
  while being left out of the declared exact set.
- **Cause:** a generator bug in `make_declared_087.py`. `setk()` rewrites `exact_kill_set` but
  not `killer`. Of the eight mutants re-predicted with `setk`, XO1 is the only one whose old
  killer left its set.
- **Not a candidate defect.**
- **Correction (next freeze):**
  - `setk()` also sets `killer`.
  - The generator refuses to freeze if any mutant's `killer` is outside its `exact_kill_set`.

## What was checked

- **Candidate and declaration unchanged since the freeze.**
  - Candidate `0292c032…` = `CANDIDATE_v0_8_7_AT_FREEZE.sha256`.
  - Declaration `ba84f29e…`, frozen 2026-10-19T16:30:36Z.
  - Both are read-only, and the harness checks both before running.
- **Before the freeze** (as declared in `frozen_before`):
  - a compile check;
  - one smoke run (`smoke087.py`) of the basic flow and of restore's accepting path;
  - exact-once and compile checks of every mutant;
  - the static refusal traces.
  - Nothing else was run on v0.8.7.
- **The harness was written after the freeze**, by `make_harness_087.py`, from
  `falsify_v0_8_6.py`, using exact-once replacements:
  - the version renames;
  - `import threading`;
  - helpers: `saved_state`, `expect_stale_reason`, `restore_ok`, `paused_race` and the two
    pause installers;
  - T70–T81;
  - the candidate-only check S1;
  - the main loop's candidate-only section and its receipt entry.
- **The run was single:** `python3 -I falsify_v0_8_7.py > STDOUT_v0_8_7_run.txt`.

## The v0.8.6 corrections, done as recorded

- **The declaration's `rules`** now name v0.8.7's files and say anchors are enforced at run time.
- **Refusal traces cite the raise line.** Check, not scored (`refusal_trace_check_v0_8_7.py` →
  `REFUSAL_TRACE_CHECK_v0_8_7.txt`): every cited raise line is the line the exception actually
  came from.

  | Test | Raise lines cited |
  |---|---|
  | T73 | L229, L932 |
  | T74 | L936 |
  | T75 | L936, L1948 |
  | T76 | L953 |
  | T77 | L925 |
  | T78 | L1965 |
  | T79 | L1058 |
  | T80 | L1066 |

  No refusal was pre-empted by an earlier check. That is the second freeze in a row without a
  check-order error.

## Noted, not deviations

- **The author's post-freeze probe findings are sealed** (`AUTHOR_FINDINGS_COMMITMENT_v0_8_7.txt`,
  16:44:22Z). They are not described here. None of them changes a scored outcome.
- **XQ1 survives, as declared.** It drops the save's own lock, which is equivalent under the
  public API because every save runs inside a locked operation.
- **XH crashes 71 tests, as declared.** No test FAILS: the threaded tests re-raise the
  injected crash from thread A unchanged.
