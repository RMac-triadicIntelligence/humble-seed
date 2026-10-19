# Humble Seed v0.8.5 CANDIDATE

Soulshine (Tulsa, OK) · 19 October 2026 · built by Claude at Rusty McMurray's direction.
**Candidate, not canonical.** It carries v0.8.4's rulings and its one serialized owner
authority.

## What changed

Round 5 (ChatGPT, blind) found four defects. Recovery trusted whatever organism object it
was handed. Apply accepted a change the replay would later refuse. And a "no" you gave
before signing was outside your own check.

| | Change | Closes |
|---|---|---|
| **V** | **Recovery reads the organism's saved state**, re-read under the owner lock, never the object handed in. A checkpoint changes nothing in memory unless its save succeeds. | Recovery committed a checkpoint that existed only in memory (F2); a stale object abandoned an installed sign-off (F3) |
| **A** | **Apply = replay.** Before changing anything, the organism runs the owner's replay on the change it is about to make, and refuses whatever the replay would refuse. One clock reading serves both the expiry check and the record. | A 2001-character note applied but could never be signed off (F4); same class: a clock behind issuance |
| **W** | **Your category window starts where you can verify it**: at your own signature of the previous change in that category, or from the start for the first. Planned as "from the last attested change"; built this way because it needs no new state and is never later. | A "no" given before signing, hidden by a forged "yes" on the organism (F1) |
| **H** | T53 signs off from a fresh session; T56 checks the lock outside the replay; XP1 renamed; XP1b removes the protection itself. | v0.8.4 deviations E1, E2; ChatGPT F5 |

The docstring also corrects round 4's credit. A1 and A2 go to ChatGPT; the v0.8.4 files are
frozen, so the correction lives here and in REVIEWS.md.

## Result (scored as frozen)

- **Declaration:** `DECLARED_v0_8_5.json` (`ddd6fbd2…`, 2026-10-19T12:27:12Z), frozen before
  the harness was written, with the mutants inside it. Before the freeze I had run only a
  compile check, one basic smoke run and the anchor checks.
- **Tests: 60/61 MATCH.** **Mutants: 58/61 MATCH.** Receipt `22d9e8eb…ad36`.
- **All four mismatches come from one error of mine, in T57's declaration (E1).**
  - I predicted that audit would refuse with "Unattested authorizing event". It refused,
    correctly, through an earlier check ("Category sequences do not match the attested
    checkpoint").
  - So T57 fails on the candidate, and the three mutants it was meant to kill (X10, XR2,
    XR4) could not show that kill.
  - **Diagnostic, not scored:** with only the message expectation corrected, the candidate
    passes every remaining assertion, and XR4 and XR2 are killed as declared.
- **A second prediction error (E2):** X10 would not be killed by T57 even with the right
  message. Details in `DEVIATIONS_v0_8_5.md`.
- **Both v0.8.4 deviations are fixed.** XD4a no longer kills T56, and XS2 is now killed by
  T53.
- **Every new mutant is killed exactly as declared**, except XR4, which is caught only by
  the corrected T57. The new mutants are XR5 (recovery trusts the object), XA1 (apply skips
  the replay check), XW1a/XW1b (your window from your own signing), XP1b and X4b.

## Regression

- **ChatGPT's round-5 sequences, same steps, on v0.8.5:**
  - **F2:** object, disk and witness all stay at 0; audit refuses the unsigned-off state;
    the retry signs off.
  - **F3:** the stale object is refused, and the sign-off is completed from the saved state.
  - **F4:** the long note is refused at apply, and the reading stays pending.
  - **F1:** sign-off is refused ("owner's position").
- **Earlier suites:** ChatGPT's adapted round-4 probes and the lineage probes give identical
  output to v0.8.4.

## Limits worth knowing

- **R18 (revised): a "no" you gave in a category now carries forward.** It blocks sign-off of
  that category's next change until you answer again, even if you signed the change itself.
  That is the price of a window you can verify.
- **R29.** Apply checks its new change from the organism's live state. Tampering with that
  state is caught at sign-off, not at apply.
- **R30.** At worst, a forged saved file can advance the witness to a checkpoint you
  yourself approved. The organism then loads only if its content matches.
- **R31.** Only checkpoint install is all-or-nothing in memory.
- **Runtime** is about 125 s.

## Run

```
python3 -I falsify_v0_8_5.py     # ~125 s; exits 1 (the recorded deviations)
```

## Withheld until the round-6 reviewers report

- `RECEIPT_SALT_AND_VALUE_v0_8_5.txt`, which opens `RECEIPT_COMMITMENT_v0_8_5.txt`.
- My sealed findings: `AUTHOR_FINDINGS_v0_8_5.txt` with its salt, plus the probe script and
  output behind them. `AUTHOR_FINDINGS_COMMITMENT_v0_8_5.txt` (`1f4c8b1d…`) is included.

## Still open

- Correct T57's message and X10's set in the next freeze.
- The owner's refusal text still contains the organism-side phrase "since the reading was
  taken".
- R3 (the keyword interpreter) and the docstring's limits.
- Grace grants as their own version, once v0.8.5 holds.
