"""Independent regression probes for Humble Seed v0.6."""

from __future__ import annotations

import inspect
import shutil
from dataclasses import asdict
from pathlib import Path

from humble_seed_v0_6 import (
    Checkpoint,
    HumbleSeed,
    IntegrityError,
    OwnerTool,
    OwnerWitness,
    RollbackDetected,
    _sha256,
)


ROOT = Path("./probe6_data")


def newborn(name: str):
    data_dir = ROOT / name
    shutil.rmtree(data_dir, ignore_errors=True)
    seed = HumbleSeed(data_dir=data_dir)
    _, pem, genesis = seed.hatch()
    witness = OwnerWitness(data_dir / "owner_witness.json")
    owner = OwnerTool(pem, witness)
    assert owner.attest(seed, genesis)
    return seed, owner, witness


def rejected_on_load(seed: HumbleSeed, expected: str) -> None:
    try:
        HumbleSeed(data_dir=seed.data_dir).load()
    except IntegrityError as exc:
        assert expected.lower() in str(exc).lower(), (expected, str(exc))
        return
    raise AssertionError(f"tampered state loaded; expected rejection containing {expected!r}")


shutil.rmtree(ROOT, ignore_errors=True)

# F6: issuance exposes no first_commit override, and apply rechecks the live gate.
assert "first_commit" not in inspect.signature(
    HumbleSeed._issue_pending_proposal
).parameters
seed, owner, _ = newborn("f6")
proposal = seed._issue_pending_proposal(
    "verbosity", {"verbosity": 0.2}, {"preference": 1.0}, ["evidence"]
)
assert proposal.first_commit is True
proposal.first_commit = False
proposal.payload_to_sign = seed._recompute_payload(proposal)
proposal.payload_hash = _sha256(proposal.payload_to_sign)
assert seed.authorize_and_apply(
    proposal.proposal_id, owner.sign_proposal(proposal.payload_to_sign)
) is None
assert "first-commit mismatch" in seed.trace[-1]["reason"]
print("F6 truthful first-commit: PASS")

# F7: critical gate state is checkpoint-attested, not merely sealed.
seed, _, _ = newborn("f7")
attacker = HumbleSeed(data_dir=seed.data_dir)
attacker.load()
attacker.first_commit_pending["curiosity"] = False
attacker._save()
rejected_on_load(seed, "gates")
print("F7 attested gates: PASS")

# F8: even a fully rebound and rechained birth/constitution branch is rejected
# by the checkpoint's pinned genesis.
seed, _, _ = newborn("f8")
attacker = HumbleSeed(data_dir=seed.data_dir)
attacker.load()
attacker.constitution["rule"] = "The organism may authorize its own growth."
attacker.birth.constitution_hash = attacker._constitution_root()
attacker.birth.genesis_hash = attacker._derive_genesis(
    attacker.birth.organism_id,
    attacker.birth.public_key_b64,
    attacker.birth.created_at,
    attacker.birth.constitution_hash,
)
bodies = [
    {k: v for k, v in entry.items() if k not in ("prev_hash", "entry_hash")}
    for entry in attacker.trace
]
bodies[0]["genesis_hash"] = attacker.birth.genesis_hash
bodies[0]["constitution_hash"] = attacker.birth.constitution_hash
attacker.trace = []
attacker._trace_head = "0" * 64
for body in bodies:
    attacker._append_trace(body)
attacker._save()
rejected_on_load(seed, "genesis")
print("F8 birth/constitution binding: PASS")

# The trace has exactly one birth, at index zero.
seed, _, _ = newborn("birth")
attacker = HumbleSeed(data_dir=seed.data_dir)
attacker.load()
attacker._append_trace({
    "event": "birth",
    "organism_id": attacker.organism_id,
    "genesis_hash": attacker.birth.genesis_hash,
    "constitution_hash": attacker.birth.constitution_hash,
    "timestamp": attacker.birth.created_at,
})
attacker._save()
rejected_on_load(seed, "exactly one birth")
print("F8 unique birth trace: PASS")

# F9: witness accepts only an immediate child with the exact recorded parent.
seed, owner, witness = newborn("f9")
assert owner.attest(seed, seed.checkpoint_request())
candidate = seed.checkpoint_request()
wrong_parent = Checkpoint(**{
    **asdict(candidate),
    "prev_checkpoint_hash": _sha256("wrong parent"),
})
try:
    witness.check(wrong_parent)
except RollbackDetected as exc:
    assert "parent" in str(exc).lower()
else:
    raise AssertionError("witness accepted an advancing wrong-parent fork")

gap = Checkpoint(**{**asdict(candidate), "sequence": candidate.sequence + 1})
try:
    witness.check(gap)
except RollbackDetected as exc:
    assert "gap" in str(exc).lower()
else:
    raise AssertionError("witness accepted a sequence gap")

wrong_genesis = Checkpoint(**{
    **asdict(candidate),
    "genesis_hash": _sha256("foreign genesis"),
})
try:
    witness.check(wrong_genesis)
except RollbackDetected as exc:
    assert "identity fork" in str(exc).lower()
else:
    raise AssertionError("witness accepted a foreign genesis")
print("F9 linear, genesis-pinned witness: PASS")

print("Independent v0.6 regression suite: PASS")
