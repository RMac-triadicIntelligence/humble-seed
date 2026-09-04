# Source provenance

[`sources.json`](sources.json) maps each of the ten uploaded filenames to its
repository path, byte size, and SHA-256 digest. All ten files retain their exact
uploaded bytes. Paths and filenames were normalized; source contents were not
edited.

```bash
python tools/verify_sources.py
```

The hashes verify preservation relative to the supplied files. They do not
establish earlier publication dates or historical authorship. Both v0.6
variants are retained, and their relative historical order is left unspecified.

The README, runner, example, tests, packaging metadata, workflow, and other
documentation were added during this repository assembly. Package version
`0.6.0` refers to that assembly, not a new behavioral revision of either kernel.
