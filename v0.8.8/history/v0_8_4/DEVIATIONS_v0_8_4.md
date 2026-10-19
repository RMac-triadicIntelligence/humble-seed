# Deviations from DECLARED_v0_8_4.json (scored as frozen; not re-scored)

Scored run: 56/56 tests and 52/54 mutants MATCH. Both mismatches are test-design errors in
the author's new tests. Neither is a candidate defect.

## E1 — XD4a also kills T56 (a spurious kill)

- **Declared exact set:** T26, T39, T41–T44, T46–T49, T52, T53.
- **Measured:** the same plus T56.
- **Cause:** T56 probes the owner lock from another process when attest calls the owner's
  clock. In attest, the clock is called only inside `verify_consequence`. XD4a removes that
  call, so the probe never runs (`seen = []`), and T56 fails although the lock is held as
  before.
- **What it means:** a kill for the wrong reason, the thing round 1's discipline rule is
  there to catch. T56 is coupled to the replay path.
- **Correction (next freeze):** probe the lock from a hook outside the replay, for example
  around `witness.begin`.

## E2 — XS2 does not kill T53 (a missed kill)

- **Declared exact set:** T49, T50, T53.
- **Measured:** T49, T50.
- **Cause:** T53 signs off from the original session. With re-reading disabled, that session
  keeps its own correct copy of the first signing time. The stale session's overwrite reaches
  the file, but only a session that re-reads the file would act on it.
- **Diagnostic, not scored** (`diagnostic_T53_XS2_v0_8_4.py` →
  `DIAGNOSTIC_T53_XS2_v0_8_4.txt`). This is ChatGPT's case with a **fresh** session signing
  off. The candidate refuses ("past its lifetime by the owner's clock"); the XS2 mutant
  accepts. The control is detectable; T53 as written does not detect it.
- **Correction (next freeze):** T53 signs off from a freshly opened session.

## Noted, not deviations

- XM1–XM3 and XL7 each make T54 and T55 **error**: those tests call attest expecting only
  the injected OSError, so an AttestationRefused surfaces as a crash. These mutants
  declared a killer only, so this is not scored. They are KILLED by assertion failures
  elsewhere (30 and 29 tests).
- Runtime rose to ~100 s, mostly T56's subprocess probes and fsync, run across 55 suites.
