# Humble Seed v0.8.2 CANDIDATE

Soulshine (Tulsa, OK) · 17 October 2026 · built by Claude at Rusty McMurray's direction.
**Candidate, not canonical.** It builds Claude's recommendations on D1–D4 so they can be
attacked. The rulings remain Rusty's.

## What changed

| | Question | Built as |
|---|---|---|
| **D1** | Re-read at apply time? | Apply as signed. A reader looks at what arrived since the reading was taken and may only **hold**: the reading stays pending, nothing crosses, nothing is re-proposed or re-derived. A reader that fails holds. Default reader: hold only on an owner "no" in that category. |
| **D2** | The owner's preview | Two prompts, two acts. The **question** ("Did I read you right?") is answered as evidence: a non-authorizing event, deposited in the basin. The **authorization** (category, bounds, lifetime) is answered by signing. |
| **D3** | Does the signer see the destination? | No. Nothing shown before signing depends on the rule. After the crossing, the consequence is rendered from the record: "I'll keep my answers shorter. (verbosity 0.50 → 0.25; …)". |
| **D4** | What does the second signature attest? | A mechanical consequence. The owner tool replays every signed reading from the genesis character in the attested constitution and refuses any state the replay doesn't reproduce. The reading stays bound to one organism's state; the tension with broadcast grace is written down (R16), not resolved. |

Every round-2 finding is fixed and credited (details in `REVIEWS.md`): finite-only readings
(ChatGPT #1), all policy read from the attested constitution (#2), D4 replay (#3), a
value-based T5 (#4), crashes no longer scored as kills (#5), and a checkpoint request built
at signing time (ChatGPT's observation). Two are the author's: readings no longer lapse
after an hour (7-day default, the owner's choice at hatch), and `1e999` is refused at parse.

## Result (scored as frozen)

- The declaration was frozen before the harness was written: `DECLARED_v0_8_2.json`
  (`0e109c0e…`, 2026-10-17T15:30:34Z). The mutants are defined inside it as exact text
  replacements, so the harness cannot drift from them. Before the freeze there was one
  smoke run, and no test or mutant had been run.
- **Tests: 40/40 MATCH.** 23 carried from v0.8.1 (re-run on changed code) and 17 new.
- **Mutants: 30/30 MATCH.** Every declared exact kill set matched. ChatGPT's alias mutant
  (X5b) and a digest variant (X5c) are now killed. ChatGPT's crash-only mutant (XH) scores
  **CRASHED**: 35 tests errored and none failed, so it is not counted as a kill.
- Receipt (statuses only): `498e2ff3…cb66`, identical across runs and from a clean copy.

## How much the result shows

- **A perfect prediction record is weak evidence.** The same author wrote the code, the
  tests and the predictions, so a clean score shows the author understands the code. It does
  not show the code is safe. The blind round tests that.
- **XF1a dies on mechanism, not safety.** With the finite check removed, NaN still can't
  cross: canonical JSON refuses to hash it. T24 fails because a different layer refused.
- **D3 hides the destination; it doesn't make it unknowable.** The prompt shows the current
  value, and the rule is in the attested constitution, so the owner can compute where a
  change lands (post-freeze probe P5). D3 means the organism never presents a destination
  for approval.
- **New limit R19, found after the freeze:** the owner replay does not check reading
  lifetimes. If the organism's clock is wound back, it can apply an expired reading and the
  owner tool will attest it (P4). The organism's clock is trusted for expiry.
- **The key check is shadowed on already-witnessed organisms:** the witness refuses first (P1). It is reachable at enrollment (P1b).
- **Lineage regression** (probes unchanged; v0.8.2 placed in the v0.7 merge slot through
  a 10-line adapter for the old `attest(seed, cp)` call). M1–M5 verdicts are unchanged.
  R10's objector changed: v0.8.2's new policy-structure check now rejects the probe's
  constitution swap first. With a fully consistent swap (P6), the checkpoint's birth root
  still objects, so R10's conclusion stands. The probe's printed conclusion is canned text
  and no longer names the actual objector.

## Run

```
python3 -I falsify_v0_8_2.py              # ~7 s; Python 3.10+, cryptography
python3 -I post_freeze_probes_v0_8_2.py   # not scored
```

## Still open

- Rusty's rulings on D1–D4 as built.
- R19 (lifetimes not replayed). T20 covers only signing in issue order.
- R3 (`interpret()` is still the keyword stub), so D1's default reader is deliberately
  narrow. R1–R9 carried, R12–R18 new (all in the candidate's docstring).
- Next blind round: send `humble_seed_v0_8_2_candidate_BLIND.zip`. It omits results and the
  post-freeze findings, which are sealed in `AUTHOR_FINDINGS_COMMITMENT_v0_8_2.txt`. After
  reviewers report, release `RECEIPT_SALT_AND_VALUE_v0_8_2.txt` and
  `AUTHOR_FINDINGS_SALT_v0_8_2.txt`, so a reviewer who finds R19 independently can be
  credited fairly.

## Files

| File | What |
|---|---|
| `humble_seed_v0_8_2_candidate.py` | The candidate (read-only; hash pinned in the declaration) |
| `falsify_v0_8_2.py` | Harness (written after the freeze) |
| `DECLARED_v0_8_2.*`, `CANDIDATE_v0_8_2_AT_FREEZE.sha256` | Frozen predictions and their hashes |
| `RESULTS_v0_8_2.json`, `STDOUT_v0_8_2_run.txt` | Scored run |
| `post_freeze_probes_v0_8_2.py`, `POST_FREEZE_PROBES_v0_8_2.txt` | Author probes after the freeze (not scored) |
| `REGRESSION_lineage_probes_v0_8_2.txt`, `regression_adapter_v0_8_2.py` | Lineage probes and the adapter used |
| `REVIEWS.md` | Blind review log, rounds 1–2, credits |
| `RECEIPT_*`, `AUTHOR_FINDINGS_*` | Commitments (and salts — withhold from reviewers) |
| `parent_humble_seed_v0_7_C5.py` | v0.7 parent (T20 runs the same session on it) |
| `v0_8_1_record/` | The full v0.8.1 record (and within it, v0.8), byte-identical |
