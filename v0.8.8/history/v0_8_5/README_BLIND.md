# Humble Seed v0.8.5 CANDIDATE: blind review pack

Humble Seed is a small "organism" that may change its own character only when its owner
signs a reading, and only in ways the owner tool can verify afterwards. This pack holds
three things:
- the candidate;
- a falsification harness;
- a declaration of predicted outcomes, frozen before the harness was written.

It contains **no results**.

## What v0.8.5 changes

- **Recovery:** an interrupted sign-off is resolved from the organism's saved state, not from
  whatever object is handed in.
- **Apply:** before changing anything, apply runs the owner's replay check on the change it is
  about to make.
- **Owner window:** the owner's own record of "no" answers counts from its signature of the
  previous change in that category, not from its signature of this one.

The candidate's docstring explains each change and lists the known limits. The author has
sealed findings from probing it (`AUTHOR_FINDINGS_COMMITMENT_v0_8_5.txt`). Their text is
released after you report.

## Run it

```
python3 -I falsify_v0_8_5.py
```

Requires Python 3.10+ and `cryptography`. Runs in about 2 minutes, with no network access.
Please report:
- the final **receipt** line, plus your Python and cryptography versions;
- the exit code, every MISMATCH line, and **your diagnosis of each mismatch**.

`RECEIPT_COMMITMENT_v0_8_5.txt` commits to the expected receipt. The salt is released after
you report.

## Then look for what the harness misses

- Can a change be signed off that the owner didn't sign, answered "no" to, or let lapse?
- Can ordinary use, an interrupted sign-off, or a stale object leave a state that can never
  be signed off, or a witness ahead of what the organism saved?
- Does apply still accept anything that sign-off will refuse?
- Is the owner's new window wrong in some ordering of signing, answering and applying?
- Is any test true by construction, or any mutant killed for the wrong reason?

Runnable code with actual output is the most useful form for a finding. Please include it
for every "no evidence of X" claim too.

## Files

| File | What |
|---|---|
| `humble_seed_v0_8_5_candidate.py` | The candidate |
| `falsify_v0_8_5.py` | The harness; reads the mutants from the declaration |
| `DECLARED_v0_8_5.json` (+ `.sha256`, `.frozen_at`) | Frozen predictions |
| `CANDIDATE_v0_8_5_AT_FREEZE.sha256` | Candidate hash at the freeze |
| `parent_humble_seed_v0_7_C5.py` | The v0.7 parent, used by T20 |
| `v0_8_4_record/humble_seed_v0_8_4_candidate.py` | The previous version, for diffing |
| `RECEIPT_COMMITMENT_v0_8_5.txt`, `AUTHOR_FINDINGS_COMMITMENT_v0_8_5.txt` | Sealed commitments |
| `MANIFEST.sha256` | Hashes of everything above |
