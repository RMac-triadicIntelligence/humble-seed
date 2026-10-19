# Humble Seed v0.8.7: documentation-accuracy battery

`humble_seed_v0_8_7_candidate.py` is a small Python prototype. It keeps a hash-chained log and
owner-signed checkpoints, and saves its state to a JSON file under a lock. Its docstring makes
the 18 claims below about locking, failed saves and restoring.

**The task: test whether each claim is accurate as written.** Run code against the candidate
and report what it did. Reading the code alone is not a test.

The frozen test suite (`falsify_v0_8_7.py`, T1–T81) is included for reference. The question
here is whether the claims hold beyond the cases those tests try.

## What to do

1. Open `claims_battery_v0_8_7.py`.
   - Its helpers set up an organism, apply a change, reload, and read the saved file and the
     witness. There is also a helper for running code in a separate process.
   - `check_U1` is a worked example.
2. For each claim, fill in its `check_<ID>(d)`. It returns a verdict and the evidence: what you
   ran, and what came back. The verdict is one of:

   | Verdict | Meaning |
   |---|---|
   | `HOLDS` | true as written, in everything you tried |
   | `HOLDS WITH CAVEATS` | true, but only under conditions the text does not state |
   | `WRONG` | a run contradicts the text |
   | `NOT TESTED` | you did not get to it |

3. QA, QB and QC are open questions. Answer `FOUND` or `NOT FOUND`, with evidence either way.
   A verdict without code that ran is not a result.
4. Anything else you notice goes in a function named `extra_<name>(d)`.
5. Run `python3 -I claims_battery_v0_8_7.py`. It prints a table and writes
   `CLAIMS_RESULTS_v0_8_7.json`.

**Rules**
- Do not edit the candidate file; `MANIFEST.sha256` covers it.
- Replacing functions or `os` calls at runtime inside your checks is fine. That is how to
  simulate a failed write; the frozen suite does the same.
- Threads and separate processes are fine. Use timeouts: a test that can hang should report
  the hang as its result.
- A `WRONG` or `HOLDS WITH CAVEATS` verdict needs the smallest run that shows it.

## Please report

1. Your filled-in `claims_battery_v0_8_7.py`.
2. The printed table and `CLAIMS_RESULTS_v0_8_7.json`.
3. Your Python and cryptography versions.

## The claims (verbatim from the docstring; also in `CLAIMS.json`)

| ID | Claim |
|---|---|
| Q1 | hatch, load, dwell_or_propose, record_owner_answer, authorize_and_apply and install_checkpoint each hold the organism lock (organism.lock: POSIX flock across processes, serialized across threads, reentrant within a thread) from a currency check, through every change to memory, to the save. |
| Q2 | A save takes its snapshot and its new generation under the lock. |
| Q3 | A stale object is refused before it changes anything in memory. |
| Q4 | The owner's answer, attest, audit and restore hold the same lock. |
| Q5 | The save's own generation check stays: it catches a write that lands during an operation through a callback in the same thread (the reader). |
| U1 | If a save fails and the saved generation cannot be re-read, the object refuses every operation until it is reloaded. *(worked example)* |
| U2 | install_checkpoint does not roll memory back on a guess. |
| G1 | A saved file without a valid generation refuses every write, including a new hatch. |
| A1 | [An answer through a stale object:] Neither the owner's ledger nor the organism records it, and the error says so. |
| R1 | OwnerTool.restore first resolves any pending commit, then rebuilds the organism at the witness head from the attested prefix of its saved trace (replayed and verified before anything is written), discards everything after it and every pending reading, keeps the discarded file beside the state, and records a non-authorizing "restored" event. |
| R2 | [Restore:] The witness does not move. |
| R20 | [A crossing must be attested within its reading's lifetime.] If it is not, OwnerTool.restore brings the organism back to its last attested state; the crossing must be read and signed again. |
| R31a | If another operation's save fails before landing, the object is ahead of its disk; its next operation writes that state unless another object has saved first, in which case it is refused as stale and the unsaved change is lost on reload. |
| R31b | No object writes over a newer saved state. |
| R33 | [A stale object] is refused before it changes anything. An answer given through a stale object is recorded nowhere. |
| R35a | Operations are serialized per organism data directory. |
| R35b | A callback that runs inside an operation (the reader) runs under the lock; a write it makes through another object is caught by the save's generation check, and the operation is refused as stale. |
| R36 | Restore needs the attested prefix intact in the saved file. An unreadable file, or one truncated below the prefix, cannot be restored; no separate backup is kept. The basin (unattested evidence) is kept. |

Bracketed words give context from the surrounding docstring text; `CLAIMS.json` holds the
exact quotes.

**Open questions**
- **QA.** Is there any interleaving of processes, threads or organism objects that loses a
  saved update, or leaves the witness and the saved file in a state that neither recovery nor
  restore can resolve?
- **QB.** Is there any failed or interrupted save, or any use of restore, that leaves a state
  that can never be signed off, or that lets something be signed off that the owner did not
  approve?
- **QC.** Can restore be made to bring back anything other than the witness head, or to
  discard something the owner signed off?

## Notes

- **Words used above:**
  - *reading*: a proposed character change.
  - *crossing*: an applied change.
  - *attest* or *sign off*: the owner signs a checkpoint of the result.
  - *witness*: the owner's record of the latest checkpoint.
  - *intent*: a signed checkpoint whose install is not yet confirmed.
  - *generation*: the saved file's version number.
- **The author has sealed findings from his own checks** (`AUTHOR_FINDINGS_COMMITMENT_v0_8_7.txt`).
  They are released after you report. If a result of yours matches one of them, it is credited
  to you as an independent find.
- Requires Python 3.10+ and `cryptography`. Uses no network access, and writes only to
  temporary directories.

## Files

| File | What |
|---|---|
| `humble_seed_v0_8_7_candidate.py` | The candidate (frozen; do not edit) |
| `claims_battery_v0_8_7.py` | The scaffold to fill in |
| `CLAIMS.json` | The claims and questions |
| `falsify_v0_8_7.py`, `DECLARED_v0_8_7.json` (+ `.sha256`, `.frozen_at`) | The frozen test suite and its predictions, for reference |
| `parent_humble_seed_v0_7_C5.py` | The suite's v0.7 reference, used by its T20 |
| `AUTHOR_FINDINGS_COMMITMENT_v0_8_7.txt` | The author's sealed findings commitment |
| `MANIFEST.sha256` | Hashes of the files above |
