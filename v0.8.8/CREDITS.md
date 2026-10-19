# Credits

The full, dated record, including corrections to earlier credit, is `REVIEWS.md`. This page
summarizes it. A reviewer result that matches a finding the author had sealed earlier is
credited to the reviewer as an independent find; where the reviewer found it first, the
credit is theirs alone.

## Direction and rulings

**Rusty McMurray (Soulshine, Tulsa, OK).** Directed the work, set the review process, and
made or delegated every design ruling. These include:
- the three rulings for v0.8.3, delegated to Claude on 2026-10-18;
- R20, "Restore from last signed off state", on 2026-10-19;
- the decision that v0.8.8 is the final revision before publication.

## Author

**Claude** (Anthropic; Opus 5.5 sessions). Wrote every candidate, frozen declaration,
harness and README, and ran every scored run. The author's own findings include:
- **Round 2:** a one-hour reading lifetime; `1e999` parsing to infinity.
- **Round 3:** R19, the owner replay not checking lifetimes; a corrected answer that could
  not release a hold.
- **T61's later-crossing case.**
- **The sealed post-freeze findings of rounds 6–8.** Among them:
  - recovery completing from a saved file that does not verify;
  - restore forgetting the owner's answers;
  - the callback lock-order deadlock (ChatGPT found it independently);
  - the symlinked-path self-deadlock.
- **v0.8.8's post-freeze findings**, in `AUTHOR_FINDINGS_v0_8_8.md`.

The author's round-4 credits were withdrawn on rereading; `REVIEWS.md` explains why. Every
declaration error is the author's, and each is recorded in that version's `DEVIATIONS` file.

## Reviewers

**ChatGPT (OpenAI).** Found most of the defects fixed in this line, by a wide margin. Its
provider's guardrail blocked it in rounds 1, 3, 4 and 7. Rounds 7 and 8 went through a
run-only pack and a claims battery instead.
- **Round 2:**
  - #1, NaN readings cross;
  - #2, policy outside the constitution;
  - #3, attestation sealed an unsigned change;
  - #4, T5 checked names, not values;
  - #5, crashes counted as kills;
  - two observations;
  - mutants X5b and XH.
- **Round 3** (reproduced by the author from ChatGPT's interrupted description):
  - F1a, an expired reading attested (the author's sealed R19, found independently);
  - F1b, a held reading attested;
  - F2, a false consequence.
- **Round 4:**
  - F1–F4: a stale-session veto bypass, sibling checkpoints, unchecked metadata, and an
    interrupted witness write;
  - A1 and A2, by priority (see the correction in `REVIEWS.md`);
  - mutants XM1–XM3.
- **Round 5:** F1–F5. These were recovery trusting the object, a checkpoint only in memory,
  apply accepting what replay refuses, and a hidden "no" before signing.
- **Round 6:** F1, a stale object's save erased newer state; F2, a failure after the
  replace.
- **Round 7:**
  - F1, one object used from two threads: a lost update, or a rewound sign-off (high);
  - F2, a double fault;
  - F3, a stale object took the answer into memory.
- **Round 8:**
  - F1, a dead end after a failed commit;
  - F2 and F3, same-thread re-entry into a save;
  - F4, an interrupt during the re-read;
  - two docstring errors;
  - the lock-order deadlock, independently;
  - the correct diagnosis of v0.8.7's E1.

**Grok (xAI).**
- **Round 1:** two real findings. The unattested-tail check was reachable (T22), and the
  prior-value check was not redundant (T21; it refuted R11).
- **Rounds 2–8:** independent execution checks that reproduced every receipt across Python
  versions.
- **Round 8:** a design note on refusing reentrant cross-object writes. It points in the
  direction of v0.8.8's E2.
- Several Grok rounds returned all-clears that were later shown false. In rounds 7 and 8, its
  claims-battery verdicts were fixed in code rather than computed from runs. `REVIEWS.md`
  records both.

## Prior work

v0.7, "Canonical Converged Constitutional Core" (`parent_humble_seed_v0_7_C5.py`), merged two
independently implemented v0.6 revisions. The lineage before v0.8 is not part of this release.
