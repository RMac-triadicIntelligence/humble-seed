# Humble Seed v0.8.8: a falsification-tested candidate (work in progress)

**Soulshine** (Tulsa, OK) · Triadic research program · October 2026

**Status:** candidate, not canonical. This is the final revision of the v0.8 line, published
as work in progress under the Apache License 2.0 (see the end).

Humble Seed is a small Python prototype, one file, whose only dependency is `cryptography`.
It models an AI "organism" whose character can change only with its owner's signed consent,
and whose history the owner can check independently. This release contains:
- the current candidate (v0.8.8);
- its frozen predictions, its test harness and its scored result;
- every earlier v0.8 version, with its own record;
- eight rounds of review by two independent AI reviewers.

## The model in one page

- **Character.** The organism keeps a few named traits (verbosity, formality, curiosity, …),
  each a number in a range. Their starting values, allowed fields, range, the rule for
  turning a reading into a change, and the reading lifetime all live in a **constitution**.
  The owner attests the constitution at birth.
- **Readings.** The organism interprets what it sees (`dwell_or_propose`). Usually it just
  **dwells**, keeping evidence in a pool (the basin). When evidence points to a lasting
  preference, it issues a **reading**: a proposal to change one trait.
  - The owner is asked two separate things. The question ("did I read you right?") is
    answered as evidence. The authorization is answered by signing.
- **Signing the reading, not the result.** The owner's signature binds the evidence, the
  distribution, the trait's prior value, its sequence number and the constitution. It does
  **not** bind a destination. The organism derives the destination at apply time, from
  signed inputs and the attested rule. Nothing shown to the owner before signing depends
  on that rule.
