# Humble Seed v0.8.4 CANDIDATE — Blind Review Report

**Reviewer:** Grok (xAI)
**Date:** 2026-10-18
**Environment:** Python 3.10.21 (main, Sep 19 2026, 01:08:03) [GCC 12.2.0], cryptography 50.0.1

## Execution

Command: `python3 -I falsify_v0_8_4.py`

**Exit code:** 1

**Receipt** (statuses only, run-independent):
```
223278777c961f4e34efabb9dafd7dc1fde0f60271da1ad5bdf6c834598bb394
```

**MISMATCH lines:** 2

Hashes verified against freeze:
- Candidate: `d66c10e415054bb4e02851bac8f47ce33f189e3a6b0f4eba65081a3503089c24`
- DECLARED_v0_8_4.json: `8db3ffdb7eb63c2c2293bc08ca31ae1cb5c9d1675f1ecf04cec546a58aada787`
- Frozen at: 2026-10-18T14:35:34Z

## Mismatches and Diagnosis

### 1. XD4a_attest_without_replay
- **Declared exact kill set:** includes T26, T39, T41–T44, T46–T49, T52, T53 (does **not** include T56)
- **Measured kill set:** same list **plus T56_owner_lock_excludes_other_processes**

**Diagnosis:**  
XD4a replaces the call to `self.verify_consequence(seed, cp)` inside the locked `attest` method with `pass`.  

T56 installs a clock probe that attempts a non-blocking flock on the owner lock, then calls `attest`. The probe is invoked when `self.clock()` is called during `verify_consequence` (the lifetime/position checks). On the candidate the lock is observed as held. On the mutant the `verify_consequence` path is skipped, so the clock probe never runs while the lock is held; T56 therefore fails and is counted as a kill.  

This is an incidental kill: the mutant is killed because it removes the code path that happens to call the clock under the lock, not because it permits an unintended attested state. The functional controls that T56 is meant to exercise (lock exclusion) are still present; the test simply does not observe them on this mutant.

### 2. XS2_ledger_not_reread
- **Declared exact kill set:** T49, T50, T53
- **Measured kill set:** T49, T50 (T53 is **not** a kill)

**Diagnosis:**  
XS2 replaces the body of `OwnerLedger._refresh` (`self._load()`) with `pass`, so the in-memory ledger is never reloaded from disk.  

T53 opens a second session that signs the same payload after the first session has already recorded `signed_at`. It then advances the first session’s clock past the TTL and expects attestation to refuse with “past its lifetime by the owner’s clock”.  

On the mutant the first session already holds the original `signed_at` in memory from its own earlier `record_signature`. The second signing does not update it (because the payload is already present), and the lifetime check in `_check_owner_acts` still sees the original timestamp. Consequently the refusal still occurs and T53 still passes. The re-read is not required for this particular single-session-memory scenario.  

T49 and T50 (which involve cross-session visibility of answers/records) correctly still kill the mutant.

Both mismatches are differences in predicted versus observed kill sets caused by the interaction of the new locking/re-read machinery with the specific probes used by T53 and T56. No test that is declared PASS fails; the candidate’s own behavior matches the declaration on every test.

## Full Harness Output

See `full_harness_output_v084.txt` in this archive. All 56 tests PASS/MATCH. All other mutants MATCH their declared verdicts.

## Review Notes

The owner-side serialization (single lock, re-read before every operation), recoverable checkpoint commit (write-ahead intent), and exhaustive record-field provenance checks behave as described in the candidate docstring.  

No evidence found of a crossing being attested that the owner did not sign, answered “no” to, or let lapse. Interrupted sign-off paths recover as tested by T54/T55. Organism-side versus owner-side differences remain those documented in the limits.

**Conclusion:** Two kill-set mismatches explained by incidental interaction of the new lock/re-read paths with the clock probe (T56) and single-session lifetime check (T53). Functional controls remain intact. Full sources, harness output, RESULTS json, and this report are included for verification.
