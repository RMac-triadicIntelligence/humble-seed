"""Author reproduction of ChatGPT round 6 (in progress, 07:55 CT): an older organism object's
ordinary save overwrites newer, signed-off state; the reload succeeds; the witness refuses it."""
import importlib.util, json, sys, tempfile
from pathlib import Path
spec = importlib.util.spec_from_file_location("k", sys.argv[1]); K = importlib.util.module_from_spec(spec)
sys.modules["k"] = K; spec.loader.exec_module(K)
d = Path(tempfile.mkdtemp())
s = K.HumbleSeed(d / "org"); _, pem, _ = s.hatch()
o = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json")); assert o.attest(s)
old = K.HumbleSeed(d / "org"); old.load()                      # a second session, at checkpoint 0
r = s.dwell_or_propose("verbosity", "evt", "I always prefer shorter answers")
assert s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"])) is not None
assert o.attest(s)                                            # disk and witness at checkpoint 1
seq = lambda: json.loads((d / "org" / "organism_state.json").read_text())["checkpoint"]["sequence"]
print("before: saved checkpoint", seq(), "| verbosity", s.character["verbosity"])
print("old session dwells:", old.dwell_or_propose("formality", "evt", "hmm ok")["status"])
print("after:  saved checkpoint", seq())
f = K.HumbleSeed(d / "org")
try: f.load(); print("reload: succeeds | verbosity", f.character["verbosity"])
except Exception as e: print("reload:", type(e).__name__, e)
try: print("audit:", o.audit(f))
except Exception as e: print("audit:", type(e).__name__, e)
