# Deviations — written after run 1, nothing frozen was changed

DECLARED.json (3aeaf805…, frozen 2026-10-17T14:31:29Z) is scored exactly as frozen.
Run 1: 19/20 tests MATCH, 10/10 mutants MATCH, **1 mismatch**. Exit code 1. Not re-scored.

## E1 — T17: right property, wrong declared objector (declaration error, mine)

T17 declared that loading an applied-but-unattested state raises IntegrityError
containing "Unattested authorizing event". It does fail closed, but the objector is
**"Category sequences do not match the attested checkpoint"**.

Cause: `_verify_attestation` compares the attested roots (birth, constitution, gates,
character, …) before it walks the unattested trace tail. An authorized mutation
advances `category_sequence`, so the gates root mismatches first. The parent v0.7
had the same ordering (its first-commit gates root flips first). I declared the
tail check from memory of the v0.5 docstring without tracing the check order.

Reading: the fail-closed property (R6) holds; the declaration named the wrong line of
defence. This is recurring bug #1 in miniature: a verdict about *which* check fires,
written without a code path that computed it. Left as a FAIL in the record.

## E2 — the definition of "killed" was not in DECLARED.json

The harness counts a mutant as KILLED when a test that PASSES on the candidate FAILS on
the mutant (the standard mutation-testing definition). DECLARED.json did not state it.
It matters here only because T17 fails on the candidate, so T17 is excluded from every
mutant's kill set. No mutant's verdict depends on T17.

## Observation, not a deviation

X3 (category-sequence check removed) was killed by T3 as well as the declared killer T4:
with the sequence check gone, the prior-value check still rejects in T3 but under a
different reason, which T3's declared substring catches. T4 is the case where the value
does not change (clamp floor), so only the sequence check can object there.
