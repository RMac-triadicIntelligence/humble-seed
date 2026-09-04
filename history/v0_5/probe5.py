"""Independent probe for v0.5. Does not reuse the module's own harness."""
import json, shutil, time
from pathlib import Path
from dataclasses import asdict
from humble_seed_v0_5 import (HumbleSeed, OwnerTool, OwnerWitness, Checkpoint,
                              IntegrityError, RollbackDetected, owner_sign_external,
                              _canonical_json, _sha256)

def newborn(tag):
    d = Path(f"./p5_{tag}"); shutil.rmtree(d, ignore_errors=True)
    s = HumbleSeed(data_dir=d); oid, pem, g = s.hatch()
    w = OwnerWitness(d/"w.json"); o = OwnerTool(pem, w); o.attest(s, g)
    return s, o, pem

def loads(s):
    try:
        f = HumbleSeed(data_dir=s.data_dir); f.load(); return "ACCEPTED"
    except IntegrityError as e: return f"rejected: {e}"

# P1 downgrade: install an older valid checkpoint
s, o, pem = newborn("p1")
old_cp = s.checkpoint
r = s.dwell_or_propose("verbosity","len","I always prefer shorter answers")
cp = s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"])); o.attest(s, cp)
old_sig = owner_sign_external(pem, HumbleSeed.checkpoint_payload(old_cp))
print("P1 downgrade to old checkpoint :", s.install_checkpoint(old_cp, old_sig), "(expect False)")

# P2 cross-organism checkpoint transplant
s2, o2, pem2 = newborn("p2")
print("P2 foreign checkpoint installed:",
      s2.install_checkpoint(s.checkpoint, s.checkpoint_sig), "(expect False)")

# P3 unattested tail fabrication (documented residual?)
s3, o3, _ = newborn("p3")
st = json.loads(s3._state_path().read_text())
tmp = HumbleSeed(data_dir=s3.data_dir); tmp.load()
tmp._append_trace({"event":"dwelling","category":"verbosity",
                   "reason":"FABRICATED HISTORY","timestamp":time.time()})
tmp._save()
print("P3 fabricated non-authorizing tail:", loads(s3))

# P4 fabricated AUTHORIZING entry in the tail
s4, o4, _ = newborn("p4")
t4 = HumbleSeed(data_dir=s4.data_dir); t4.load()
t4._append_trace({"event":"authorized_mutation","record":{"note":"FAKE"},"timestamp":time.time()})
t4._save()
print("P4 fabricated authorizing tail   :", loads(s4))

# P5 basin/pending rewritten after checkpoint, seal recomputed
s5, o5, _ = newborn("p5")
s5.dwell_or_propose("curiosity","x","something odd happened")
o5.attest(s5, s5.checkpoint_request())
t5 = HumbleSeed(data_dir=s5.data_dir); t5.load()
t5.basin[0].evidence = ["REWRITTEN AFTER ATTESTATION"]
t5._save()
print("P5 basin rewritten + resealed    :", loads(s5),
      "| evidence now:", HumbleSeed(data_dir=s5.data_dir).__class__ and
      json.loads(s5._state_path().read_text())["basin"][0]["evidence"])

# P6 witness catches nothing if attacker rolls back BOTH files (R1 control)
s6, o6, _ = newborn("p6")
snap_state = s6._state_path().read_text()
snap_ledger = (s6.data_dir/"w.json").read_text()
r6 = s6.dwell_or_propose("verbosity","len","I always prefer shorter answers")
c6 = s6.authorize_and_apply(r6["proposal_id"], o6.sign_proposal(r6["payload_to_sign"])); o6.attest(s6, c6)
s6._state_path().write_text(snap_state); (s6.data_dir/"w.json").write_text(snap_ledger)
rolled = HumbleSeed(data_dir=s6.data_dir); rolled.load()
w6 = OwnerWitness(s6.data_dir/"w.json"); o6b = OwnerTool("", w6)
try:
    w6.check(rolled.checkpoint); print("P6 both-file rollback            : UNDETECTED, as documented (R1)")
except RollbackDetected as e: print("P6 detected:", e)
