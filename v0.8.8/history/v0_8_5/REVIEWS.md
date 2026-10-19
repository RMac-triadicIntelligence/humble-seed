# Blind review log

## Round 1 — v0.8 candidate, 17 October 2026

Pack: `humble_seed_v0_8_candidate_BLIND.zip` (no results; salted commitment
`4bd41f43…89b1` to the expected receipt). Sent to Grok and ChatGPT at the same time
with the same prompt.

### Grok — complete

- **Execution verified.** Receipt `52083c47…659b` matches the salted commitment.
  Python 3.10.21, cryptography 50.0.1 (the author ran 3.13.16): the receipt reproduces
  across Python versions.
- **T17**: correctly read as a check-order issue (fails closed, different objector).
  Independent confirmation of the author's declaration error.
- **Finding 1 (new):** the unattested-tail check is reachable when every attested root
  still matches (extra authorizing entry, re-chained and resealed). Adopted as **T22**.
- **Finding 2 (new, refutes R11):** the prior-value check is not redundant. An in-memory
  change to the character between issuing a reading and applying it is rejected with the
  check, and silently overwritten without it. Re-run by the author: without the check the
  tamper is laundered (state loads clean); with it the tamper is preserved as evidence
  (next load fails). Grok's test adopted verbatim as **T21**; the author added **T23** for the
  evidence-preservation half.
- **Overstated:** "(or resealed) state". A file-level reseal of the character is caught by
  the checkpoint at load, before apply runs.
- **Not attempted:** a valid reading going stale through ordinary use; tests true by
  construction.
- Facet note: earlier Grok rounds on this lineage returned no novel findings. This round
  returned two, both reproducible, one with a mutant-killing test.

### ChatGPT — incomplete (provider guardrail)

- First session: ran the harness and reported the baseline exactly (19/20; T17 with the
  exact objector string "Category sequences do not match the attested checkpoint"; exit
  code 1; all ten mutant predictions matching). Read T17 correctly as a declaration error.
- The session was then stopped by OpenAI's cybersecurity guardrail. A second session with
  a neutral prompt ("Run and analyze") was stopped the same way, mid-output. The trigger
  is the pack's content (signatures, tampering, rollback, attack helpers), not the prompt.
- **Status:** outcomes reproduced; **receipt not captured**; review blocked at the attack
  phase. Earlier ChatGPT rounds on this lineage (Sept 4) were not blocked.

### Disposition of round 1

v0.8.1 (docstring-only; R11 retracted), with T17 corrected, T21 and T22 (Grok), T23, X4
now KILLED, and X10 as the one genuine prediction. 0 mismatches.

## Round 2 — v0.8.1 candidate, 17 October 2026

Pack: `humble_seed_v0_8_1_candidate_BLIND.zip` (sha256 `c41f3d08…ae52`; salted
commitment `193972b2…991c` to the expected receipt). Sent to Grok and ChatGPT.

### Grok — complete, no findings

- **Execution verified.** Receipt `853ddfc9…ee19` matches the commitment. Python 3.10.21,
  cryptography 50.0.1.
- Confirmed the round-1 changes: the T17 objector, T21/T23 killing X4, T22 killing X10, the
  R11 retraction, and T0.
- Probed that the payload names no destination and that a post-signature rule change is
  rejected. Both held.
- Wrote one new test: flip `first_commit` on the pending object after issuance. It was
  rejected with "first-commit mismatch", the same check T13 reaches. Not a finding.
- **False all-clear:** "Ordinary use does not stale a valid reading." Correct for the
  staleness conditions (dwellings, other-category commits, checkpoints). Wrong overall: in
  v0.8.1 a reading lapsed one hour after issuance, so signing at the end of an ordinary
  session failed. See the author findings below.

### ChatGPT — complete (no guardrail block this round)

- **Execution verified** on the exact zip delivered (sha256 matches). Receipt
  `853ddfc9…ee19` matches the commitment. Python 3.12.14, cryptography 50.0.2. Its bundle
  re-runs from a fresh extraction. The author reproduced every finding from it.
