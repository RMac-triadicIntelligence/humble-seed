# Humble Seed v0.8.7 CANDIDATE: blind review pack

Humble Seed is a small "organism" that may change its own character only when its owner
signs a reading, and only in ways the owner tool can verify afterwards. This pack holds:
- the candidate;
- a falsification harness;
- a declaration of predicted outcomes, frozen before the harness was written.

It contains **no results**.

## What v0.8.7 changes

- **One operation at a time per organism.** Every operation holds the organism's lock from
  its version check, through every change to memory, to its save. Two threads sharing one
  organism object can no longer interleave, and a stale object is refused before it changes
  anything.
- **A save whose outcome cannot be confirmed leaves the object unusable** until it is
  reloaded, instead of guessing.
- **A saved file without a valid version number refuses every write**, including a new hatch.
- **An answer given through a stale object is recorded nowhere**, and the error says so.
- **Restore.** `OwnerTool.restore` brings the organism back to its last signed-off state (the
  witness head). It discards everything after it, keeps a copy of the discarded file, and
  records a non-authorizing "restored" event. A crossing that missed its lifetime is no
  longer stuck for good.

The candidate's docstring explains each change and lists the known limits (R20, R31, R33
revised; R35, R36 new). The author has sealed findings from probing it
(`AUTHOR_FINDINGS_COMMITMENT_v0_8_7.txt`); their text is released after you report.

## Run it

```
python3 -I falsify_v0_8_7.py
```

Requires Python 3.10+ and `cryptography`. Runs in about 6 minutes, with no network access.
Please report:
- the final **receipt** line, plus your Python and cryptography versions;
- the exit code, every MISMATCH line, and **your diagnosis of each mismatch**.

`RECEIPT_COMMITMENT_v0_8_7.txt` commits to the expected receipt. The salt is released after
you report.

## Then check the docstring's claims against the code

A claims battery (`humble_seed_v0_8_7_CLAIMS.zip`) comes separately. It lists the
docstring's claims verbatim and provides a scaffold for testing each one with code that runs.

## Files

| File | What |
|---|---|
| `humble_seed_v0_8_7_candidate.py` | The candidate |
| `falsify_v0_8_7.py` | The harness; reads the mutants from the declaration |
| `DECLARED_v0_8_7.json` (+ `.sha256`, `.frozen_at`) | Frozen predictions |
| `CANDIDATE_v0_8_7_AT_FREEZE.sha256` | Candidate hash at the freeze |
| `parent_humble_seed_v0_7_C5.py` | The v0.7 parent, used by T20 |
| `v0_8_6_record/humble_seed_v0_8_6_candidate.py` | The previous version, for diffing |
| `RECEIPT_COMMITMENT_v0_8_7.txt`, `AUTHOR_FINDINGS_COMMITMENT_v0_8_7.txt` | Sealed commitments |
| `MANIFEST.sha256` | Hashes of everything above |
