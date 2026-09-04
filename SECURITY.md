# Prototype scope and trust assumptions

Humble Seed is a local research prototype. Its demonstrations and tests cover
specific state transitions and adversarial edits under the assumptions below.

## What the primary v0.6 checks

An applied proposal must carry an owner signature over its mutation envelope.
That envelope includes the proposed category/change, evidence and distribution
roots, first-commit flag, prior state/trace references, sequence, nonce, and
expiration. Applying a proposal and attesting the resulting state are separate
operations.

An owner checkpoint attests selected persistent roots. The external witness
remembers checkpoint lineage and can reject an older state or a competing
branch. `load()` checks internal state; use `OwnerTool.audit()` to also consult
the witness. The unkeyed state seal alone provides no authenticity against an
attacker who can recompute it.

## Limits retained from the supplied sources

| Area | Prototype limit |
| --- | --- |
| Witness | A local JSON file. An attacker who can roll back both state and witness can evade rollback detection. |
| Owner boundary | The signer, key generation, and organism run in one process. Their code organization does not enforce process or hardware isolation. |
| Key lifecycle | No rotation or revocation; owner-key compromise defeats its authorizations. |
| Interpretation | Fixed keyword matching and weights, without a learned model or calibrated confidence. |
| Concurrency | Single-writer assumption; no file locks. |
| Recovery | A crash after apply and before attestation leaves state that cannot reload; owner-assisted recovery is not automated. |
| Human review | Showing a first-commit flag does not establish that an owner understood the payload. |
| Unattested trace | Non-authorizing entries after the checkpoint can be fabricated and resealed. |
| Basin and pending data | Pre-proposal evidence and pending storage are advisory until bound into an appropriate signed envelope or attested record. |
| Schemas | v0.5 and the two v0.6 implementations have incompatible records. No state migration is provided. |

`hatch()` returns private PEM material to the owner side of the demonstration.
It is not written into the organism state by the supplied code. Keep real owner
material and live organism data out of a published source repository. The
runner uses disposable identities; the package includes no generated keys or
state files.

The alternative v0.6 describes `constitution_root` as defense in depth relative
to its other birth/constitution checks. Its interface and exact properties
are documented in [VERSIONS.md](docs/VERSIONS.md).

## Reproducible findings

Include the snapshot path and source hash, the attacker access assumed, the
smallest reproduction, expected and observed behavior, and the exact check
that rejects or accepts the operation. Distinguish an existing stated limit,
a probe defect, and a newly demonstrated implementation defect. Use disposable
keys and remove private data from reports.
