"""Author reproduction of ChatGPT's interrupted-witness-write report (v0.8.3, sighted round 4).
attest = check -> sign -> organism installs checkpoint -> witness records. Interrupt between
the last two steps, then take the normal paths."""
import sys, tempfile, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("k", sys.argv[1]); K = importlib.util.module_from_spec(spec)
sys.modules["k"] = K; spec.loader.exec_module(K)
d = Path(tempfile.mkdtemp())
s = K.HumbleSeed(d / "org"); _, pem, _ = s.hatch()
o = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json")); assert o.attest(s)
r = s.dwell_or_propose("verbosity", "evt", "I always prefer shorter answers")
s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
real = o.witness.record
def crash(cp): raise OSError("interrupted before the witness wrote")
o.witness.record = crash
try: o.attest(s)
except OSError as e: print("attest interrupted:", e)
o.witness.record = real
print("organism checkpoint seq:", s.checkpoint.sequence, "| witness seq:", o.witness.ledger[s.organism_id]["sequence"])
f = K.HumbleSeed(d / "org"); f.load(); print("organism loads on its own: True")
for label, fn in (("audit", lambda: o.audit(f)), ("retry attest", lambda: o.attest(s))):
    try: print(label, "->", fn())
    except (K.RollbackDetected, K.AttestationRefused) as e: print(label, "->", type(e).__name__ + ":", e)
r2 = s.dwell_or_propose("formality", "evt", "I prefer a casual tone always")
s.authorize_and_apply(r2["proposal_id"], o.sign_proposal(r2["payload_to_sign"]))
try: print("next crossing attest ->", o.attest(s))
except (K.RollbackDetected, K.AttestationRefused) as e: print("next crossing attest ->", type(e).__name__ + ":", e)
