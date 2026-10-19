# Humble Seed v0.8.7 CANDIDATE

Soulshine (Tulsa, OK) · 19 October 2026 · built by Claude at Rusty McMurray's direction
("Build it into 8.7. Restore from last signed off state", 11:09 CT).
**Candidate, not canonical.** Everything from v0.8.6 not listed below is carried unchanged.

## What changed

Round 7's claims battery (ChatGPT) found that v0.8.6's protection did not hold for one
organism object shared by two threads. An update could be lost, or a signed-off checkpoint
rewound with the witness ahead and nothing able to recover it. The author reproduced it with
no instrumentation, in 1 of 3 runs at normal interpreter settings.

| | Change | Closes |
|---|---|---|
| **Q** | **One operation at a time per organism.** hatch, load, dwell_or_propose, record_owner_answer, authorize_and_apply and install_checkpoint hold the organism lock from a version check, through every change to memory, to the save. A stale object is refused before it changes anything. The owner's answer, attest, audit and restore hold the same lock. The save's own version check stays, for writes made by a callback inside an operation. | ChatGPT r7 F1 (lost update; rewound sign-off), F3 (stale object took the answer into memory) |
| **U** | **A save whose outcome cannot be confirmed leaves the object unusable** until it is reloaded. No rollback on a guess. | ChatGPT r7 F2 |
| **G** | **A saved file without a valid version number refuses every write**, including a new hatch. | Author A1 (v0.8.6) |
| **A** | **An answer through a stale object is recorded nowhere**, and the error says so. | Author A3 (v0.8.6), ChatGPT r7 F3 |
| **R** | **Restore to the last signed-off state** (`OwnerTool.restore`). It resolves any pending commit, then rebuilds the organism at the witness head from the attested part of its saved history, which is replayed and verified before anything is written. It discards everything after that and every pending reading, keeps the discarded file beside the state, and records a non-authorizing "restored" event. The witness does not move. | R20 (your ruling) |
| **H** | R31 reworded (author A2, v0.8.6); the declaration's rules name the right files; refusal traces cite the raise line. | v0.8.6 deviations |

## Result (scored as frozen)

- **Declaration:** `DECLARED_v0_8_7.json` (`ba84f29e…`), frozen 2026-10-19T16:30:36Z, before the
  harness was written.
- **Tests: 81/81 MATCH.**
- **Two-thread stress check** (candidate only, 3 s): MATCH. 179 dwellings and 54 sign-offs,
  all saved, checkpoint = witness.
- **Mutants: 79/80 MATCH.** Receipt `8bbf49c0…663e`.
- **The one mismatch is a declaration error (E1, in `DEVIATIONS_v0_8_7.md`).**
  - I re-predicted XO1's kill set as {T76}, which is exactly what was measured.
  - But I left its separate `killer` field naming T62, from v0.8.6. The harness requires the
    killer to be among the kills, so XO1 scores MISMATCH.
  - It was a generator bug: the kill-set helper did not update `killer`.
- **Every new mutant died on exactly its declared tests**, and XQ1 survived as declared:

  | Mutants | Killed by |
  |---|---|
  | XQ2 | T72 |
  | XQ3 | T74 |
  | XQ4 | T75 |
  | XU1, XU2 | T73 |
  | XV1 | T77 |
  | XT1 | T79 |
  | XT2 | T81 |
  | XT3, XT4 | T78 |
  | XT5 | T80 |

  XQ1, which drops the save's own lock, is equivalent under the operation lock.
- **The refusal traces now cite the raise line, and every one is exact.** No check-order error,
  for the second freeze running.

## Regression (not scored)

- **Round-7 thread schedules** (author reproduction):
  - two threads on one object, ChatGPT's pause and the author's lock-call pause: nothing lost,
    nothing rewound;
  - the uninstrumented two-thread race, 6 runs of 15 s at two switch intervals: 0 lost
    dwellings, checkpoint = witness, fresh audit passes every time. v0.8.6 failed 3 of 6.
- **Double fault:** memory and disk both at checkpoint 1; the object refuses as "unusable"; a
  fresh load audits.
- **ChatGPT's round-7 battery re-run on v0.8.7:**
  - Q1's schedule can no longer happen. B blocks on the lock, and ChatGPT's own 10-second pause
    times out.
  - R33a/R33b now fail their v0.8.6 expectations, because the stale object and the ledger
    record nothing.
  - I1, I2 and R34 count calls that v0.8.7 makes more of, so their fault lands elsewhere.
  - All are expected; details are in `regression_round7/`.
- **Rounds 4, 5 and 6 and the lineage probes:** output identical to v0.8.6.

## Limits worth knowing (docstring)

- **R20 (revised).** A crossing not signed off within its lifetime is no longer stuck for good:
  restore brings the organism back, and the reading must be taken and signed again.
- **R31 (revised).** If a save fails before landing and another object saves first, the first
  object's unsaved change is lost on reload. No object ever writes over newer saved state.
- **R35.** Operations are serialized per organism directory. Reading attributes, or calling
  private methods outside operations, is not. A callback inside an operation runs under the lock.
- **R36.** Restore needs the attested part of the saved history intact. There is no separate
  backup, and the unattested evidence pool (basin) is kept.
- **Runtime** is about 4.5 minutes.

## Run

```
python3 -I falsify_v0_8_7.py     # ~4.5 min; exits 1 (the recorded deviation E1)
```

## Withheld until the round-8 reviewers report

- `RECEIPT_SALT_AND_VALUE_v0_8_7.txt`, which opens `RECEIPT_COMMITMENT_v0_8_7.txt` (`3f14e8e0…`).
- My sealed findings: `AUTHOR_FINDINGS_v0_8_7.txt` with its salt, plus the probe script and its
  output. `AUTHOR_FINDINGS_COMMITMENT_v0_8_7.txt` (`1dae66bb…`, sealed 2026-10-19T16:44:22Z) is
  included.

## Still open

- Fix the kill-set generator (`killer` inside `exact_kill_set`, enforced) in the next freeze.
- R3 (the keyword interpreter).
- Grace grants as their own version, once v0.8.7 holds.
