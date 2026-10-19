# Humble Seed v0.8.6 CANDIDATE

Soulshine (Tulsa, OK) · 19 October 2026 · built by Claude at Rusty McMurray's direction.
**Candidate, not canonical.** Carries v0.8.5's rulings, the serialized owner authority,
saved-state recovery (V), apply = replay (A) and the owner window (W).

## What changed

Round 6 found the common cause behind ChatGPT's F1 and F2 and the author's sealed A1. The
organism's saved file had many writers, no write protocol, and recovery trusted it. A stale
object's ordinary save could erase newer, signed-off state.

| | Change | Closes |
|---|---|---|
| **O** | **One organism persistence protocol.** The saved state carries a generation number. Every save takes the organism's own lock and writes only if the saved generation is still the one this object last saw; otherwise it raises `StaleOrganism`, and the object must reload. A new hatch cannot overwrite an existing organism. attest holds the organism lock from recovery to the witness commit, and refuses a stale object before signing anything. | ChatGPT r6 F1: a stale object's save erased newer state, in all three schedules (sequential, during attest, after an interrupted commit) |
| **I** | **Indeterminate saves are resolved, not assumed.** After a save error, the saved generation is re-read. Install rolls memory back only if nothing landed. | ChatGPT r6 F2: a failure after the replace left memory behind disk |
| **C** | **Recovery completes only from a saved state that loads and verifies.** A saved file that claims the pending checkpoint but does not verify is neither completed nor abandoned. | Author A1 (sealed before round 6) |
| **M** | The owner's refusal names its own window: "its latest answer to this reading is 'no'" or "its latest answer in verbosity since … is 'no'". | Author A2 |
| **H** | T57 expects the check that actually fires first; X10 = {T22}. Every new or corrected refusal records the line traced to raise it. | v0.8.5 E1, E2; the check-order process fix |

## Result (scored as frozen)

- **Declaration:** `DECLARED_v0_8_6.json` (`f5e4bc48…`), frozen 2026-10-19T13:22:02Z,
  before the harness was written.
- **Tests: 69/69 MATCH.** **Mutants: 68/68 MATCH.** **0 mismatches.** Receipt `6230c43e…7ca2`.
- **The eight new tests pass:**
  - T62–T64: ChatGPT's three F1 schedules;
  - T65: F2;
  - T66: A1;
  - T67: hatch over an existing organism;
  - T68: attest of a stale object;
  - T69: the organism lock is held during saves and attest.
- **The seven new mutants each die on exactly their declared kill sets:** XO1–XO4, XI1,
  XG1, XC1.
- **The v0.8.5 deviations are fixed as declared.** T57 passes; XR4 = {T57};
  XR2 = {T55, T57, T66}; X10 = {T22}.
- **The process fix held.** A non-scored check recorded where each declared refusal actually
  originated. Every one came from its traced check. Some traces cite the `if` line instead
  of the `raise` line; details are in `DEVIATIONS_v0_8_6.md`.

## Regression (not scored)

**ChatGPT's round-6 sequences, same steps, outcomes recorded** (`REGRESSION_chatgpt_round6_probes_on_v0_8_6.txt`):

| Sequence | Outcome on v0.8.6 |
|---|---|
| Stale ordinary write | Refused (`StaleOrganism`). Saved state stays at checkpoint 1 with verbosity 0.25; a fresh load audits and attests. |
| Post-replace fsync failure | Object, disk and witness at 1 / 1 / 0, intent pending. The same-object retry attests; a fresh load audits. |
| Interrupted commit, then stale write | Stale write refused. A fresh audit completes the sign-off: witness 1, verbosity 0.25. |
| Stale write during attest | ChatGPT's hook lets the exception escape, so attest raises `StaleOrganism`. The witness stays at 0 with the intent pending; a fresh audit completes it. |
| Authority, window and pending-recovery controls | Same refusals as v0.8.5. |

**Earlier suites:** ChatGPT's round-5 sequences, adapted round-4 probes and the lineage probes
give output identical to v0.8.5, except the owner's refusal wording (M).

## Limits worth knowing (docstring R30–R34)

- **R33.** A stale object must reload, and its unsaved changes are lost.
- **R32.** The organism lock is POSIX flock. A writer that bypasses `HumbleSeed._save` is not
  serialized.
- **R30 (revised).** An edit outside the protocol (writing the file directly) is not prevented.
  Recovery refuses to complete from a saved state that does not verify.
- **R34.** Every save re-reads the saved state.
- **Runtime:** about 164 s.

## Run

```
python3 -I falsify_v0_8_6.py     # ~164 s; exit 0
```

## Withheld until the round-7 reviewers report

- `RECEIPT_SALT_AND_VALUE_v0_8_6.txt`, which opens `RECEIPT_COMMITMENT_v0_8_6.txt` (`b88ab1e3…`).
- My sealed findings: `AUTHOR_FINDINGS_v0_8_6.txt` with its salt, plus the probe scripts and
  output behind them. `AUTHOR_FINDINGS_COMMITMENT_v0_8_6.txt` (`ffdf5a04…`, sealed
  2026-10-19T14:33:59Z) is included.

## Still open

- Correct the two stale v0.8.5 names in the declaration's `rules`, and make refusal traces
  cite the `raise` line, in the next freeze.
- R3 (the keyword interpreter).
- Grace grants as their own version, once v0.8.6 holds.
