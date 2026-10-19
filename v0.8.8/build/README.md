# Build scripts (as run)

- `make_candidate_088.py <v0.8.7 candidate> <out>`: derives the v0.8.8 candidate by exact-once edits.
- `make_declared_088.py <dir>`: writes and freezes `DECLARED_v0_8_8.json`. It refuses if the harness or a
  declaration already exists, and if any KILLED mutant's `killer` is outside its exact kill set.
  `FREEZE_v0_8_8.log` is its output.
- `make_harness_088.py <v0.8.7 harness> <out>`: derives `falsify_v0_8_8.py`. It was run after the freeze.
- `run_regression_088.sh`: the unscored regression run. Its paths are the author's working paths.
- `make_release_088.py`: assembles this release. Its paths are the author's working paths.
