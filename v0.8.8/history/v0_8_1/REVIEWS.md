# Blind review log

## Round 1 — v0.8 candidate, 17 October 2026

Pack: `humble_seed_v0_8_candidate_BLIND.zip` (no results; salted commitment
`4bd41f43…89b1` to the expected receipt). Sent to Grok and ChatGPT at the same time
with the same prompt.

### Grok — complete

- **Execution verified.** Receipt `52083c47…659b` matches the salted commitment.
  Python 3.10.21, cryptography 50.0.1 (the author ran 3.13.16): the receipt reproduces
  across Python versions.
- **T17**: correctly read as a check-order issue (fails closed, different objector).
  Independent confirmation of the author's declaration error.
- **Finding 1 (new):** the unattested-tail check is reachable when every attested root
  still matches (extra authorizing entry, re-chained and resealed). Adopted as **T22**.
- **Finding 2 (new, refutes R11):** the prior-value check is not redundant. An in-memory
  change to the character between issuing a reading and applying it is rejected with the
  check, and silently overwritten without it. Re-run by the author: without the check the
  tamper is laundered (state loads clean); with it the tamper is preserved as evidence
  (next load fails). Grok's test adopted verbatim as **T21**; the author added **T23** for the
  evidence-preservation half.
- **Overstated:** "(or resealed) state". A file-level reseal of the character is caught by
  the checkpoint at load, before apply runs.
- **Not attempted:** a valid reading going stale through ordinary use; tests true by
  construction.
- Facet note: earlier Grok rounds on this lineage returned no novel findings. This round
  returned two, both reproducible, one with a mutant-killing test.

### ChatGPT — incomplete (provider guardrail)

- First session: ran the harness and reported the baseline exactly (19/20; T17 with the
  exact objector string "Category sequences do not match the attested checkpoint"; exit
  code 1; all ten mutant predictions matching). Read T17 correctly as a declaration error.
- The session was then stopped by OpenAI's cybersecurity guardrail. A second session with
  a neutral prompt ("Run and analyze") was stopped the same way, mid-output. The trigger
  is the pack's content (signatures, tampering, rollback, attack helpers), not the prompt.
- **Status:** outcomes reproduced; **receipt not captured**; review blocked at the attack
  phase. Earlier ChatGPT rounds on this lineage (Sept 4) were not blocked.

## Disposition

v0.8.1 (docstring-only candidate; R11 retracted) with a new frozen declaration
(`DECLARED_v0_8_1.json`, 665c0939…): T17 corrected, T21 and T22 (Grok), T23, X4 now
KILLED, and X10 (tail check removed) as the one genuine prediction. Run: 0 mismatches;
X10 killed by exactly T22, as predicted.