- **Crossings.** Applying a signed reading changes the trait. A reader callback may **hold**
  a reading (for example, on the owner's later "no"), but it can never alter one or issue a
  new one.
- **Sign-off.** The owner attests checkpoints. Before signing, the owner tool replays every
  signed reading from the attested genesis. It refuses any state the replay does not
  reproduce, any reading the owner's own ledger did not sign, and any reading past its
  lifetime by the owner's clock or held by the owner's latest answer.
- **Witness and ledger.** The owner keeps an external **witness** (the latest checkpoint, with
  a write-ahead intent so an interrupted sign-off can be recovered). It also keeps a
  **ledger** of what it signed and answered. The organism's records can veto; they never
  authorize.
- **Persistence.**
  - The saved state is hash-chained, sealed and generation-numbered.
  - Every operation holds a per-organism lock (flock across processes, serialized across
    threads). It checks currency before changing anything, and writes only over the
    generation it read.
  - A save cannot be re-entered in the same thread.
  - Owner operations come before organism operations, and the reverse order is refused.
- **Restore.** `OwnerTool.restore` brings the organism back to the last signed-off state. It
  rebuilds from the attested part of its own history, keeps the discarded file, carries the
  owner's answers forward, and reports any outstanding "no".

The limits are numbered R1–R39 in the candidate's docstring and its parents'. For example,
`interpret()` is still a keyword stub (R3), and restore needs the attested history intact in
the saved file (R36).

## Quick start

```
pip install cryptography          # Python 3.10+
python3 quickstart.py             # hatch, sign a reading, sign off, restore
python3 -I falsify_v0_8_8.py      # the scored harness: ~5.5 min, exits 1 (one recorded deviation)
```

`quickstart.py` writes to `./demo`. The harness refuses to run if the candidate or the
frozen declaration has changed. It writes `RESULTS_v0_8_8.json` and prints a receipt, a
hash of the statuses only, which reproduces across machines and Python versions.

## How it was tested: pre-registration

Each version was built under the same discipline:

1. **Freeze the predictions before the tests exist.**
   - `DECLARED_v0_8_8.json` names every test with the exact outcome it must have.
   - It lists every **mutant**, an exact-once edit that removes one control. For each it
     declares the **exact set of tests** that will catch it.
   - Its hash and freeze time are recorded. The harness is written after the freeze and
     reads the mutants from the frozen file, so it cannot drift from the predictions.
2. **One scored run.** The result is what it is. A wrong prediction is a **deviation**: it is
   recorded with its cause and a diagnostic, and **never re-scored**.
3. **Kills are honest.** KILLED means a test that passes on the candidate fails on the
   mutant. A test that crashes is CRASHED, never a kill. One mutant only injects an unrelated
   crash, to prove the point.
4. **Refusals are traced.** Every declared refusal cites the line expected to raise it, and a
   post-run check compares that line with where the refusal actually came from.
5. **Independent review.**
   - Blind packs (no results) went to two AI reviewers, **ChatGPT** and **Grok**. Each pack
     included a salted commitment to the expected receipt.
   - In rounds 3, 4, 6, 7 and 8, the author sealed its own post-freeze findings before the
     reviewers reported, so their independent finds could be credited.
   - In later rounds, when a provider's guardrail blocked review requests, reviewers got a
     run-only pack or a claims battery. A claims battery quotes each docstring claim and
     asks the reviewer to test it by running code.

**What this does and does not show.** The same author wrote the code, the tests and the
predictions. So a clean score shows the author understands the code, not that the code is
safe. The reviews test the second. Most defects fixed in this line were found by a
reviewer, and most of those by ChatGPT (`CREDITS.md`).

## v0.8.8 result (scored as frozen)

| | |
|---|---|
| Declaration | `21626b3f…824d`, frozen 2026-10-19T18:41:24Z |
| Tests | **87/88 MATCH** |
| Two-thread stress check | MATCH |
| Mutants | **85/87 MATCH** |
| Receipt | `3d3b3d1afa938c5885a46a75450d449ba2290ca9ba877c97471ec55a4a8a4224` |

**All three mismatches have one cause, a test-setup error.** T88 loaded a second object
before issuing a reading, so the object was stale, and the organism held the reading as
designed. Two mutants then had no passing T88 to be killed by. A diagnostic run with the
order corrected passes on the candidate, and fails on exactly those two mutants. Details:
`DEVIATIONS_v0_8_8.md`.

| Version | Tests | Mutants | Mismatches |
|---|---|---|---|
| v0.8 | 19/20 | 10/10 | 1 |
| v0.8.1 | 24/24 | 11/11 | 0 |
| v0.8.2 | 40/40 | 30/30 | 0 |
| v0.8.3 | 47/48 | 40/41 | 2 |
| v0.8.4 | 56/56 | 52/54 | 2 |
| v0.8.5 | 60/61 | 58/61 | 4 |
| v0.8.6 | 69/69 | 68/68 | 0 |
| v0.8.7 | 81/81 | 79/80 | 1 |
| v0.8.8 | 87/88 | 85/87 | 3 |

Every mismatch in every version is a declaration or test error by the author. Each is
recorded, never re-scored. None was a candidate defect.

This release was unzipped into a fresh folder and every harness re-run from there. All nine
reproduce their recorded receipts, v0.8 through v0.8.8 (`RELEASE_VERIFICATION.txt`;
Python 3.13.16, cryptography 50.0.1). Reviewers had already reproduced earlier receipts on
Python 3.10 and 3.12.

## What is in this release

| Path | What |
|---|---|
| `humble_seed_v0_8_8_candidate.py` | **The candidate.** Its docstring lists changes, closed findings and limits |
| `quickstart.py` | A five-step usage example |
| `DECLARED_v0_8_8.json` (+ `.sha256`, `.frozen_at`), `CANDIDATE_v0_8_8_AT_FREEZE.sha256` | The frozen predictions |
| `falsify_v0_8_8.py`, `parent_humble_seed_v0_7_C5.py` | The harness; the v0.7 parent, used by T20 |
| `RESULTS_v0_8_8.json`, `STDOUT_v0_8_8_run.txt`, `HARNESS_v0_8_8_AT_RUN.sha256`, `RUN_v0_8_8.*` | The scored run |
| `DEVIATIONS_v0_8_8.md`, `diagnostic_T88_v0_8_8.py`, `DIAGNOSTIC_T88_v0_8_8.txt` | The deviation and its diagnostic |
| `refusal_trace_check_v0_8_8.py`, `REFUSAL_TRACE_CHECK_v0_8_8.txt` | The refusal-line check |
| `AUTHOR_FINDINGS_v0_8_8.md`, `author_probe_v0_8_8*.py`, `AUTHOR_PROBE_v0_8_8*.txt` | The author's post-freeze probes and findings |
| `regression_*`, `REGRESSION_*`, `regression_round7/`, `regression_round8/`, `lineage/` | Earlier rounds' attacks re-run on v0.8.8 (not scored) |
| `dev_prefreeze/` | The two development runs made before the freeze, as declared |
| `build/` | The generators that derived the candidate, the declaration and the harness, by exact-once edits |
| `README_v0_8_8.md` | The version README |
| `CHANGELOG.md` | v0.8 → v0.8.8 |
| `CREDITS.md` | Who found what |
| `REVIEWS.md` | The full, dated review log for rounds 1–8, with corrections |
| `history/v0_8*/` | Each earlier version's candidate, declaration, harness, results, deviations and README |
| `reviews/` | The reviewers' archives and reports, as received, with the author's re-runs |
| `v0_8_7_record/` | The parent version's record, as it sat beside the run (probe P9 reads it) |
| `RELEASE_VERIFICATION.txt` | The clean-unzip check of this release |
| `LICENSE`, `NOTICE` | Apache-2.0 license and the Soulshine notice |
| `MANIFEST.sha256`, `SHA256SUMS` | SHA-256 of every file (same list, two names) |

To verify a copy: `sha256sum -c MANIFEST.sha256`.

One note for secret scanners. Grok's round-8 battery printed the return value of a `hatch()` it ran
in a temporary test folder, and that value includes the throwaway Ed25519 owner key it generated.
The key appears in that battery's results and archive, and in their v0.8.8 re-run under
`regression_round8/`. It belonged to a test organism that was deleted with its folder, and it
controls nothing. For publication that key has been replaced with `[REDACTED-test-key]` in
`regression_round8/grok_claims/CLAIMS_RESULTS_on_v0_8_8.json`,
`regression_round8/grok_claims/src/CLAIMS_RESULTS_v0_8_7.json`, and the copy inside
`reviews/review_round8_grok/GROK_full_report_v0_8_7.zip` (rebuilt with that one change). Those
three files therefore differ from the bytes as received; every other reviewer archive is
byte-identical.

**Held back: the v0.8.7 blind-round salts.** `AUTHOR_FINDINGS_SALT_v0_8_7.txt` and
`RECEIPT_SALT_AND_VALUE_v0_8_7.txt` are not included (in `history/v0_8_7/` or `v0_8_7_record/`),
and the two salt values are shown as `[WITHHELD-v0.8.7-salt]` in `SEALS_OPENED_v0_8_7.txt`.
The commitments and the receipt itself are published; the salts are held by Soulshine. Salts from
the earlier, closed rounds (v0.8–v0.8.6) are included.

## Open items

- T88's corrected setup, for any later version.
- R3: a real interpreter in place of the keyword stub.
- Grace grants: a separate line of work, not in this release.
- Promotion from candidate to canonical is Soulshine's decision.

## Credits

Directed by **Rusty McMurray** (Soulshine). Built by **Claude** (Anthropic). Reviewed by
**ChatGPT** (OpenAI) and **Grok** (xAI). See `CREDITS.md`.

## License

Apache License 2.0. See `LICENSE` and `NOTICE`. Copyright 2026 Rusty Williams McMurray /
Soulshine (Tulsa, OK). This is a candidate, not canonical. (`build/make_release_088.py` still
writes the earlier "not yet set" notice; it is kept as the build record, and `LICENSE` governs.)
