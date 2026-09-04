import json, shutil
from pathlib import Path
from dataclasses import asdict
from humble_seed_v0_6 import (HumbleSeed, OwnerTool, OwnerWitness, Checkpoint,
                              IntegrityError, RollbackDetected,
                              _canonical_json, _sha256, _fixed)

def newborn(tag):
    d = Path(f"./g6_{tag}"); shutil.rmtree(d, ignore_errors=True)
    s = HumbleSeed(data_dir=d); oid, pem, g = s.hatch()
    w = OwnerWitness(d/"w.json"); o = OwnerTool(pem, w); o.attest(s, g)
    return s, o, pem, w

def loads(s):
    try:
        f = HumbleSeed(data_dir=s.data_dir); f.load(); return ("ACCEPTED", f)
    except IntegrityError as e: return (f"rejected: {e}", None)

# G1 — first mutation signed with first_commit=False despite pending gate
s, o, pem, w = newborn("g1")
print("G1 gate before:", s.first_commit_pending.get("verbosity", True))
p = s._issue_pending_proposal("verbosity", {"verbosity":0.25}, {"preference":1.0}, ["e"])
print("   derived flag:", json.loads(p.payload_to_sign)["first_commit"], "(param removed)")
fp = json.loads(p.payload_to_sign); fp["first_commit"] = False
p.first_commit = False; p.payload_to_sign = _canonical_json(fp)
cp = s.authorize_and_apply(p.proposal_id, o.sign_proposal(p.payload_to_sign))
print("G1 applied without first_commit flag:", cp is not None, "| character:", s.character)

# G2 — gates rewritten + resealed, checkpoint untouched
s, o, pem, w = newborn("g2")
t = HumbleSeed(data_dir=s.data_dir); t.load()
t.first_commit_pending = {"verbosity": False, "formality": False, "curiosity": False}
t._save()
res, f = loads(s)
print("G2 gates flipped + resealed:", res if f is None else f"ACCEPTED -> {f.first_commit_pending}")

# G3 — constitution replaced, birth rebuilt self-consistently, checkpoint untouched
s, o, pem, w = newborn("g3")
st = json.loads(s._state_path().read_text())
st["constitution"]["rule"] = "The organism may authorize its own growth."
st["constitution"]["invariants"] = []
new_ch = _sha256(_canonical_json(st["constitution"]))
st["birth"]["constitution_hash"] = new_ch
st["birth"]["genesis_hash"] = HumbleSeed._derive_genesis(
    st["birth"]["organism_id"], st["birth"]["public_key_b64"],
    st["birth"]["created_at"], new_ch)
s._state_path().write_text(_canonical_json(st))
t = HumbleSeed(data_dir=s.data_dir)
t.organism_id=st["organism_id"]
from humble_seed_v0_6 import BirthRecord, PreTrace, PendingProposal
t.birth=BirthRecord(**st["birth"]); t.constitution=st["constitution"]
t.character=st["character"]; t.basin=[]; t.pending={}
t.consumed=set(); t.trace=st["trace"]; t.first_commit_pending=st["first_commit_pending"]
t.mutation_sequence=st["mutation_sequence"]; t._trace_head=st["trace_head"]
t.checkpoint=Checkpoint(**st["checkpoint"]); t.checkpoint_sig=st["checkpoint_sig"]
st["state_seal"]=t._compute_seal()
s._state_path().write_text(_canonical_json(st))
res, f = loads(s)
print("G3 constitution swapped:", res if f is None else
      f"ACCEPTED -> rule now: {f.constitution['rule']!r}")

# G4 — advancing fork: higher sequence, wrong parent
s, o, pem, w = newborn("g4")
r = s.dwell_or_propose("verbosity","len","I always prefer shorter answers")
cp = s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"])); o.attest(s, cp)
print("G4 witness holds sequence:", w.ledger[s.organism_id]["sequence"])
bogus = Checkpoint(**{**asdict(s.checkpoint), "sequence": 99,
                      "prev_checkpoint_hash": _sha256("unrelated branch"),
                      "character_root": _sha256("forked character")})
try:
    w.check_successor(bogus); print("G4 advancing fork with wrong parent: ACCEPTED by witness")
except RollbackDetected as e: print("G4 rejected:", e)

# G5 — is the birth trace entry cross-checked against birth/constitution?
s, o, pem, w = newborn("g5")
t = HumbleSeed(data_dir=s.data_dir); t.load()
print("G5 birth trace genesis:", t.trace[0]["genesis_hash"][:12],
      "| birth record genesis:", t.birth.genesis_hash[:12],
      "| cross-checked by verify():", "no explicit check in verify()")
