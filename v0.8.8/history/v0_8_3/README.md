# Humble Seed v0.8.3 CANDIDATE

Soulshine (Tulsa, OK) · 18 October 2026 · built by Claude.
**Candidate, not canonical.** Rusty delegated the three rulings below to Claude
(2026-10-18). They are Claude's calls, made so they can be attacked.

## The three rulings

| # | Question | Ruling | Why |
|---|---|---|---|
| 1 | Should the owner tool keep its own record? | **Yes.** It records every reading it signs and every answer you give, and checks each new crossing against that record, not against the organism's account. The organism's own records may still **veto** (a recorded "expired", a recorded "no"), never authorize. | Same move as the rollback witness: the organism can't vouch for itself. It also keeps D1's rule: evidence can only hold. |
| 2 | Whose clock runs a reading's lifetime? | **Yours**, from when you signed. A crossing must be applied **and attested** within the lifetime (default 7 days). | The owner tool can't check the organism's clock. |
| 3 | What is an answer? | **Your current position.** Every answer stays in the record; only the latest counts. A reading is held if your latest answer to it is "no", or your latest answer in its category since it was taken is "no". "No" then "yes" releases it. "Unsure" is not "no". | A permanent "no" left a corrected answer stuck forever (author, round 3). |

Plus a fix that needed no ruling: the owner replay now checks **every** field of every
change record, so the plain-language report of a change can't be edited to say the opposite
(ChatGPT, round 3, F2).

## Result (scored as frozen)

- Declaration frozen before the harness: `DECLARED_v0_8_3.json` (`241924f7…`,
  2026-10-18T14:00:27Z). The mutants are inside it. Before the freeze: one basic smoke run,
  a compile check, and an exact-once check of each mutant's edit location. The new answer
  paths had never run.
- **Tests: 47/48 MATCH. Mutants: 40/41 MATCH.** Both mismatches have one cause, a
  declaration error in T26 (`DEVIATIONS_v0_8_3.md`). The new full record check catches
  ChatGPT's round-2 tamper earlier than the check I predicted. It is still refused and
  still preserved as evidence (`DIAGNOSTIC_T26_v0_8_3.txt`); only which check catches it
  changed. It is recorded, not re-scored, as with v0.8's T17.
- Every other kill happened for the predicted reason. Three of them are declared
  mechanism kills: a backstop refused instead of the removed check.
- The crash-only mutant (XH) scores CRASHED, not KILLED.
- Receipt `27214795…da59`, identical from a clean copy. Exit code 1 because of E1.

## Regression

- **All four round-3 findings are now refused or fixed** (`REGRESSION_earlier_probes_on_v0_8_3.txt`):
  - expired reading applied anyway: refused;
  - held reading applied anyway: refused;
  - edited change record: refused;
  - corrected answer: applies and attests.
- The v0.8.2 post-freeze probes behave as before, except P4 (expired reading), which is now
  refused.
- Lineage probes M1–M5 and R10 are identical to v0.8.2.

## What the rulings cost

- **R20.** A crossing not attested within its lifetime can never be attested, and
  restoring the last attested state isn't built. With 7 days this should be rare, but it
  is a hard edge.
- **R21.** The owner ledger is a local file. Losing it blocks attestation of readings signed
  before the loss and not yet attested.
- **R22.** The organism holds on any answer given since a reading was taken. The owner
  counts its answers to the reading, plus its answers in the category after it signed. A gap
  remains only if the organism also hides answers from its own record, and you answered "no"
  to a sibling reading before signing this one.
- **R13 (revised).** A forged "yes" written to the organism releases its hold, but the owner
  tool won't attest the crossing (T47). A forged "no" can hold and block attestation:
  denial of change, visible in the trace.
- The T26 refusal message is accurate but cryptic ("prior_character_snapshot"); see the
  observation in `DEVIATIONS_v0_8_3.md`.

## Run

```
python3 -I falsify_v0_8_3.py     # ~12 s; exits 1 (E1)
```

## Still open

- The T26 declaration fix goes in the next freeze.
- T20 covers only signing in issue order.
- R3 (keyword interpreter), R1–R9, and the limits listed in the candidate's docstring.
- Next blind round: send `humble_seed_v0_8_3_candidate_BLIND.zip`; withhold
  `RECEIPT_SALT_AND_VALUE_v0_8_3.txt`. A good test is whether reviewers diagnose the two
  mismatches as one check-order error. Both did for T17.
- `v0_8_2_record/` holds the full v0.8.2 record (and, nested, v0.8.1 and v0.8),
  byte-identical, including round 3's review log and both seals.
