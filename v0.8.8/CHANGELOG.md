# Changelog: Humble Seed v0.8 → v0.8.8

Every version below is a **candidate**: built, frozen, scored once, then reviewed. Each was
scored against a declaration frozen before its harness existed. Mismatches are recorded as
deviations and never re-scored. Full records for each version are in `history/`.

| Version | Date | Tests | Mutants | Mismatches | Receipt | Declaration |
|---|---|---|---|---|---|---|
| v0.8 | 2026-10-17 | 19/20 | 10/10 | 1 | `52083c47…659b` | `3aeaf805…` |
| v0.8.1 | 2026-10-17 | 24/24 | 11/11 | 0 | `853ddfc9…ee19` | `665c0939…` |
| v0.8.2 | 2026-10-17 | 40/40 | 30/30 | 0 | `498e2ff3…cb66` | `0e109c0e…` |
| v0.8.3 | 2026-10-18 | 47/48 | 40/41 | 2 | `27214795…da59` | `241924f7…` |
| v0.8.4 | 2026-10-18 | 56/56 | 52/54 | 2 | `22327877…b394` | `8db3ffdb…` |
| v0.8.5 | 2026-10-19 | 60/61 | 58/61 | 4 | `22d9e8eb…ad36` | `ddd6fbd2…` |
| v0.8.6 | 2026-10-19 | 69/69 | 68/68 | 0 | `6230c43e…7ca2` | `f5e4bc48…` |
| v0.8.7 | 2026-10-19 | 81/81 | 79/80 | 1 | `8bbf49c0…663e` | `ba84f29e…` |
| **v0.8.8** | 2026-10-19 | 87/88 | 85/87 | 3 (one cause) | `3d3b3d1a…4224` | `21626b3f…` |

---

## v0.8.8: the final revision of the v0.8 line

The fixes for round 8. ChatGPT's claims battery found four defects and two documentation
errors; the author's three sealed findings are fixed too.

- **E1. Restore resolves a failed commit followed by a crossing** (ChatGPT r8 F1). After a
  failed witness commit and an ordinary crossing, attest, audit and restore all refused, for
  good. Restore now completes the pending commit if the attested prefix verifies, then
  rebuilds. attest and audit keep the strict rule.
- **E2. No re-entry into a save** (ChatGPT r8 F2, F3). A same-thread re-entry, such as a
  signal handler, between a save's check and its write could lose a saved update. It could
  also let restore overwrite a sign-off. A save is now marked, per thread, from its checks to
  its write, and a nested save is refused with `ReentryRefused`.
- **E3. An interrupt during the generation re-read** still marks the object unusable
  (ChatGPT r8 F4).
- **E4. Restore keeps the owner's answers** (author A1).
  - Answers in the discarded tail are carried into the restored trace.
  - Restore reports each category whose next crossing the owner's own "no" would hold.
- **E5. Lock order is enforced**: owner, then organism (author A2; ChatGPT, independently).
  An owner operation started inside an organism operation is refused, not left to deadlock.
- **E6. Locks are keyed by real path** (author A3), so a symlinked path shares the lock.
- **E7. Docstring corrections.** "The witness does not move" and "a stale object is refused
  before it changes anything" were both contradicted by the author's own frozen tests (T81,
  T76).
- **Process.** The declaration generator now keeps each mutant's `killer` inside its exact
  kill set, and refuses to freeze otherwise (v0.8.7 E1).

## v0.8.7: one operation at a time, and restore

Round 7 (ChatGPT's claims battery) showed v0.8.6's protocol failed for one object used from
two threads. An update could be lost, or a signed-off checkpoint rewound with no recovery.

- **Q.** Every organism operation holds the organism lock (flock across processes, reentrant
  in a thread) from a currency check, through every change to memory, to the save.
- **U.** A save whose outcome cannot be confirmed leaves the object unusable until reloaded.
- **G.** A saved file without a valid generation refuses every write, including a hatch.
- **A.** An answer through a stale object is recorded nowhere, and the error says so.
- **R.** `OwnerTool.restore`, built at Rusty's ruling (R20): back to the last signed-off state.

## v0.8.6: one persistence protocol

Round 6 found a stale object's ordinary save could erase newer, signed-off state.

- **O.** The saved state carries a generation, and every save writes only if the generation
  is still the one this object last saw (`StaleOrganism` otherwise). attest holds the organism
  lock from recovery to the witness commit.
- **I.** After a save error, the saved generation is re-read; install rolls back only if
  nothing landed.
- **C.** Recovery completes only from a saved state that loads and verifies (author A1).
- **M.** The owner's refusal names its own window (author A2).

## v0.8.5: recovery from disk, apply = replay

- **V.** Recovery reads the organism's saved state, never the object handed in. A checkpoint
  changes nothing in memory unless its save succeeds.
- **A.** Before applying, the organism runs the owner's replay on the change and refuses
  whatever the replay would refuse.
- **W.** The owner's category window starts at its own signature of the previous crossing.

## v0.8.4: one serialized owner authority

- **S.** Every owner operation runs under one exclusive lock and re-reads the ledger and
  witness from disk.
- **R.** Sign-off is recoverable: a durable intent, then install, then the witness advances.
- **P.** The change record's metadata is checked; the free-text note became
  `unverified_annotation`.

## v0.8.3: the owner keeps its own record

Three rulings, delegated by Rusty to Claude:
- **The owner tool keeps its own ledger.** The organism's records may veto, never authorize.
- **Lifetimes run on the owner's clock.**
- **An answer is the owner's current position.**

Also: the owner replay checks every field of every change record.

## v0.8.2: D1–D4

- **D1.** A reading applies as signed; a reader may only hold it.
- **D2.** Two prompts: the question is answered as evidence, the authorization by signing.
- **D3.** Nothing shown before signing depends on the rule.
- **D4.** The second signature attests a replayed, mechanical consequence.

Also every round-2 finding: finite-only readings; all policy from the attested
constitution; a value-based T5; crashes no longer scored as kills.

## v0.8.1: docstring only

R11 retracted after Grok refuted it. T21–T23 added.

## v0.8: liveness, and signing the reading

- **K1.** Staleness is per category, so ordinary messages no longer expire a reading.
- **K2.** The signature binds the reading (evidence, distribution, prior value, category
  sequence, constitution root) and no destination. The destination is derived at apply time,
  from a rule in the attested constitution.

Parent: v0.7, "Canonical Converged Constitutional Core" (`parent_humble_seed_v0_7_C5.py`).