- **#1 NaN crosses.** A NaN lead weight passed validation and the minimum-weight test,
  applied at 0.25, attested, loaded and audited.
  → v0.8.2: readings must be finite; strict parsing; canonical JSON refuses non-finite
  numbers. **T24, T40; XF1a, XF1b, XF1c.**
- **#2 Clamp outside the constitution.** Changing the module `VALUE_MIN` after signing moved
  the result from 0.25 to 0.40 with the constitution and the signed reading unchanged.
  → v0.8.2: value range, allowed fields, reading lifetime and genesis character are all read
  from the attested constitution. **T25, T29; XF2a, XF2b.**
- **#3 Attestation sealed an unsigned change.** Formality was set to 0.99 while a verbosity
  reading waited. The normal attestation helper sealed both.
  → v0.8.2 D4: the owner tool replays signed readings before it attests. **T26, T39; XD4a,
  XD4b.**
- **#4 T5 checked names.** A destination under the name `landing_value` passed all 24 tests.
  → v0.8.2: T5 checks values, and checks that the payload is unchanged when only the rule
  changes. **X5b (ChatGPT's mutant), X5c (a digest no value scan can see).**
- **#5 Crashes counted as kills.** An unrelated crash produced 20 ERRORs and was scored
  KILLED. ChatGPT also checked that every shipped kill was a genuine assertion failure.
  → v0.8.2: CRASHED is its own verdict. **XH (ChatGPT's crash mutant), declared CRASHED.**
- **Observation: stale checkpoint request.** A request returned at apply went stale if a
  dwelling happened before signing; a fresh request recovered.
  → v0.8.2: the owner tool builds the request when it signs. **T27.**
- **Observation: the second signature binds the result.** The checkpoint signature binds
  the exact resulting character root.
  → v0.8.2 D4: that signature now attests a replayed, mechanical consequence.

### Author findings (not reported by either reviewer)

- **Readings lapsed after one hour.** A reading taken at the start of a session was dead by
  the time the owner signed at the end of the day. Neither reviewer reported this; Grok
  explicitly cleared it.
  → v0.8.2: default lifetime 7 days, chosen by the owner at hatch, attested. **T28, XF2c.**
- **`1e999` parses to infinity**, a variant of #1 that a NaN-only check misses.
  → Refused at parse. **T40.**
- **Open, not addressed:** T20's 3-of-4 result holds for signing in issue order. It says
  nothing about other orders.

## Disposition of round 2

v0.8.2 builds Claude's D1–D4 recommendations and fixes every round-2 item. Declaration
`DECLARED_v0_8_2.json` (`0e109c0e…`) was frozen before the harness was written, with the
mutants defined inside it. Run: 40/40 tests and 30/30 mutants MATCH; every exact kill set
as predicted; XH CRASHED, not KILLED.

The author's post-freeze probes (not scored) add **R19**: the owner replay does not check
reading lifetimes. Details in `README.md` and `POST_FREEZE_PROBES_v0_8_2.txt`.

Credit summary: Grok (round 1: T21, T22). ChatGPT (round 2: findings #1–#5, both
observations, the X5b and XH mutants). Author (lifetime, `1e999`, R19).

## Round 3 — v0.8.2 candidate, 17 October 2026

Pack: `humble_seed_v0_8_2_candidate_BLIND.zip` (salted receipt commitment `f7c98d8a…0bbf`;
author's post-freeze findings sealed in `01f43ae3…3f08`).

### Grok — complete, no findings

- **Execution verified.** Receipt `498e2ff3…cb66` matches the commitment. Python 3.10.21,
  cryptography 50.0.1, against the author's 3.13.16: the receipt reproduces across versions.
  Every file in Grok's archive matches the pack manifest.
- Described D1–D4 accurately. Two probes, both happy-path: a normal crossing, and a hold on
  an owner "no". No probe code was included in the archive.
- Reported no evidence of ordinary use stopping a valid reading from applying, of tests
  true by construction, of kills for the wrong reason, or of conflicts between D1–D4.
- **Missed the sealed author findings:** R19 (owner replay does not check lifetimes), D3
  derivability (P5), and the key check shadowed by the witness (P1).
- **False all-clear, demonstrated after the report (author):** a corrected answer cannot
  un-hold a reading. With an owner answer of "no" and then "yes" on the same reading, the
  signed reading is held and stays held until it expires. The default reader treats any
  "no" since issuance as final; the trace is append-only, so the owner cannot retract it.
  This is a D1×D2 interaction, and the exact case the blind README asked about ("Can
  ordinary use stop a valid reading from ever applying?"). It fails safe (no change), and a
  new reading issued after the "no" can still apply (R18). Sealed before ChatGPT's round in
  `AUTHOR_FINDINGS_COMMITMENT_2_v0_8_2.txt`; evidence in `post_report_probe_corrected_answer.py`.
- Pattern across three Grok rounds: round 1 two real findings; rounds 2 and 3 no findings,
  each with an all-clear later shown false on the question asked.

## Round 3 (continued) — ChatGPT on v0.8.2: stopped by its provider's guardrail

ChatGPT's run was cut off while it packaged its examples. No receipt or code was captured.
Its in-progress description (screenshot, `CHATGPT_round4_screenshot.png`) named three
findings. The author reproduced all three from that description; credit is ChatGPT's.
Evidence: `post_report_probe_chatgpt_round4.py`, `POST_REPORT_PROBE_chatgpt_round4.txt`.

- **F1a — expired reading attested.** Live apply rejects an expired reading. An organism
  that applies it anyway gets attested by the owner tool, and the state reloads and audits
  with the "proposal expired" rejection still in its history. **The author's sealed R19
  (P4), found independently.** ChatGPT's version goes further: the replay ignores a refusal
  the trace itself records.
- **F1b — held reading attested (new).** The owner answers "no" and live apply holds the
  reading. An organism that applies it anyway is attested, reloads and audits, with the "no"
  and the hold in its history. The replay ignores D1 holds and D2 answers.
- **F2 — false consequence (new).** The replay checks the change, lead, delta, roots and
  sequences, but not the record's `prior_value`, `first_commit` or prior snapshot. With
  those edited, the state attests, and D3's rendered consequence says the opposite of what
  happened ("I'll give fuller answers. (verbosity 0.00 → 0.25; … rule step -0.25)").

Common cause: D4 replays what was signed and what the rule derives, but takes the
organism's word for everything else, including its own liveness decisions.

## Disposition of round 3

The author delegated the three rulings to Claude (2026-10-18):
1. **Owner ledger:** yes.
2. **Lifetimes:** run on the owner's clock, from signing.
3. **Answers:** an answer is the owner's current position.

v0.8.3 builds them, plus the full record check. Declaration `DECLARED_v0_8_3.json`
(`241924f7…`) was frozen before the harness was written.

Run: 47/48 tests and 40/41 mutants MATCH. Both mismatches come from one declaration
error: the T26 objector, a check-order misprediction (`DEVIATIONS_v0_8_3.md`). The tamper
is still refused and preserved; only the check that catches it moved.

Regression: every round-3 finding is refused on v0.8.3, and the corrected answer applies
and attests. The lineage probes are unchanged (`REGRESSION_*_v0_8_3.txt`).

Credit for the closed findings: ChatGPT (F1a, F1b, F2), the author (R19, corrected
answer). Grok: none this round.

## Round 4 — v0.8.3 candidate, 18 October 2026

Pack: `humble_seed_v0_8_3_candidate_BLIND.zip` (salted receipt commitment `0011a481…cf8e`).
No author findings were sealed this round; every known limit is disclosed in the docstring.

### Grok — complete, no findings

- **Execution verified.** Receipt `27214795…da59` matches the commitment. Exit code 1, 2
  MISMATCH lines. Python 3.10.21, cryptography 50.0.1. Every file in its archive matches the
  pack manifest.
- **Diagnosed both mismatches correctly and independently**, matching `DEVIATIONS_v0_8_3.md`
  E1. The new full record check refuses inside the replay on `prior_character_snapshot`
  before the final comparison is reached. XD4a loses T26 because T26 fails on the candidate.
  Grok called it "test brittleness". The harness checks the mechanism on purpose, so the
  author's reading is a declaration error; the substance is the same.
- Asserted the refusal is preserved, but did not check the other half (witness unchanged,
  state won't load, tamper kept as evidence). The author's diagnostic did.
- No probe code, although the README asked for runnable code behind every "no evidence of
  X" claim. Its account of the organism/owner disagreement matches R22.

### ChatGPT — sighted round (full pack, sent to get past its provider's guardrail)

ChatGPT received the full pack, with results, salts and the author's diagnoses, so this
round is **sighted**. A receipt match shows it ran the harness, not that its execution was
independent. Findings count as independent only when they were not in that pack.
In progress at the time of writing (`CHATGPT_round4_screenshot.png`):

- **Receipt reproduced; T26 diagnosis confirmed.** The diagnosis was in the pack.
- **Stale owner session attests over a "no"** (reported 09:19 CT). The author sealed the same
  root cause at 14:18:21Z (09:18 CT): owner sessions each hold their own copy of the ledger
  (`AUTHOR_FINDINGS_COMMITMENT_v0_8_3.txt`, A2). ChatGPT's form differs: an older session
  attests from its stale copy, and reload and audit pass. Whether it needs the organism to
  hide its own record (as A2 does) awaits its code. Credit: independent find; the author
  sealed first.
- **Sibling checkpoints from one parent (new, ChatGPT).** Two owner sessions, each with its
  own copy of the witness, attest two different sequence-1 successors of the same
  checkpoint. The last writer wins, and the witness then flags the earlier, legitimate
  branch as the fork. Reproduced by the author (`repro_chatgpt_r4_witness_fork.py`). The
  author had only an untested suspicion of this, stated in chat and not sealed, so full
  credit goes to ChatGPT.
- **Forged timestamps and notes pass attestation.** The author sealed this as A1 at
  14:18:21Z. Credit: independent find; the author sealed first.

Common cause: owner-side state (ledger and witness) is read once into memory and written
back whole, with no re-read and no lock. Every owner-side check-then-write needs to be one
atomic step.
- **Interrupted witness write strands the organism (new, ChatGPT).** `attest` installs the
  checkpoint on the organism, then records it at the witness. If it is interrupted between
  the two, the organism is one sequence ahead. Audit then reports "Unwitnessed advance";
  retrying attest, and every later attest, is refused as "Non-successor". Nothing crosses
  that shouldn't (fail-closed), but the organism can never be attested again by the normal
  paths. Reproduced by the author (`repro_chatgpt_r4_witness_interrupt.py`). The author had
  nothing on this. Full credit to ChatGPT.
- **Three metadata mutants survived the shipped tests** (reported). Not yet seen; awaits
  its archive.
- **"Reproduced results file is byte-for-byte identical to the shipped file"**: cannot hold
  for an independent run. RESULTS details carry random reading IDs, and the author's own
  two runs differ there; only the receipt is run-independent. In the full pack the harness
  overwrites `RESULTS_v0_8_3.json` in place, so the comparison was most likely of the file
  with itself. The receipt match stands; check the archive.

### ChatGPT — final archive (sighted round)

Archive: `review_round4_chatgpt/CHATGPT_review_archive_v0_8_3.zip`. It was built from the
exact zip delivered (sha256 `0f82d933…`). Python 3.12.14, cryptography 50.0.2. Receipt
matches. The author ran ChatGPT's own reproduction package
(`author_rerun_of_chatgpt_package/`): all nine probes and all three supplemental mutants
reproduce exactly.

The report is careful: it is labelled not-blind, includes three controls next to the
failure cases, and states limits for each finding.

- **F1 — stale owner sessions (root cause sealed by the author first, A2).** Three forms:
  - *veto bypass*: the stale session attests over the owner's durable "no". This form needs
    **no hidden organism record**: a forged "yes" (already in T47's threat model) defeats
    the organism-record veto. **Stronger than A2; credit ChatGPT.**
  - *signature erased*: the same as A2's lost write. Independent find.
  - *lifetime refreshed* (**new, ChatGPT**): a stale session re-signs the same payload, and
    the "first signing" time moves later. This is the control the declaration listed as
    "not exercised".
- **F2 — stale witnesses issue sibling checkpoints** (new, ChatGPT; reproduced).
- **F3 — unvalidated metadata.** `authorized_at` and `note` were sealed by the author first
  (A1). ChatGPT adds the outer event timestamp, which is not bound to the record, and
  **three surviving mutants (XM1–XM3)**: a real coverage gap. Credit ChatGPT for the
  mutants and the event timestamp.
- **F4 — interrupted witness write strands the organism** (new, ChatGPT; reproduced).

**One error.** The "byte-identical RESULTS" claim does not hold. ChatGPT's
`RESULTS_v0_8_3_reproduced.json` carries the author's run's random reading IDs and equals
the shipped file (`16bc306e…`). The author's own runs, and ChatGPT's own wrapper run here,
produce different files (`2affc782…`, `b2524c16…`). Only the receipt is run-independent.
The archived file was most likely captured from the shipped copy rather than a fresh run.
The findings do not depend on it.

## Disposition of round 4

- Grok: verified execution, diagnosed the mismatches correctly, no findings.
- ChatGPT: four finding groups (F1–F4) and three surviving mutants, all reproduced; one
  evidence-handling error.

The common cause of F1, F2 and F4: owner-side state (ledger, witness) has no single
serialized, durable authority, and the checkpoint commit spans two stores with no recovery.

Scope for v0.8.4:
1. One serialized owner authority. Lock, re-read, check, write as one step, for both the
   ledger and the witness; or enforce a single owner instance.
2. A recoverable checkpoint commit.
3. Field provenance: validate `authorized_at` and the event timestamp as finite and agreeing;
   treat `note` as an untrusted organism annotation.
4. Tests for all nine probes and XM1–XM3.
5. Correct T26 and XD4a in the next declaration.

### v0.8.4 result (built from the round-4 disposition)

Declaration `DECLARED_v0_8_4.json` (`8db3ffdb…`) was frozen before the harness was written.
Run: **56/56 tests MATCH**, including the corrected T26 and ChatGPT's nine round-4 cases.
**52/54 mutants MATCH**, including ChatGPT's XM1–XM3, which survived v0.8.3 and are now
killed.

The two mismatches are test-design errors in the author's new tests
(`DEVIATIONS_v0_8_4.md`):
- T56's lock probe only runs inside the replay, so XD4a kills it spuriously.
- T53 signs off from the original session, so the ledger re-read mutant is invisible to it.

A diagnostic shows the candidate refuses ChatGPT's lifetime case from a fresh session,
where the mutant accepts it.

Regression: ChatGPT's round-4 probes, run unchanged on v0.8.4, now fail to reproduce
their attacks. The veto bypass, lifetime refresh and fork are refused, and the signature
survives. Two probes no longer fit the interface and were adapted minimally; both
outcomes are refused or recovered. All earlier probes behave as on v0.8.3 or better. The
lineage probes are unchanged.

## Round 5 — v0.8.4 candidate, 18 October 2026

Pack: `humble_seed_v0_8_4_candidate_BLIND.zip` (sha256 `93bd2969…`; salted receipt
commitment `a2fa3efa…41db`). No author findings sealed. The author's own run of the
uploaded pack gives the same receipt.

### Grok — complete, no findings

- **Execution verified, and this time provably its own run.** Receipt `22327877…b394`
  matches the commitment. Its RESULTS file carries reading IDs different from the
  author's, so it is a fresh run, not a copy. Python 3.10.21, cryptography 50.0.1.
  Archive files match the pack manifest.
- **Both mismatches diagnosed correctly and independently.** The blind pack had no
  deviation file. Its diagnoses:
  - XD4a's T56 kill is "incidental": the clock probe runs only inside `verify_consequence`.
  - T53 survives XS2 because the attesting session keeps its own correct `signed_at`.

  Both match `DEVIATIONS_v0_8_4.md` E1 and E2. It did not note that a fresh session would
  expose XS2 (the author's diagnostic).
- No new findings. "No evidence" claims again come without probe code, despite the
  README's request: the third round running.

### ChatGPT — complete, BLIND (no guardrail block this round)

- **Execution verified.** It ran the exact delivered zip (sha256 `93bd2969…`). Receipt
  `22327877…b394` matches the commitment. Python 3.12.14, cryptography 50.0.2, 48 s.
- **Both mismatches diagnosed correctly, with extra evidence:**
  - Under XD4a, a direct flock probe from `witness.begin` reads "locked", so the T56 kill is
    a missing observation, not lost serialization.
  - For XS2, the fresh-session comparison: the candidate refuses, the mutant accepts.

  This matches the author's diagnostic, reached independently; the blind pack had no
  deviation file.
- The author ran its scripts here (`author_rerun_*.json`). All findings reproduce.
- **F1 — category "no" bypassed before signing (new; refutes the narrowness of R22).**
  1. Readings X and Y are issued.
  2. The owner answers Y "no" through the tool.
  3. A "yes" to Y is forged on the organism only.
  4. The owner signs X, which is applied and attested; a restart audit passes.

  The owner side counts category answers only after its signature, so the earlier "no" is
  outside its window. The forged "yes" clears the organism-record veto. R22 said this
  needed the organism to *hide* its record; a forged "yes" is enough.
  **Credit ChatGPT.**
- **F2 — recovery commits a checkpoint that exists only in memory (new).**
  `install_checkpoint` assigns the checkpoint, then the save fails. Recovery on the same
  object treats it as installed and advances the witness, leaving the witness ahead of disk:
  stranded. **Credit ChatGPT.**
- **F3 — a stale organism object abandons an installed intent (new).** The durable install
  happened; audit called with an old object sees "at head", drops the intent, and strands
  the real state. **Credit ChatGPT.**
- **F4 — a 2001-character annotation applies but can never be attested (new).** Apply does
  not validate what replay refuses, so a valid crossing is stranded. **Credit ChatGPT.**
- **F5 — XP1's kill is a refusal-message change (confirmation).** The declaration already
  predicted this as a mechanism kill. ChatGPT's added point is fair: with the window check
  still refusing, XP1 does not remove the protection its name says it removes.

## Disposition of round 5

- Grok: verified execution and a correct diagnosis, no findings.
- ChatGPT: four new findings (F1–F4) and one confirmation.

Common cause of F2/F3: recovery trusts the organism object handed to it, not the
organism's durable state. F4: apply and replay validate differently. F1: the owner-side
answer window has no owner-verifiable start.

Scope for v0.8.5:
1. Recovery resolves against the organism's durable state, re-read under the owner lock.
   `install_checkpoint` changes nothing in memory unless its save succeeds.
2. Apply refuses anything replay would refuse, before changing any state.
3. An owner-verifiable category window, starting from the last attested crossing in that
   category (from the owner's own records), not from signing.
4. Fix T53 (sign off from a fresh session) and T56 (probe the lock outside the replay).
   Rename XP1 to what it actually removes.

## Correction (author, on rereading the thread, 2026-10-18)

**A1 and A2 were not independent finds. Credit for both goes to ChatGPT.**

The author sealed A1 (unchecked `authorized_at`/`note`) and A2 (stale owner sessions) at
14:18:21Z. That was *after* ChatGPT's in-progress screen (09:16 CT) announced exactly those
two lines of attack: "whether repeated owner sessions preserve the new ledger guarantees"
and "whether the replay check validates all the record fields it claims to validate". The
author's probes tested hypotheses ChatGPT had already stated. The seal proves when the
author's probes ran. It does not prove they were independent.

Every "sealed first" or "author A1/A2" credit for round 4 is withdrawn: in this log, the
v0.8.4 README, the v0.8.4 docstring and the v0.8.4 declaration. The last two are frozen and
are left as they are; the correction is recorded here and carried into the next version.

The other author credits stand:
- R19 was sealed in v0.8.2, before either reviewer saw the pack.
- The corrected-answer finding came from rereading Grok's round-3 claim, before ChatGPT
  reported.

### v0.8.5 result (built from the round-5 disposition, 2026-10-19)

The declaration `DECLARED_v0_8_5.json` (`ddd6fbd2…`, 12:27:12Z) was frozen before the harness
was written.

**Scope as planned:**
1. Recovery from the organism's saved state, and an in-memory rollback in `install_checkpoint`.
2. Apply refuses whatever replay refuses.
3. An owner-verifiable category window.
4. T53 and T56 corrected, and XP1 renamed. XP1b was added, removing the protection itself.

**Item 3 was refined during the build.** The window starts at the owner's own signature of the
previous crossing in the category, not at its last attested crossing. This needs no new owner
state, and it is never later than the planned boundary, so it holds at least as often.

**Run:** 60/61 tests MATCH, 58/61 mutants MATCH (`DEVIATIONS_v0_8_5.md`).
- **One declaration error (E1):** T57 predicted the wrong refusal message. The candidate refuses
  correctly, but through the category-sequence check, which comes first. That one error accounts
  for all four mismatches: T57 itself, X10, XR2 and XR4.
- **The unscored diagnostic** reruns T57 with only the message expectation corrected. The
  candidate passes every remaining assertion, and XR4 and XR2 are killed as declared.
- **One mispredicted mechanism (E2):** X10 would not be killed by T57 even with the correct
  message.
- **Both v0.8.4 deviations are fixed:** XD4a no longer kills T56, and XS2 is killed by T53.

**Regression:**
- **ChatGPT's round-5 sequences, same steps, on v0.8.5:**
  - F2: object, disk and witness stay at 0; audit refuses the unattested state; the retry attests.
  - F3: the stale object is refused, and the intent is completed from the saved state.
  - F4: the 2001-character annotation is refused at apply; the reading stays pending.
  - F1: attestation is refused ("owner's position").
- **Earlier suites:** ChatGPT's adapted round-4 probes and the lineage probes behave exactly as on
  v0.8.4.

**Author findings:** sealed before any reviewer has seen v0.8.5
(`AUTHOR_FINDINGS_COMMITMENT_v0_8_5.txt`, `1f4c8b1d…`, 12:34Z). The text and salt are released
after round 6 reports.

## Round 6 — v0.8.5 candidate, 19 October 2026

**Pack:** `humble_seed_v0_8_5_candidate_BLIND.zip` (`9f317d6f…`). It carried a salted receipt
commitment (`9348f503…`) and the author's sealed findings (`1f4c8b1d…`, sealed 12:34Z).
Both seals were opened after the two reports (`SEALS_OPENED_v0_8_5.txt`), and both verify.

**Receipt `22d9e8eb…`:** identical in four runs (the author, the author's clean copy, Grok and
ChatGPT) across Python 3.10, 3.12 and 3.13.

### Grok — complete, no findings

Grok diagnosed all four mismatches correctly as one root cause (E1). It noted that a plain
unattested apply hits the same error first. It did not catch E2.

### ChatGPT — complete, BLIND (no guardrail block)

- **Run:** all four mismatches diagnosed, including E2, which ChatGPT found independently; the
  author's E2 was recorded in DEVIATIONS, which was not in the blind pack.
- **Full diagnostic battery** with only T57's message corrected: 61/61 tests, 1 mismatch
  (X10's set). Diagnostic receipt `e72f4c9a…`, labelled as not the frozen one.
- **F1 (high): a stale organism object's ordinary save erases newer saved state.**
  `_save` has no saved-generation check and no organism lock. Three schedules:
  - **Sequential:** the witness detects the rollback; availability is lost.
  - **During attest:** attest returns True, yet the saved state is left behind the witness.
  - **Interrupted commit, then a stale write:** recovery sees the witness head on disk and
    abandons the intent. Audit then passes at the old state, and the saved, signed-off change
    is lost silently.

  The sequential case also reproduces on v0.8.4. **Credit ChatGPT.**
- **F2 (medium): a failure after the replace leaves memory behind disk.** `install_checkpoint`
  rolls back on any save exception, including a directory-fsync failure after `os.replace`, so
  the checkpoint is on disk but not in memory. Recovery completes it from disk correctly, but
  the same object's retry is refused until it reloads. This was introduced by v0.8.5's change
  V. **Credit ChatGPT.**
- **Coverage:** it exercised both of recovery's refusal paths (unreadable saved state; neither
  match). The declaration had listed both as not exercised.
- **Reproduction:** the author reran all nine of ChatGPT's probe functions on a copy of the
  archive (`author_rerun_probes.txt`). All reproduce with ChatGPT's own assertions holding.

### Author findings, opened

| | Finding | Status |
|---|---|---|
| **A1** (low) | Recovery completes an intent from a saved file that does not load (forged content plus the copied pending checkpoint). | Not reported by either reviewer. |
| **A2** (cosmetic) | The owner's refusal text contradicts itself. | Not reported. |
| **A3** (note) | Apply re-verifies the whole trace chain each time: 8.6 ms at 2000 entries. | Not reported. |
| P1, P3 | Confirmations | ChatGPT's `window_orderings` independently matches P1. |

**A1 and F1 share a root.** The saved file is recovery's trust source, but there is no write
protocol that protects or verifies it. Their triggers differ (tampering versus benign stale
writes), and so does their direction (wrongly completing versus wrongly abandoning). Credit is
separate: A1 to the author, sealed before any report; F1 to ChatGPT.

### Disposition of round 6

The common cause of F1, F2 and A1 is that the organism's saved file has many writers, no
protocol, and recovery trusts it.

**Scope for v0.8.6:**
1. **One organism persistence protocol.**
   - An organism lock, and a saved generation counter checked on every save.
   - A stale object cannot write; it must reload.
   - attest takes the organism lock across install and witness commit.
2. **Indeterminate saves are resolved, not assumed.** After a save exception, re-read the saved
   generation and sync memory to what is actually on disk (F2).
3. **Recovery treats an intent as installed only if the saved state loads and verifies** (A1).
4. **Declaration and wording:** T57 expects "Category sequences do not match the attested
   checkpoint"; X10 = {T22}; the owner's refusal text gets its own window wording (A2).
5. **Tests:** ChatGPT's three F1 schedules, the post-replace failure (F2), and A1's forged file.

## Correction (author, on rereading the thread, 2026-10-19)

1. **"All four round-5 findings are closed" was too broad.**
   - The reported sequences are closed. But F3's outcome, an installed sign-off abandoned and
     the approved change lost, is still reachable another way: through a stale write
     (ChatGPT r6 F1, third schedule).
   - v0.8.5 moved recovery's trust from the object to the saved file. Nothing protects that
     file from the same stale objects.
   - The round-6 summary's "v0.8.5's four fixes hold up" carries the same overstatement.
2. **R30 covered only one direction.**
   - It said a bad saved file can at worst make recovery *complete* an owner-approved
     checkpoint. My sealed A1 probe tested only that direction too.
   - The mirror case is a saved file rewound so that recovery *abandons* an installed intent.
     ChatGPT found it with an ordinary write, no forgery needed.
3. **I introduced F2 myself.**
   - v0.8.5's rollback assumes a failed save wrote nothing.
   - `_durable_write`, which I wrote in v0.8.4, replaces the file before the directory fsync,
     so a failure can come after the new state is already on disk.
   - v0.8.4 kept memory at the new checkpoint and had no such gap.
4. **A recurring prediction error: which check fires first.** This is the third time a
   declared refusal fired through an earlier check (T26 in v0.8.3; T57 and X10 here).
   - I had read `_verify_attestation` during the build: the category-sequence check (line 820)
     precedes the unattested-tail check (line 842).
   - **Process fix for v0.8.6:** before freezing, trace the check order for every declared
     refusal message, and record the traced line in the declaration.
5. **Smaller points.**
   - W's docstring says the previous crossing's signature "precedes this reading's issuance".
     That is true for an honest organism. The window property holds without that assumption,
     because the previous crossing's own check covers any gap, but the docstring argues it the
     wrong way.
   - My probes P1 and P2 were each fixed before sealing: P1's name overstated it, and P2 first
     audited an unloaded object, then loaded at the wrong point. The sealed text describes only
     the final versions.
