# Deviations from DECLARED_v0_8_5.json (scored as frozen; not re-scored)

**Scored run:** 60/61 tests and 58/61 mutants MATCH; receipt `22d9e8eb…`.
- All four mismatches come from one declaration error in a new test (E1).
- One carried-mutant prediction was also wrong in its mechanism (E2).
- No mismatch is a candidate defect.

## E1: T57 declared the wrong refusal message (cascades to X10, XR2, XR4)

- **Declared:** after the failed checkpoint save, audit on the same object raises
  IntegrityError containing "Unattested authorizing event".
- **Measured:** the candidate behaves correctly but refuses through an earlier check.
  - The object and its saved state are both at checkpoint 0, so T57's first assertion
    passed.
  - audit raises IntegrityError: "Category sequences do not match the attested
    checkpoint". `_verify_attestation` compares the category-sequence root before it
    looks at the unattested tail.
  - T57 stops there, so its remaining assertions never ran in the scored run.
- **Cascade:** a test that fails on the candidate cannot kill a mutant.
  - X10: declared {T22, T57}, measured {T22}.
  - XR2: declared {T55, T57}, measured {T55}.
  - XR4: declared KILLED by {T57}, measured SURVIVES. T57 was its only killer.
- **Diagnostic, not scored** (`diagnostic_T57_v0_8_5.py` → `DIAGNOSTIC_T57_v0_8_5.txt`).
  The only change is the message expectation, which becomes any IntegrityError naming
  "the attested checkpoint".
  - Candidate: PASS on every remaining assertion. Witness at 0 with no intent; retry
    attests; reload and audit pass; witness at 1.
  - XR4: FAIL ("object at 1, saved state at 0"), as declared.
  - XR2: FAIL (recovery refuses instead of abandoning), as declared.
  - XR5: PASS, as declared (T57 is not its killer).
  - X10: PASS. See E2.
- **Correction (next freeze):** T57 expects IntegrityError naming "the attested checkpoint".
  XR4 = {T57}; XR2 = {T55, T57}.

## E2: X10's predicted T57 kill was wrong in its mechanism

Even with T57 corrected, removing the unattested-tail check does not change audit's
outcome there: the category-sequence check refuses first. **Correction:** X10 = {T22}.

## Both v0.8.4 deviations are fixed, as declared

- **T56** now probes the lock from inside `install_checkpoint`. XD4a no longer kills it
  (v0.8.4 E1).
- **T53** now signs off from a fresh session. XS2 is killed by T53 (v0.8.4 E2).

## Noted, not deviations

- **The owner's refusal text is self-contradictory.** It reads "...latest answer in this
  category since the reading was taken is 'no' (owner's window: its answers in verbosity
  since its record began)". The first phrase is `answer_position`'s shared wording, which
  describes the organism's window. Cosmetic; fix with v0.8.6.
- **Runtime** is about 125 s (v0.8.4: ~100 s).
