# Humble Seed v0.8.3 CANDIDATE — Blind Review Report

**Reviewer:** Grok (xAI)
**Date:** 2026-10-18
**Environment:** Python 3.10.21 (main, Sep 19 2026, 01:08:03) [GCC 12.2.0], cryptography 50.0.1

## Execution

Command: `python3 -I falsify_v0_8_3.py`

**Exit code:** 1

**Receipt** (statuses only, run-independent):
```
27214795c8e28269b073979e25bfef58b166acdecca4f071c69e4f85017bda59
```

**MISMATCH lines:** 2

Hashes verified against freeze:
- Candidate: `2fd53071a4c76f4bc74e482f1297788ad475aea035c0293f1c4a3881597739d2`
- DECLARED_v0_8_3.json: `241924f75ad5a1426ea5686882619278d30a5d76c15734063ead4ca18eba7369`
- Frozen at: 2026-10-18T14:00:27Z

## Mismatches and Diagnosis

### 1. T26_attest_refuses_unsigned_change
- **Declared:** PASS
- **Measured:** FAIL
- **Observed reason:** refused for a different reason: `"trace index 2: record fields differ from the replay: ['prior_character_snapshot']"`

**Diagnosis:**  
The test tampers with `character["formality"]` *before* applying a signed verbosity reading, then expects attestation to refuse with a message containing `"not the consequence of signed readings"`.  

In v0.8.3 the replay (ChatGPT round 3 F2, implemented without a separate ruling) now checks **every field** of every mutation record against the reconstructed state, including `prior_character_snapshot`. The snapshot recorded at apply time includes the tampered formality value; the replay’s reconstructed `before` state does not. The check therefore fails inside `replay_signed_history` with the precise field-difference message shown above, before the outer “presented state is not the consequence…” message is reached.

The attestation still correctly refuses the unsigned change. The test fails only because it hard-codes an expected reason string that the stricter v0.8.3 field check no longer produces. This is a test brittleness, not a functional regression.

### 2. XD4a_attest_without_replay
- **Declared:** KILLED by (includes T26 among others)
- **Measured:** KILLED by the same list **excluding T26**

**Diagnosis:**  
Direct consequence of the T26 failure on the candidate. A mutant is “killed” only by tests that PASS on the candidate and FAIL on the mutant. Because T26 now FAILs on the candidate itself, it cannot appear in the measured kill list for this mutant. The mutant is still killed by the other expected tests (T39, T41–T44, T46–T48).

Both mismatches are explained by the same root cause: the addition of exhaustive record-field checking in the replay.

## Full Harness Output

See `full_harness_output_v083.txt` in this archive. All other tests and mutants MATCH their declared outcomes.

## Review Notes (probes and design questions)

The three rulings and the record-field check behave as described in the candidate docstring:

- Owner ledger records signatures and answers; attestation checks crossings against the owner’s own record.
- Reading lifetime is measured from the owner’s signing time on the owner’s clock.
- Latest owner answer is the current position (a later “yes” can release a prior “no”).
- Replay verifies every mutation-record field against the reconstructed history.

No evidence found of a crossing being attested that the owner did not sign, answered “no” to, or let lapse. Ordinary-use paths that leave a state permanently unattestable are those explicitly documented as limits (R20, R21). Organism-side and owner-side checks can disagree (organism more conservative on answer windows), but the owner side is authoritative for attestation, as specified.

**Conclusion:** Two mismatches, both caused by the stricter record-field check interacting with a brittle expected-reason assertion in T26. Functional refusal of unsigned changes is preserved. Full sources, harness output, RESULTS json, and this report are included for verification.
