# Humble Seed v0.8.6: documentation-accuracy battery

`humble_seed_v0_8_6_candidate.py` is a small Python prototype. It keeps a hash-chained log
and owner-signed checkpoints, and saves its state to a JSON file. Its docstring makes 24
specific claims about how that saving and recovery behave.

**The task: test whether each claim is accurate as written.** Run code against the
candidate and report what it did. Reading the code alone is not a test.

The frozen test suite (`falsify_v0_8_6.py`, T1–T69) already passes on three machines. Its
tests are not the question here. The question is whether the docstring's claims hold beyond
the cases those tests try.

## What to do

1. Open `claims_battery_v0_8_6.py`.
   - Its helpers set up an organism, apply a change, reload, and read the saved file and the
     witness. There is also a helper for running code in a separate process.
   - `check_O1` is a worked example.
2. For each claim, fill in its `check_<ID>(d)`. It returns a verdict and the evidence: what you
   ran, and what came back. The verdict is one of:

   | Verdict | Meaning |
   |---|---|
   | `HOLDS` | true as written, in everything you tried |
   | `HOLDS WITH CAVEATS` | true, but only under conditions the text does not state |
   | `WRONG` | a run contradicts the text |
   | `NOT TESTED` | you did not get to it |

3. Q1 and Q2 are open questions. Answer `FOUND` or `NOT FOUND`, with evidence either way.
4. Anything else you notice goes in a function named `extra_<name>(d)`.
5. Run `python3 -I claims_battery_v0_8_6.py`. It prints a table and writes
   `CLAIMS_RESULTS_v0_8_6.json`.

**Rules**
- Do not edit the candidate file; `MANIFEST.sha256` covers it.
- Replacing functions or `os` calls at runtime inside your checks is fine. That is how to
  simulate a failed write or an interrupted step; the frozen suite does the same.
- Separate processes are fine, and so are threads.
- A `WRONG` or `HOLDS WITH CAVEATS` verdict needs the smallest run that shows it.

## Please report

1. Your filled-in `claims_battery_v0_8_6.py`.
2. The printed table and `CLAIMS_RESULTS_v0_8_6.json`.
3. Your Python and cryptography versions.

## The claims (verbatim from the docstring; also in `CLAIMS.json`)

| ID | Claim |
|---|---|
| O1 | The saved state carries a generation number. *(worked example)* |
| O2 | Every save runs under the organism's own lock (organism.lock, POSIX flock, reentrant within a thread). |
| O3 | It writes only if the saved generation is still the one this object last loaded or wrote. Otherwise it raises StaleOrganism, and the object must reload. |
| O4 | A new hatch cannot overwrite an existing organism. |
| O5 | attest holds the organism lock from recovery to the witness commit. |
| O6 | It [attest] refuses a stale object before signing anything. |
| I1 | A save can fail after its replace has already landed: the directory fsync comes last. On a failure, the saved generation is re-read. |
| I2 | install_checkpoint rolls memory back only if the new state did not land, so memory always matches disk. |
| C1 | A pending intent counts as installed only if the saved state names it and also loads and verifies on its own. |
| C2 | A saved state that claims the intent but does not verify is neither completed nor abandoned. |
| C3 | Abandoning still requires the saved checkpoint to be the witness head. |
| M1 | The owner's refusal names its own window ("its latest answer in verbosity since it signed the previous verbosity crossing is 'no'"), not the organism's. |
| R30a | Recovery completes an intent only from a saved state that verifies, and abandons one only if the saved checkpoint is the witness head. |
| R30b | An edit made outside the protocol (writing the file directly) is not prevented. |
| R30c | A rewind to the exact pre-install file looks the same as an install that never happened, and is abandoned. |
| R31a | Only install_checkpoint is transactional in memory. |
| R31b | If another operation's save fails before landing, the object is ahead of its disk and its next save writes that state. |
| R31c | Because of the generation check, no other object can write over it. |
| R32a | The organism lock is POSIX flock, like the owner lock (R26). |
| R32b | Writers that bypass HumbleSeed._save are not serialized. |
| R33a | A stale object must reload, and its unsaved changes are lost. |
| R33b | An answer given through a stale object reaches the owner's ledger, which is authoritative, but not the organism. |
| R34 | Every save re-reads the saved state to check its generation, a cost that grows with the trace. |
| W1 | Answers given before the owner signed the previous crossing were already checked when that crossing was attested, so the window holds without assuming when the organism issued the reading. |

**Open questions**
- **Q1.** Is there any interleaving of processes, threads or organism objects that loses a
  saved update, or leaves the witness and the saved file in a state that recovery cannot
  resolve?
- **Q2.** Is there any failed or interrupted save that leaves a state that can never be signed
  off, or that lets something be signed off that the owner did not approve?

## Notes

- **Words used above:**
  - *reading*: a proposed character change.
  - *crossing*: an applied change.
  - *attest* or *sign off*: the owner signs a checkpoint of the result.
  - *witness*: the owner's record of the latest checkpoint.
  - *intent*: a checkpoint the owner signed whose install has not yet been confirmed.
- **The author has sealed findings from his own checks** (`AUTHOR_FINDINGS_COMMITMENT_v0_8_6.txt`).
  They are released after you report. If a result of yours matches one of them, it is credited
  to you as an independent find.
- Requires Python 3.10+ and `cryptography`. Uses no network access, and writes only to
  temporary directories.

## Files

| File | What |
|---|---|
| `humble_seed_v0_8_6_candidate.py` | The candidate (frozen; do not edit) |
| `claims_battery_v0_8_6.py` | The scaffold to fill in |
| `CLAIMS.json` | The claims and questions |
| `falsify_v0_8_6.py`, `DECLARED_v0_8_6.json` | The frozen test suite and its predictions, for reference |
| `parent_humble_seed_v0_7_C5.py` | The suite's v0.7 reference, used by its T20 |
| `AUTHOR_FINDINGS_COMMITMENT_v0_8_6.txt` | The author's sealed findings commitment |
| `MANIFEST.sha256` | Hashes of the files above |
