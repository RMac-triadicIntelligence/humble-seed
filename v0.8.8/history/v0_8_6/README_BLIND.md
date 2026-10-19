# Humble Seed v0.8.6 CANDIDATE: blind review pack

Humble Seed is a small "organism" that may change its own character only when its owner
signs a reading, and only in ways the owner tool can verify afterwards. This pack holds:
- the candidate;
- a falsification harness;
- a declaration of predicted outcomes, frozen before the harness was written.

It contains **no results**.

## What v0.8.6 changes

- **One write protocol for the organism's saved file.** The file carries a generation number.
  Every save takes the organism's lock and writes only if the file is still at the generation
  this object last saw. Otherwise the object is stale and must reload. attest holds the same
  lock from recovery to the witness commit.
- **A save that fails partway is resolved from disk.** The code checks whether the new state
  actually landed, instead of assuming it did not.
- **Recovery completes a sign-off only from a saved file that loads and verifies.**
- **The owner's refusal text** names the owner's own record.

The candidate's docstring explains each change and lists the known limits (R30–R34 are new
or revised). The author has sealed findings from probing it
(`AUTHOR_FINDINGS_COMMITMENT_v0_8_6.txt`); their text is released after you report.

## Run it

```
python3 -I falsify_v0_8_6.py
```

Requires Python 3.10+ and `cryptography`. Runs in about 3 minutes, with no network access.
Please report:
- the final **receipt** line, plus your Python and cryptography versions;
- the exit code, every MISMATCH line, and **your diagnosis of each mismatch**.

`RECEIPT_COMMITMENT_v0_8_6.txt` commits to the expected receipt. The salt is released after
you report.

## Then look for what the harness misses

- Can any write path reach the organism's saved file without the generation check, or with a
  check that passes when it should not?
- Can two processes, threads or objects interleave so that an update is lost, or so that the
  witness and the saved file disagree in a way recovery cannot resolve?
- Can a failed or interrupted save leave memory, disk and witness in a state that can never
  be signed off, or one that signs off something the owner did not approve?
- Can recovery be made to complete or abandon a sign-off wrongly?
- Can a change still be signed off that the owner didn't sign, answered "no" to, or let lapse?
- Is any test true by construction, or any mutant killed for the wrong reason?

Runnable code with actual output is the most useful form for a finding. Please include it
for every "no evidence of X" claim too.

## Files

| File | What |
|---|---|
| `humble_seed_v0_8_6_candidate.py` | The candidate |
| `falsify_v0_8_6.py` | The harness; reads the mutants from the declaration |
| `DECLARED_v0_8_6.json` (+ `.sha256`, `.frozen_at`) | Frozen predictions |
| `CANDIDATE_v0_8_6_AT_FREEZE.sha256` | Candidate hash at the freeze |
| `parent_humble_seed_v0_7_C5.py` | The v0.7 parent, used by T20 |
| `v0_8_5_record/humble_seed_v0_8_5_candidate.py` | The previous version, for diffing |
| `RECEIPT_COMMITMENT_v0_8_6.txt`, `AUTHOR_FINDINGS_COMMITMENT_v0_8_6.txt` | Sealed commitments |
| `MANIFEST.sha256` | Hashes of everything above |
