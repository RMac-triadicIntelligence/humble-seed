# Humble Seed

**A seed can propose its own growth. Its owner must authorize the change.**

Humble Seed is a Python research prototype within **Raised, Not Rented**, led by
Rusty W. McMurray. It explores persistent state, provisional evidence, signed
change proposals, owner-attested checkpoints, and an external witness that can
detect a rollback of the organism's state.

This repository preserves all **ten supplied files**, including v0.3, v0.4,
v0.5, and **two distinct v0.6 implementations**. Their code is unchanged. It adds
installation metadata, an isolated runner, a worked example, integration tests,
documentation, and GitHub Actions.

The default module is
[`humble_seed_v0_6.py`](humble_seed_v0_6.py), **Constitution-Bound State and Linear
Witness**. It matches the supplied assertion-based validation suite. The other
v0.6 implementation has its own directory and matching probes. See
[version and interface mapping](docs/VERSIONS.md).

## Start here

For uploading this package to GitHub, follow [START_HERE.md](START_HERE.md).

Use **Python 3.10 or newer**. Local validation used Python 3.12.13 and
`cryptography` 46.0.0. From the repository directory:

```bash
python -m venv .venv
```

Activate the environment on macOS/Linux:

```bash
source .venv/bin/activate
```

Or in Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install the dependency and run the short walkthrough:

```bash
python -m pip install -r requirements.txt
python run.py example
```

Expected walkthrough:

```text
Proposal issued; verbosity is still 0.5
First commitment in this category: True
Authorized and attested: verbosity 0.5 -> 0.25
Mutation sequence: 1
Reload and external witness audit succeeded.
```

The examples use local files and generated test identities. Running them makes
no model API calls and requires no API key.

## Run and validate

| Command | Purpose |
| --- | --- |
| `python run.py demo` | Run the primary v0.6 demonstration. |
| `python run.py validate` | Run the supplied v0.6 assertion suite. |
| `python -m unittest discover -s tests -v` | Run 18 integration and repository checks. |
| `python run.py all` | Run all ten supplied scripts plus the new walkthrough. |
| `python run.py list` | List individual historical and alternative targets. |
| `python tools/verify_sources.py` | Verify all ten original SHA-256 hashes. |

The runner puts each script in a separate temporary working directory and
selects its matching module. To retain demonstration logs and data, use a new
directory:

```bash
python run.py all --output-dir runs/first-review
```

Existing output directories are refused. The short `example` always removes
its own temporary identity; its printed log can still be retained.

Several original scripts print observations without asserting them. A clean
process exit means the script ran; interpret its results using
[VALIDATION.md](docs/VALIDATION.md). The assertion suite and integration tests
provide explicit failure signals.

## What the prototype does

The default state has three numeric traits: `verbosity`, `formality`, and
`curiosity`. A fixed keyword interpreter decides whether to retain an
observation in a provisional evidence store or issue a proposed change.

1. `hatch()` creates an identity and returns an initial checkpoint request.
2. The owner signs and installs that initial checkpoint.
3. `dwell_or_propose()` retains evidence and may issue a signed-envelope candidate.
4. The owner reviews the proposed change and signs its exact payload.
5. `authorize_and_apply()` verifies authorization, applies the change, and returns
   a new checkpoint request.
6. The owner attests the result; the witness records the checkpoint chain.
7. `load()` checks internal consistency and attestation. `OwnerTool.audit()`
   also checks the external witness.

A proposal alone does not change character. Applying a signed proposal creates
an intermediate state that cannot be reloaded until the resulting checkpoint
has also been attested. The [worked example](examples/owner_authorization.py)
shows both stages.

You can also install the primary module for use from another directory:

```bash
python -m pip install .
```

```python
from humble_seed_v0_6 import HumbleSeed, OwnerTool, OwnerWitness
```

The package installs the primary module. Historical snapshots, probes, and the
runner remain available in the repository checkout.

## Research boundaries

The interpreter is a keyword stub with fixed weights. The owner tool and key
generation run in the same process, and the witness is a local JSON file.
Rolling back both state and witness can evade detection. Unattested history and
pre-proposal evidence remain forgeable. There is no key rotation, revocation,
or concurrent-writer control. These are documented prototype limits.

The tests establish specific behavior under their stated conditions. The
constitution's theorem label is retained project metadata. Read the
[scope and trust assumptions](SECURITY.md) and
[validation evidence](docs/VALIDATION.md) when evaluating broader claims.

## Repository contents

| Path | Contents |
| --- | --- |
| `humble_seed_v0_6.py` | Primary, unchanged v0.6 snapshot. |
| `history/` | Unchanged v0.3–v0.5 snapshots and their supplied probes. |
| `variants/v0_6_birth_root/` | Unchanged alternative v0.6 and its probes. |
| `probes/` | Supplied regression suite for the primary v0.6. |
| `examples/` | Short owner-authorization walkthrough. |
| `tests/` | Assertions for the primary workflow and declared limits. |
| `provenance/` | Original filenames, repository paths, sizes, and SHA-256 hashes. |
| `validation/` | Captured outputs from the matched script runs. |
| `.github/workflows/ci.yml` | Installation, source-integrity, test, and script checks. |

Repository packaging version: `0.6.0`. This identifies the assembly; both v0.6
state schemas retain their original `"0.6"` value. Keep their state directories
separate. No state migration is included.

## License and contributions

A reuse license was not supplied, so this assembly leaves the license choice
open. See [LICENSE_STATUS.md](LICENSE_STATUS.md). Research changes should keep
their source lineage and matching probes explicit; see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Related

The adversarial review record and merged v0.7 lineage live in
[`humble-seed-lineage-v2`](https://github.com/RMac-triadicIntelligence/humble-seed-lineage-v2).

