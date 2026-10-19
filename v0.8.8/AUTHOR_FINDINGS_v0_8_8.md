# Author findings on v0.8.8 (post-freeze probes, published openly)

`author_probe_v0_8_8.py` → `AUTHOR_PROBE_v0_8_8.txt`, run once after the scored run. There is
no further review round, so nothing is sealed. P6 errored on a probe bug: it loaded a second
object while the state held an unattested crossing, which does not load, by design. It was
fixed and re-run alone (`author_probe_v0_8_8_P6_rerun.py` → `AUTHOR_PROBE_v0_8_8_P6_rerun.txt`),
and the first output is kept unchanged. None of these findings changes a scored outcome.

## Findings

**B1 (cosmetic). When the prefix route also fails, restore's refusal gives the wrong reason** (P2).
- Setup:
  - F1's state: a failed commit, then a crossing;
  - then a dwelling inside the attested prefix is rewritten, with the chain rebuilt and the
    seal recomputed.
- Restore refuses correctly: `RollbackDetected`, the file is untouched, and the intent is
  still pending.
- But the message gives the whole-state reason ("Category sequences do not match the
  attested checkpoint"), not the reason the prefix failed ("the attested prefix does not
  match the checkpoint").
- Fix direction: name both reasons.

**B2 (note). The lock-order refusal is wider than the deadlock it prevents** (P7, R38).
- A reader that calls an owner operation is refused for this owner's lock file, where the
  deadlock is real. It is also refused for a second owner directory with a different lock
  file, which could not deadlock with this organism's attest.
- This is conservative and documented as R38. A per-pair rule would allow it; nothing here
  needs it.

**B3 (note). A signal handler that lets `ReentryRefused` propagate interrupts the outer operation** (P1).
- Probe P1 delivers a real SIGUSR1 between the save's check and its write. The handler runs
  another object's dwell.
- **Handler catches the refusal:**
  - the outer dwell completes;
  - generation +1, holding only the outer dwelling;
  - a fresh audit passes.
- **Handler re-raises it:**
  - the outer dwell raises `ReentryRefused` and nothing is written (generation +0);
  - a fresh audit passes;
  - the outer object is ahead of its disk (R31), and its next dwell succeeds.
- Either way no saved update is lost, which is what E2 promises. A handler should catch the
  refusal if the outer operation is meant to complete.

**B4 (note). Cost is unchanged** (P9; ms per dwell, back to back on one machine).

| Trace length | v0.8.7 | v0.8.8 |
|---|---|---|
| ~22 | 2.30 | 2.50 |
| ~500 | 13.86 | 16.70 |
| ~2000 | 45.27 | 44.53 |

The differences are within run-to-run noise.

## Confirmed as documented

- **P3 (E4, the report's window).** A "no" given before the owner signed the category's last
  attested crossing is not reported. One given after it is: `['verbosity']`.
- **P4 (Q across processes).** 4 processes × 50 dwells, plus 10 attests from a 5th:
  200 of 200 dwellings saved, witness 10, fresh audit True.
- **P5 (Q with the lock-order check).**
  - Dwell, cross+attest, answer and audit threads ran for 6 s on one object: 182 dwells,
    43 crossings, 85 answers.
  - 0 lock-order refusals; checkpoint 43 = witness 43; fresh audit True.
  - As in v0.8.7, the audit thread stopped when it caught an unattested state between an apply
    and its attest. Audit is not meant to pass there (T17).
- **P6 (thread state).** These all happened in one thread:
  - a `ValueError` inside the organism lock;
  - a `LockOrderRefused` in a reader;
  - a `ReentryRefused` nested in a save.
  
  Afterwards the thread's lock count was 0, its save marks were empty, and answer, attest and
  a fresh audit all succeeded.
- **P8 (E3 and U at other points).**
  - **KeyboardInterrupt before the replace:** nothing landed. Memory rolled back to
    checkpoint 0, the object stayed usable, and the audit abandoned the intent.
  - **KeyboardInterrupt after the replace, with the re-read succeeding:** it landed. Memory
    and disk are both at checkpoint 1, the object stays usable, and the audit completed the
    intent (witness 1).
