# Contributing

Start with [the version map](docs/VERSIONS.md) and
[validation record](docs/VALIDATION.md). Use an isolated environment:

```bash
python -m pip install -r requirements.txt
python tools/verify_sources.py
python -m unittest discover -s tests -v
python run.py all
```

The ten files in `provenance/sources.json` are preserved source snapshots.
For a behavioral change, retain the relevant original and introduce an
explicit new version or implementation path. Add matching assertions and
document any state-schema or witness-interface change. Updating a recorded
hash alone would erase the evidence that a snapshot changed.

Probe improvements should assert observable outcomes, identify the intended
control, and demonstrate that the setup reaches that control. Use fresh
temporary directories, keep private material out of logs, and report known
residual behaviors separately from regressions.

Package version `0.6.0` labels this repository assembly. It does not create a
historical ordering between the two supplied v0.6 variants.

The project's reuse license is still undecided; see
[LICENSE_STATUS.md](LICENSE_STATUS.md).
