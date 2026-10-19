from pathlib import Path
from humble_seed_v0_8_8_candidate import HumbleSeed, OwnerTool, OwnerWitness

d = Path("demo"); d.mkdir(exist_ok=True)
seed = HumbleSeed(d / "organism")
_, owner_key_pem, _ = seed.hatch()                     # keep the owner key private
owner = OwnerTool(owner_key_pem, OwnerWitness(d / "witness.json"))
owner.attest(seed)                                     # sign off the newborn state

r = seed.dwell_or_propose("verbosity", "chat", "I always prefer shorter answers")
print(r["status"])                                     # "proposal": a reading awaits your signature
seed.authorize_and_apply(r["proposal_id"], owner.sign_proposal(r["payload_to_sign"]))
owner.attest(seed)                                     # sign off the consequence (replayed first)
print(seed.character["verbosity"])                    # 0.25

r = seed.dwell_or_propose("formality", "chat", "I prefer a casual tone always")
seed.authorize_and_apply(r["proposal_id"], owner.sign_proposal(r["payload_to_sign"]))
print(owner.restore(seed)["status"])                   # not signed off: back to the last sign-off
print(seed.character["formality"])                    # 0.5
