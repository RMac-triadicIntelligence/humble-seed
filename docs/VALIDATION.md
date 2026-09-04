# Validation record

Repository assembly date: **2026-09-02**.

Local environment: Linux, Python **3.12.13**, `cryptography` **46.0.0**.
Identities, key pairs, timestamps, and hashes are generated afresh on each run;
those values will differ across runs.

## Results

| Check | Observed result |
| --- | --- |
| SHA-256 comparison against the ten uploads | All ten mapped source files are byte-identical. |
| Supplied scripts in their matching environments | All ten complete with exit code 0. |
| Supplied primary-v0.6 assertion suite | All five printed regression groups pass. |
| Added `unittest` suite | 18 tests pass. |
| New owner-authorization walkthrough | Proposes without changing character, then authorizes, attests, reloads, and passes witness audit. |
| Isolated runner | All eleven targets complete with exit code 0; pre-existing output directories are refused. |

See the [captured script outputs](../validation/README.md). Package installation
and import results are recorded in [installation.txt](../validation/installation.txt).

## Assertion coverage

The supplied `probe6_validation.py` asserts first-commit truthfulness, attested
gates, genesis/constitution rebinding rejection, the unique birth trace, and
witness rejection of wrong-parent, skipped-sequence, and foreign-genesis
checkpoints.

The added suite exercises the primary implementation's authorized lifecycle,
ambiguous-input dwelling, invalid and foreign signatures, evidence/distribution
substitution, proposal expiry, stale proposals, replay, category/value
validation, character forgery under a recomputed seal, the apply-before-attest
window, and externally detected rollback.

It also explicitly records two remaining limitations as expected behavior:
rolling back both local files can pass a fresh witness audit, and fabricated
non-authorizing history/pre-proposal evidence can load without changing
attested character. These passing checks confirm that the limitations remain.

The repository suite also invokes the supplied assertion probe and checks
that the runner refuses an existing output directory without overwriting it.

## Read the original probe output carefully

`probe4.py`, `probe5.py`, `probe6.py`, and `triage6.py` are primarily
print-based observations. They can return exit code 0 even when they print a
finding. The built-in demonstrations mix printed expectations and assertions.
Their successful execution is reported separately from assertion results.

Three source details are preserved and documented:

1. **v0.4 O1 control is incomplete.** `probe4.py` reconstructs a temporary seed
   to recompute the seal but omits `first_commit_pending`. Its output therefore
   rejects the attempted forge for a seal mismatch. This does not establish
   that an unkeyed seal resists a complete resealing attack; the kernel's own
   stated O1 limitation remains.
2. **The triage G5 message is static and outdated.** It prints
   `no explicit check in verify()` even though its matching alternative v0.6
   does contain birth-trace checks. That string is not a measured result.
   Its G3 attempt is rejected at the birth-trace check, and its G4 attempt
   uses a sequence jump, so neither alone isolates the deeper checkpoint-root
   or wrong-parent control. The alternative kernel's built-in demo exercises
   a rechained constitution attack and an immediate wrong-parent successor.
3. **`probe6.py` still calls itself a v0.5 probe in its docstring.** Its imports
   and `check_current()` call target the alternative v0.6 interface. The runner
   pairs it using the actual API.

No supplied script was rewritten to alter an observation or manufacture a
passing result.

## Reproduce

```bash
python tools/verify_sources.py
python -m unittest discover -s tests -v
python run.py all --output-dir runs/review-001
```

The output directory must be new. Running `python run.py all` without an output
path uses temporary directories and removes them afterward. The runner starts
children with Python's isolated mode so `PYTHONOPTIMIZE` does not silently
disable the supplied assertions.

GitHub Actions is configured for Python 3.10, 3.12, and 3.13 on Ubuntu. Those
remote matrix jobs have **not** run as part of this local assembly. The workflow
uses the versions documented by
[actions/checkout](https://github.com/actions/checkout) and
[actions/setup-python](https://github.com/actions/setup-python).

This is packaging and behavioral validation of the supplied prototypes. It
does not establish a comprehensive security audit or a general scientific
result about intelligence.
