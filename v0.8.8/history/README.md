# History: every earlier v0.8 version

Each folder is that version's working directory as frozen and scored: its candidate, frozen declaration,
harness, results, stdout, deviations (from v0.8.3 on, plus v0.8's `DEVIATIONS.md`), author probes and
findings, opened seals, regression outputs and README. Run a harness from inside its folder, for example
`cd v0_8_6 && python3 -I falsify_v0_8_6.py`. Each `REVIEWS.md` is the log as it stood at that version;
the cumulative log is `../REVIEWS.md`.

Omitted:
- the `v0_8_X_record/` copies of the previous version, since each has its own folder here. The exception
  is v0.8.1's `v0_8_record/humble_seed_v0_8_candidate.py`, which its T0 needs;
- review archives and screenshots, which are in `../reviews/`.

Some author probes and adapters refer to a previous version's record folder or to the author's working
paths. Their outputs are kept as they were produced.
