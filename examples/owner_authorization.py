"""A fresh identity, a proposal, owner authorization, and an audited reload."""

from pathlib import Path
from tempfile import TemporaryDirectory

from humble_seed_v0_6 import HumbleSeed, OwnerTool, OwnerWitness


def demonstrate(root: Path) -> None:
    seed_dir = root / "organism"
    owner_dir = root / "owner"
    owner_dir.mkdir()
    seed = HumbleSeed(seed_dir)
    _, private_pem, genesis = seed.hatch()
    owner = OwnerTool(private_pem, OwnerWitness(owner_dir / "witness.json"))

    # This prototype generates the key in-process. Keep it out of state files
    # and logs. Same-process code is not a security isolation boundary.
    if not owner.attest(seed, genesis):
        raise RuntimeError("Genesis attestation failed")

    before = seed.character["verbosity"]
    proposal = seed.dwell_or_propose(
        "verbosity", "answer_length", "I always prefer shorter answers"
    )
    if proposal["status"] != "proposal":
        raise RuntimeError("Expected a proposal for this demonstration input")
    print(f"Proposal issued; verbosity is still {seed.character['verbosity']}")
    print(f"First commitment in this category: {proposal['first_commit']}")

    # An actual owner reviews the payload before signing. Automatic signing
    # below is a walkthrough fixture, not an implementation of human review.
    signature = owner.sign_proposal(proposal["payload_to_sign"])
    checkpoint = seed.authorize_and_apply(proposal["proposal_id"], signature)
    if checkpoint is None or not owner.attest(seed, checkpoint):
        raise RuntimeError("Mutation or result attestation failed")

    reloaded = HumbleSeed(seed_dir)
    reloaded.load()
    if not owner.audit(reloaded):
        raise RuntimeError("External audit failed")
    print(f"Authorized and attested: verbosity {before} -> {reloaded.character['verbosity']}")
    print(f"Mutation sequence: {reloaded.mutation_sequence}")
    print("Reload and external witness audit succeeded.")


if __name__ == "__main__":
    with TemporaryDirectory(prefix="humble-seed-example-") as directory:
        demonstrate(Path(directory))
