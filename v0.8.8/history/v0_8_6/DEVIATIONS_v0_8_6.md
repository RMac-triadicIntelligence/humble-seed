# Deviations from DECLARED_v0_8_6.json (scored as frozen; not re-scored)

**Scored run:** 69/69 tests and 68/68 mutants MATCH; 0 mismatches. Receipt `6230c43e…7ca2`.

**No scoring deviations.**

## What was checked

- **Candidate and declaration unchanged since the freeze.**
  - The candidate's sha256 equals `CANDIDATE_v0_8_6_AT_FREEZE.sha256` (`3711074f…`).
  - `DECLARED_v0_8_6.json` equals its `.sha256` (`f5e4bc48…`, frozen 2026-10-19T13:22:02Z).
  - The harness checks both at start-up and would have refused to run otherwise.
- **The harness was written after the freeze**, by `make_harness_086.py`, from
  `falsify_v0_8_5.py`, using exact-once replacements:
  - the version renames;
  - T57's message, corrected as declared;
  - `import os` and `import stat`;
  - the `expect_stale` helper and T62–T69, implementing the declared assertions.
- **The run was single:** `python3 -I falsify_v0_8_6.py > STDOUT_v0_8_6_run.txt`, about 164 s.

## v0.8.5 deviations, fixed as declared

- **E1 (T57's message).** T57 now expects "Category sequences do not match the attested
  checkpoint" and PASSES. XR4 = {T57} and XR2 = {T55, T57, T66} are both killed exactly as
  declared.
- **E2 (X10's mechanism).** X10 = {T22}, killed exactly as declared.

## Process fix, as declared

For each new or corrected refusal, the declaration's `refusal_trace` traces the check order
and records the line that raises it.

**Check, not scored** (`refusal_trace_check_v0_8_6.py` → `REFUSAL_TRACE_CHECK_v0_8_6.txt`):
- It records where each exception actually originated while T57 and T62–T68 ran.
- **Every declared refusal came from its traced check; no earlier check pre-empted one.**
  This is the first freeze since v0.8.3 without a "which check fires first" error.

The traces were less precise than the result:
- **Lines off by one.** Most traces cite the check's `if` line rather than the `raise` line
  after it: L827 → raise at L828, L926 → L927. L1930 is the continuation of the `raise` that
  starts at L1929.
- **T68 cites the wrong line.** It cites L893, the `def` of `_require_current`; the raise is
  at L898.
- **T67's detail is wrong.** It says the saved generation is 0. It is 1: born's attestation
  installs the genesis checkpoint, which is a second save. The traced check (L926/927) is
  right.

## Noted, not deviations

- **Stale text in the frozen declaration's `rules`.** Two carried rules still name v0.8.5:
  - "...differs from DECLARED_v0_8_5.sha256";
  - "...re-checked as exact-once anchors on v0.8.5".
  In fact the harness checks `DECLARED_v0_8_6.sha256`. `build_mutant` applies every edit as
  an exact-once anchor on the v0.8.6 candidate and stops if one is not, so all 68 were
  re-checked on v0.8.6 in the scored run. The declaration is frozen, so this correction is
  recorded here and goes into the next freeze.
- **The author's post-freeze probe findings are sealed** (`AUTHOR_FINDINGS_COMMITMENT_v0_8_6.txt`).
  They are not described here, so that this record does not open them before the round-7
  reviewers report. None of them changes a scored outcome.
- **Runtime.** About 164 s, up from about 125 s: eight new tests, seven new mutants, and the
  per-save generation read.
