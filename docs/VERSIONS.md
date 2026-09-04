# Versions, variants, and probe pairing

The supplied materials contain four numbered versions and five kernel files.
The two v0.6 files share a schema label but differ in checkpoint fields,
witness interfaces, and verification behavior. Their relative historical
order cannot be established from the filenames alone.

## Exact source mapping

Every mapped file retains the exact bytes of its upload. Filenames were
normalized for Python imports and paths were chosen to keep interfaces apart.

| Uploaded filename | Repository path | Runner target |
| --- | --- | --- |
| `humble_seed_v0_3(1).py` | `history/v0_3/humble_seed_v0_3.py` | `demo-v03` |
| `humble seed v0 4(1).py` | `history/v0_4/humble_seed_v0_4.py` | `demo-v04` |
| `probe4(1).py` | `history/v0_4/probe4.py` | `probe-v04` |
| `humble seed v0 5(1).py` | `history/v0_5/humble_seed_v0_5.py` | `demo-v05` |
| `probe5(1).py` | `history/v0_5/probe5.py` | `probe-v05` |
| `humble_seed_v0_6(1).py` | `humble_seed_v0_6.py` | `demo` |
| `probe6_validation(1).py` | `probes/probe6_validation.py` | `validate` |
| `humble seed v0 6(1).py` | `variants/v0_6_birth_root/humble_seed_v0_6.py` | `demo-v06-birth-root` |
| `probe6.py` | `variants/v0_6_birth_root/probe6.py` | `probe-v06-birth-root` |
| `triage6.py` | `variants/v0_6_birth_root/triage6.py` | `triage-v06-birth-root` |

Run a target with `python run.py TARGET`. The runner chooses the matching import
directory; no compatibility shims or combined witness APIs are introduced.

## Development described by the source

| Snapshot | Focus described in the file |
| --- | --- |
| v0.3 | Numeric mutation schema, full trace-chain verification, and an expanded unkeyed seal. |
| v0.4 | Full pending/basin seal coverage, persisted constitution, genesis re-derivation, external signing helper, atomic replacement. |
| v0.5 | Proposal evidence and category binding, first-commit flags, stale-state rejection, owner checkpoints, and an external witness. |
| v0.6, primary | Truthful first-commit flags, attested genesis/constitution/gates, a unique birth trace, and a witness that pins genesis and enforces parent continuity. |
| v0.6, alternative | Truthful first-commit flags, an attested whole-birth root, constitution/gate roots, birth-trace cross-checks, and separate current/successor witness checks. |

These summarize source contents. Earlier v0.1/v0.2 work mentioned by the files
was not supplied and has not been reconstructed here. Historical wording such
as "closed" remains in the original files; packaging does not expand those
claims beyond their stated experiments.

## The two v0.6 interfaces

| Detail | Primary: Constitution-Bound State and Linear Witness | Alternative: Attestation Covers the Constitution |
| --- | --- | --- |
| Original filename | `humble_seed_v0_6(1).py` | `humble seed v0 6(1).py` |
| Checkpoint identity field | `genesis_hash` | `birth_root` |
| Other attested roots | `constitution_root`, `gates_root`, character, consumed ledger, trace prefix | `constitution_root`, `gates_root`, character, consumed ledger, trace prefix |
| Witness API | `check()` accepts the recorded checkpoint or its immediate valid child. | `check_current()` requires the recorded checkpoint; `check_successor()` checks a new child. |
| Witness identity record | Stores `genesis_hash` with sequence and checkpoint hash. | Stores sequence and checkpoint hash. |
| Birth-trace verification | Exactly one birth event at index zero; checks identity, genesis, constitution hash, and timestamp. | Checks the first entry against identity, genesis, and constitution hash. |
| Gate initialization | All allowed categories explicitly present and validated as booleans. | Gates can be absent and default to pending when consulted. |
| Supplied assertion suite | `probe6_validation.py` | No separate assertion suite supplied for this interface. |
| Supplied observation scripts | Its built-in demo | `probe6.py`, `triage6.py`, and its built-in demo |

The primary entry point is selected because it is the direct target of the
supplied assertion suite. Both kernels remain unchanged and available for
comparison.

Both declare `SCHEMA_VERSION = "0.6"`, but their checkpoint records are
incompatible. There is no adapter or migration between them. Use separate
data directories and the matching runner target. The alternative retains its
original `./seed_data_v05` default and an outdated v0.5 usage line; the runner
isolates those paths.
