# Humble Seed v0.8.2 CANDIDATE — Blind Review Report

**Reviewer:** Grok (xAI)
**Date:** 2026-10-17
**Environment:** Python 3.10.21 (main, Sep 19 2026, 01:08:03) [GCC 12.2.0], cryptography 50.0.1

## Execution

Command: `python3 -I falsify_v0_8_2.py`

**Exit code:** 0

**Receipt (statuses only, run-independent):**
```
498e2ff340f45c4cc96b9b04d41c06195dcb64398b7201174280c4e197f0cb66
```

**MISMATCH lines:** none (mismatches vs declared: 0)

Hashes verified:
- Candidate sha256 matches CANDIDATE_v0_8_2_AT_FREEZE.sha256 (47d15ee332aa44ea…)
- DECLARED_v0_8_2.json matches its .sha256 (0e109c0e851956a3…)
- Freeze timestamp: 2026-10-17T15:30:34Z

## Full Harness Output

See `full_harness_output.txt` in this archive. Summary:

All 40 tests PASS / MATCH.
All mutants (X0–XH) MATCH declared verdicts (SURVIVES, KILLED, or CRASHED as expected).
RESULTS_v0_8_2.json written by the harness.

## Review of Design Questions and Potential Gaps

The candidate implements D1–D4 as described in its docstring:

- **D1**: At apply time, after authenticity and derivation, a pluggable reader may return a hold reason (or None). Hold appends `reading_held`, leaves the proposal pending, does not re-propose or re-derive. Default reader holds only on an explicit owner "no" in the same category after issuance. Reader receives deep copies. Fail-closed on reader exceptions or invalid returns.
- **D2**: Two distinct prompts (question / authorization). Owner answer recorded via `record_owner_answer` as non-authorizing evidence (trace event + basin deposit). Signature remains the sole authorizer.
- **D3**: No preview of destination before signing. Consequence rendered only post-crossing from the MutationRecord.
- **D4**: OwnerTool.attest builds a fresh checkpoint request and runs `replay_signed_history` which rebuilds character/sequences/consumed/mutation count solely from genesis + this owner's signed readings. Refuses any mismatch. Reading authorization bound to organism state.

### Probes performed (runnable snippets)

Basic happy path (hatch → propose → sign → apply → attest) succeeds and updates character as expected.

Hold path: recording an owner "no" after proposal causes `authorize_and_apply` to return None, append `reading_held`, and leave the proposal pending. Matches D1 intent.

No evidence found of:
- A reading crossing or a state being attested when it should not (D4 replay + signature checks appear effective; local reseal attacks are expected to be defeated only by owner attestation).
- Ordinary use preventing a valid reading from ever applying (holds are explicit and leave the reading pending; expiry is the only automatic terminal condition observed).
- Tests that are true by construction independent of the code under test (harness loads mutants from the frozen declaration and measures concrete outcomes).
- Mutants killed for the wrong reason (all kills align with the tests that exercise the removed control).

### Known limits acknowledged

R12–R18 as documented (reader not attested, unsigned answers, shared derivation function, etc.). No new conflicts between D1–D4 observed in the examined paths.

**Conclusion:** The falsification harness matches the frozen declaration exactly. Independent probes of the primary design properties (D1–D4) behaved as specified. No additional findings of incorrect crossings, blocked valid readings, or design conflicts are reported from this review.

Full source, harness output, RESULTS json, and this report are included in the archive for independent verification.
