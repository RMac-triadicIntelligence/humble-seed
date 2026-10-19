# Humble Seed v0.8.1 CANDIDATE

Soulshine (Tulsa, OK) · 17 October 2026 · built by Claude at Rusty McMurray's direction.
**Candidate, not canonical.** "Sign the reading" (K2) still awaits Rusty's ruling.

v0.8.1 is a **docstring-only** revision of v0.8. It retracts R11, which Grok refuted in
blind review round 1. The harness proves the code is unchanged (T0 compares syntax trees
with docstrings removed). The full v0.8 record is preserved byte-identical in
`v0_8_record/`.

## Result (scored as frozen)

Declarations frozen before the harness changes: `DECLARED_v0_8_1.json`
(`665c0939…`, 2026-10-17T14:53:18Z). Every item is labelled *observed* (already seen) or
*predicted* (not yet run). Only X10 was a genuine prediction.

- **Tests: 24/24 MATCH** (T0–T23).
- **Mutation lane: 11/11 MATCH.** X4 (prior-value check removed), a declared survivor in
  v0.8, is now killed by Grok's T21 and by T23. X10 (unattested-tail check removed) is killed
  by exactly T22, as predicted.
- Receipt (statuses only): `853ddfc9…ee19`, identical across runs and from a clean copy.

## What round 1 changed

| Item | v0.8 | v0.8.1 |
|---|---|---|
| T17 objector | Declared "Unattested authorizing event" (wrong) | "Category sequences do not match" (gates root is checked first) |
| R11 / X4 | "Prior-value check redundant"; declared survivor | Refuted by Grok: the check preserves tamper evidence; X4 killed |
| Tail check | Never reached by any test | Reachable (Grok's T22); its mutant X10 is killed |

Credit: T21 and T22 are Grok's. Details in `REVIEWS.md`.

## Run

```
python3 -I falsify_v0_8_1.py     # ~2 s; Python 3.10+, cryptography
```

## Still open

- Rusty's rulings: D1 (apply-time re-reading under the Oct 15 rule), D2 (owner preview),
  D3 (whether the signer sees the destination).
- A second independent reviewer. ChatGPT's review was stopped by its provider's
  cybersecurity guardrail; it reproduced the outcomes but no receipt was captured.
- Not yet attempted by any reviewer: a valid reading going stale through ordinary use;
  tests true by construction.
- R1–R9 from the parent are unchanged; `interpret()` is still the keyword stub.

For the next blind round: send `humble_seed_v0_8_1_candidate_BLIND.zip`; check the reported
receipt against `RECEIPT_COMMITMENT_v0_8_1.txt` using the salt in
`RECEIPT_SALT_AND_VALUE_v0_8_1.txt` (withhold the salt until they report).
