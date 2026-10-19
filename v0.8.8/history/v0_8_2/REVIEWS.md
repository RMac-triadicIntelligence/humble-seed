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
