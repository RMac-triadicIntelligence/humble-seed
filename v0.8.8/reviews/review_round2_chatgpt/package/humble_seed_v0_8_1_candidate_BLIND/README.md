# Humble Seed v0.8.1 CANDIDATE — BLIND review pack

No results are included. Your job:

1. Run `python3 -I falsify_v0_8_1.py` (Python 3.10+, `cryptography`). It refuses to run if
   `DECLARED_v0_8_1.json` differs from its .sha256.
2. Report: the receipt line it prints, your Python and cryptography versions, and the full
   DECLARED / MEASURED / VERDICT tables.
3. Then attack. Does the code match `DECLARED.json`? Is any test true by construction? Does any
   mutant fail to remove the control it names? Can you make a reading apply that should not,
   or make a valid reading go stale through ordinary use? Is "sign the reading, not the result"
   actually destination-free, or does the destination leak back into what is signed?

The author holds a salted commitment to the expected receipt (`RECEIPT_COMMITMENT_v0_8_1.txt`).
The salt is released after you report.

Files: `humble_seed_v0_8_1_candidate.py` (candidate), `v0_8_record/humble_seed_v0_8_candidate.py` (prior version, needed by T0), `parent_humble_seed_v0_7_C5.py` (parent),
`falsify_v0_8_1.py` (harness), `DECLARED_v0_8_1.json` + `.sha256` + `.frozen_at` (frozen predictions),
`CANDIDATE_v0_8_1_AT_FREEZE.sha256`.
