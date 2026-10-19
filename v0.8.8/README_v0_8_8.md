# Humble Seed v0.8.8 CANDIDATE: the final revision of the v0.8 line

Soulshine (Tulsa, OK) · 19 October 2026 · built by Claude at Rusty McMurray's direction ("Go.
Make this the final revision before publishing this current works progress.").
**Candidate, not canonical.** Everything from v0.8.7 not listed below is carried unchanged.

## What changed

Round 8 found four defects and two documentation errors, all in ChatGPT's claims battery.
The author had sealed three more.

| | Change | Closes |
|---|---|---|
| **E1** | **Restore resolves a failed commit followed by a crossing.** If the saved checkpoint is the pending one but the whole saved state does not verify, restore completes the commit when the attested prefix verifies, then rebuilds. The prefix verifies when the owner's signature on the checkpoint verifies, the chain ends at its head, and a replay reproduces every root. attest and audit keep the strict rule. | ChatGPT r8 F1 (a dead end: attest, audit and restore all refused) |
| **E2** | **No re-entry into a save.** A save is marked, per thread, from its checks to its write. A save nested in it, from a signal handler or a callback, is refused with `ReentryRefused` and writes nothing. | ChatGPT r8 F2 (a lost update), F3 (restore overwrote a sign-off) |
| **E3** | **An interrupt during the generation re-read** still marks the object unusable, and the interrupt propagates. | ChatGPT r8 F4 |
| **E4** | **Restore keeps your answers.** Your answers in the discarded tail are carried into the restored trace. Restore reports `owner_no_outstanding`: each category where your own latest "no" would hold the next crossing. | Author A1 (v0.8.7) |
| **E5** | **Lock order is enforced: owner, then organism.** An owner operation started inside an organism operation is refused with `LockOrderRefused`, not left to deadlock. | Author A2 (v0.8.7); ChatGPT r8, independently |
| **E6** | **Locks are keyed by the real path**, so a symlinked path shares the lock. | Author A3 (v0.8.7) |
| **E7** | **Docstring corrections.** Restore moves the witness only when it completes a pending commit. An object made stale during its own operation has already changed its memory. Audit still works on an unusable object. | ChatGPT r8 (R2, Q3/R33, U1) |
| **H** | The declaration generator keeps every `killer` inside its exact kill set and refuses to freeze otherwise. | v0.8.7 E1 |

New limits: R37 (the prefix route's conditions), R38 (the lock-order rule's scope) and R39 (an
attest nested in a restore leaves an intent that the next owner operation abandons).

## Result (scored as frozen)

- **Declaration:** `DECLARED_v0_8_8.json` (`21626b3f…`), frozen 2026-10-19T18:41:24Z, before
  the harness was written.
- **Tests: 87/88 MATCH.** Two-thread stress check: MATCH (183 dwellings, 53 sign-offs).
- **Mutants: 85/87 MATCH.** Receipt `3d3b3d1a…4224`. Runtime 5.5 min. Exit code 1.
- **All three mismatches come from one test-setup error of mine (E1, `DEVIATIONS_v0_8_8.md`):**
  - T88 loaded the symlinked object before issuing the reading. Issuing saves, so that object
    was stale in the reader, and the organism held the reading, as designed.
  - T88 therefore failed on the candidate, so XO1 and XE7 could not count it as a kill.
  - **Diagnostic, not scored:** with the load moved after the issue, as in T76, T88 passes.
    Across all 87 mutants it fails on exactly XO1 and XE7, its two declared killers.
- **Every other new mutant died on exactly its declared tests:**

  | Mutant | Killed by |
  |---|---|
  | XE1 | T82 |
  | XE2 | T83, T84 |
  | XE3 | T85 |
  | XE4, XE5 | T86 |
  | XE6 | T87 |

- **All 15 re-predicted carried sets matched, except XO1** (E1). One example is XR1, which
  is now killed by 8 tests, including T82 and T85.
- **Every new refusal trace is exact**, apart from T88's (E1). That is three freezes in a row
  without a check-order error.

## Regression (not scored)

- **ChatGPT's round-8 battery, re-run unchanged.** Every check that found a v0.8.7 defect now
  errors, because the defect it asserts no longer happens:
  - F1: restore returns `restored`, not `RollbackDetected`;
  - F4: memory stays at checkpoint 1;
  - the lock inversion: no deadlock; the child finishes.
- **Its real-signal checks needed a one-line adaptation.** They schedule SIGUSR1 by tracing
  `_save` for its write line, which now lives in `_save_locked`; renaming that function in the
  trace is the only change (`regression_round8/chatgpt_claims/adapted/`).
  - The signal arrives at the same point as in round 8.
  - The nested operation is refused with `ReentryRefused`, and the refusal propagates out of
    the handler, so the outer operation writes nothing.
  - No update is lost and no sign-off is overwritten.
- **The author's round-8 reproduction** (`regression_round8/`):
  - F1 restored at checkpoint 1;
  - F2 and F3 refused;
  - F4 unusable;
  - Grok's G1 restored;
  - every fresh audit passes.
- **Same outcomes as v0.8.7:**
  - rounds 4, 5 and 6, and the lineage probes: identical output;
  - round 7's two batteries: identical tables;
  - the author's round-7 schedules: same outcomes, with only the timed counts differing;
  - the uninstrumented two-thread race: 6 runs, 0 lost dwellings, checkpoint = witness, and
    a fresh audit passes every time.
- Grok's round-8 battery returns the same fixed verdicts as before.

## Author findings (post-freeze, published openly)

These are in `AUTHOR_FINDINGS_v0_8_8.md`.
- **B1 (cosmetic).** When the prefix route fails too, restore's refusal names the
  whole-state reason, not the prefix's.
- **B2.** The lock-order rule also refuses owner operations on an unrelated owner directory.
  It is conservative, and documented as R38.
- **B3.** A signal handler that lets `ReentryRefused` propagate interrupts the outer operation;
  nothing saved is lost.
- **B4.** Cost is unchanged.
- **Confirmed:** across processes, 200 of 200 dwellings saved; the mixed-thread run hit 0
  lock-order refusals; per-thread state is clean after every refusal; an interrupt before or
  after the replace is handled.

## Run

```
python3 -I falsify_v0_8_8.py     # ~5.5 min; exits 1 (the recorded deviation E1)
```

## Still open

- T88 as corrected, for any later version.
- R3: `interpret()` is still the keyword stub.
- Grace grants, as their own line of work.
