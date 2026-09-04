import json, shutil
from pathlib import Path
from humble_seed_v0_4 import (HumbleSeed, IntegrityError, owner_sign_external,
                              _canonical_json, _sha256)

d = Path("./probe4"); shutil.rmtree(d, ignore_errors=True)
s = HumbleSeed(data_dir=d); oid, pem = s.hatch()
s.first_commit_pending["verbosity"] = False
r = s.dwell_or_propose("verbosity","len","I always prefer shorter answers")
s.authorize_and_apply(r["proposal_id"], owner_sign_external(pem, r["payload_to_sign"]), "legit")
base = json.loads(s._state_path().read_text())

def attempt(name, mutate):
    st = json.loads(json.dumps(base)); mutate(st)
    s._state_path().write_text(_canonical_json(st))
    try:
        HumbleSeed(data_dir=d).load(); print(f"{name}: ACCEPTED — FAIL")
    except (IntegrityError, Exception) as ex:
        print(f"{name}: rejected -> {type(ex).__name__}: {str(ex)[:70]}")

# genesis re-derivation in isolation (constitution binding left intact)
attempt("created_at only        ", lambda st: st["birth"].__setitem__("created_at", 1.0))
attempt("organism_id in birth   ", lambda st: st["birth"].__setitem__("organism_id", "x"))
attempt("public key swapped     ", lambda st: st["birth"].__setitem__("public_key_b64", "A"*43+"="))
attempt("genesis_hash only      ", lambda st: st["birth"].__setitem__("genesis_hash", "0"*64))
attempt("constitution deleted   ", lambda st: st.pop("constitution"))
attempt("character out of range ", lambda st: st["character"].__setitem__("verbosity", 5.0))
attempt("character string value ", lambda st: st["character"].__setitem__("verbosity", "preference"))
attempt("character extra field  ", lambda st: st["character"].__setitem__("evil", 0.5))
attempt("consumed entry dropped ", lambda st: st.__setitem__("consumed", []))
attempt("trace truncated        ", lambda st: st.__setitem__("trace", st["trace"][:1]))
attempt("schema_version bumped  ", lambda st: st.__setitem__("schema_version", "9.9"))

# O1 control: full forge with recomputed seal — expected to be ACCEPTED
st = json.loads(json.dumps(base))
st["character"]["verbosity"] = 0.99
s._state_path().write_text(_canonical_json(st))
o = HumbleSeed(data_dir=d)
o.organism_id=st["organism_id"]
from humble_seed_v0_4 import BirthRecord, PreTrace, PendingProposal
o.birth=BirthRecord(**st["birth"]); o.constitution=st["constitution"]
o.character=st["character"]; o.basin=[PreTrace(**p) for p in st["basin"]]
o.pending={k:PendingProposal(**v) for k,v in st["pending"].items()}
o.consumed=set(st["consumed"]); o._trace_head=st["trace_head"]
st["state_seal"]=o._compute_seal()
s._state_path().write_text(_canonical_json(st))
try:
    f=HumbleSeed(data_dir=d); f.load()
    print(f"O1 control (reseal)    : ACCEPTED as documented -> {f.character}")
except Exception as ex:
    print("O1 control            : rejected", ex)

# apply-time schema re-validation: in-memory pending tampered after issuance
s2 = HumbleSeed(data_dir=d)
st = json.loads(json.dumps(base)); s2._state_path().write_text(_canonical_json(st)); s2.load()
p = s2._issue_pending_proposal("formality", {"formality":0.3}, {"preference":1.0}, ["e"])
sig = owner_sign_external(pem, p.payload_to_sign)
s2.pending[p.proposal_id].change = {"formality": 9.9}
print("apply-time tamper      :", s2.authorize_and_apply(p.proposal_id, sig),
      "->", [e["reason"] for e in s2.trace if e.get("event")=="authorization_rejected"][-1])
