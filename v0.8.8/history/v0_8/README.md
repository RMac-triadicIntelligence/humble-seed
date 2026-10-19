# Humble Seed v0.8 CANDIDATE — liveness and signing the reading

Soulshine (Tulsa, OK) · 17 October 2026 · built by Claude at Rusty McMurray's direction.
**Candidate, not canonical.** K2 implements a proposal that awaits Rusty's ruling.

Parent: the v0.7 file headed "Canonical Converged Constitutional Core"
(`parent_humble_seed_v0_7_C5.py`, sha256 `08a75604…3707`). It already carries C5, the
fail-closed unknown-organism audit that the published lineage repo's v0.7 lacks.

## The two changes

| | Problem in v0.7 | v0.8 candidate |
|---|---|---|
| **K1 liveness** | A signed proposal was stale if the trace head, the whole character, or the global sequence had moved. One ordinary message between proposal and signature killed it; so did a commit in another category. | Staleness is per category: the envelope binds the category's prior value and its attested sequence. Ordinary messages and other categories no longer expire a reading. Same-category ordering (F4) still holds. |
| **K2 sign the reading** | The signature bound the exact change, so it named a destination (against the Sept 2026 rule). The rule mapping a read to a delta was a module constant, not attested. | The envelope binds evidence, distribution, prior value, category sequence and constitution root, and **no destination**. The destination is derived at apply time from signed inputs and a derivation rule that now lives in the attested constitution. |

`first_commit_pending` (bool map) became `category_sequence` (int map, attested via
`gates_root`); `first_commit` is derived as sequence == 0, so the two cannot disagree.

## Result (scored as frozen)

Declarations frozen before any test code: `DECLARED.json` (`3aeaf805…`, 2026-10-17T14:31:29Z).

- **Tests: 19/20 MATCH.** T17 is a FAIL as frozen: the state does fail closed, but I declared the
  wrong objector. See `DEVIATIONS.md` E1. Not re-scored.
- **Mutation lane: 10/10 MATCH.** Every new control has a mutant that removes it; each is killed by
  its declared test. X0 (identical copy) survives, and X4 (prior-value check removed) survives as declared in advance (R11: redundant with
  the category sequence).
- **Realistic session (T20):** 8 messages, 4 readings across 3 categories, owner signs at session end.
  v0.8 applies 3 of 4 (one per category; the second same-category reading is correctly stale).
  The parent v0.7 applies **0 of 4**.
- The new liveness tests T1 and T2 **fail on the parent v0.7**, so they test the real change.
- **Lineage regression:** with v0.8 in the merge slot, the repo's own probes give the same
  verdicts as the committed evidence (M1–M5 rejected; R10: constitution_root never the sole objector).
  `REGRESSION_lineage_probes.txt`.
- Receipt (statuses only, identical on three runs): `52083c47…659b`.

## Run

```
python3 -I falsify_v0_8.py      # ~2 s; Python 3.10+, cryptography
```
Refuses to run if `DECLARED.json` changed. Exit code is non-zero on any mismatch (currently 1, for T17).

## Open design questions (Rusty's)

- **D1** A signed reading of earlier evidence still applies after newer evidence arrives in the same
  category. Under the Oct 15 rule ("every reading is a fresh look at the whole present terrain") you
  may want apply-time re-reading instead.
- **D2** The owner sees the derived destination as a preview (returned, never stored, never signed).
- **D3** Whether the signer should see the destination at all.

## Bounds

Same author for the candidate, the declarations and the harness, in one sandbox; that is the
weakest form of check. For an independent round, send `humble_seed_v0_8_candidate_BLIND.zip`
(no results) to each reviewer at once; they report their receipt; check it against
`RECEIPT_COMMITMENT.txt` with the salt in `RECEIPT_SALT_AND_VALUE.txt` (withhold the salt until they report).
R1–R9 from the parent are unchanged; `interpret()` is still the keyword stub.
