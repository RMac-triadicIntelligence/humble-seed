# Humble Seed v0.8.4 CANDIDATE

Soulshine (Tulsa, OK) · 18 October 2026 · built by Claude at Rusty McMurray's direction.
**Candidate, not canonical.** It carries v0.8.3's three rulings, which Rusty delegated to
Claude.

## What changed

Round 4 showed that your owner-side record wasn't one authority. Every owner session
worked from its own copy, and signing off a checkpoint wrote to two places with no way to
recover. v0.8.4 fixes both, and tightens the change record.

| | Change | Closes |
|---|---|---|
| **S** | Every owner operation (sign, answer, attest, audit, and every ledger or witness call) runs under **one exclusive lock**. It **re-reads** the ledger and witness from disk before checking or writing. Writes are atomic and fsynced. | Stale-session veto bypass, erased signature, refreshed lifetime (ChatGPT F1; my sealed A2); sibling checkpoints (ChatGPT F2) |
| **R** | Sign-off is recoverable. The witness records a durable intent, the organism installs, then the witness advances. Sign-off and audit first finish an intent the organism already installed, or drop one it never did. | Interrupted witness write strands the organism (ChatGPT F4) |
| **P** | The change record's metadata is checked. `authorized_at` must be a finite number, inside the reading's own window, and equal to the event's timestamp. The free-text `note` becomes `unverified_annotation`: the organism's words, never yours, and a short string. | Unchecked timestamps and notes (ChatGPT F3; my sealed A1); ChatGPT's surviving mutants XM1–XM3 |
| T26 | The refusal names the changed category ("formality: recorded 0.99, replay 0.5"), and T26 now predicts the right check. | v0.8.3 deviation E1 |

## Result (scored as frozen)

- Declaration frozen before the harness: `DECLARED_v0_8_4.json` (`8db3ffdb…`,
  2026-10-18T14:35:34Z). Mutants are inside it. Before the freeze: one basic smoke run and
  anchor checks only; no multi-session, recovery or lock path had run.
- **Tests: 56/56 MATCH.**
- **Mutants: 52/54 MATCH.** Both misses are my test-design errors (`DEVIATIONS_v0_8_4.md`):
  - **XD4a also killed T56, for the wrong reason.** T56 checks the lock by probing it from
    another process when the owner's clock is read, and that only happens inside the
    replay. Remove the replay and the probe never runs.
  - **XS2 (no re-read) didn't kill T53.** T53 signs off from the original session, which
    still holds the correct first-signing time. Signed off from a fresh session, the
    candidate refuses and the mutant accepts (`DIAGNOSTIC_T53_XS2_v0_8_4.txt`).
- **Kill reasons:** every other kill is for the predicted reason. XP1 is a declared
  mechanism kill. The crash-only mutant XH is CRASHED, not killed.
- Receipt `22327877…b394`, identical from a clean copy. Exit code 1 (the two deviations).

## Regression

- **ChatGPT's round-4 probes, run unchanged on v0.8.4:** the attacks no longer reproduce.
  - stale-session veto bypass: refused ("owner's position");
  - lifetime refresh: refused;
  - sibling checkpoint: refused ("Non-successor");
  - erased signature: the signature survives.
- **Two probes no longer fit the new interface**, so I adapted them minimally:
  - forged metadata: refused;
  - a witness write failing at the intent: the retry succeeds;
  - a witness write failing at the commit: a reopened audit completes it.
- My sealed A1/A2 probes are refused. All earlier probes behave as on v0.8.3. The lineage
  probes are unchanged.

## Limits worth knowing

- **R1 (revised).** The lock is advisory. Only owner tools that take it are serialized; a
  process editing the files directly is not. This is still not a TPM, HSM or notary.
- **R26.** POSIX flock: Linux and macOS only, and unreliable on some network
  filesystems.
- **R27.** An interrupted sign-off blocks new checkpoints for that organism until attest
  or audit runs and recovers it.
- **R20.** A change not signed off within its reading's lifetime still can't be signed
  off, and there's no built way back to the last good state.
- **Runtime** is now ~100 s, mostly T56's subprocess probes and fsync.

## Run

```
python3 -I falsify_v0_8_4.py     # ~100 s; exits 1 (two recorded deviations)
```

## Still open

- Fix T56 and T53 in the next freeze.
- T20 covers only signing in issue order.
- R3 (the keyword interpreter) and the limits in the candidate's docstring.
- Next blind round: send `humble_seed_v0_8_4_candidate_BLIND.zip`; withhold
  `RECEIPT_SALT_AND_VALUE_v0_8_4.txt`. No author findings were sealed this round. All known
  limits are in the docstring, and both deviations show in the run.
