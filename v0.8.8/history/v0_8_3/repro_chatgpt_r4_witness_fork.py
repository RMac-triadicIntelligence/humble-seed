"""Author reproduction of ChatGPT's sibling-checkpoint report (v0.8.3, sighted round 4):
two owner sessions, each holding its own copy of the witness, attest two different
successors of the same checkpoint."""
import sys, shutil, tempfile, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("k", sys.argv[1]); K = importlib.util.module_from_spec(spec)
sys.modules["k"] = K; spec.loader.exec_module(K)
d = Path(tempfile.mkdtemp())
s = K.HumbleSeed(d / "org"); _, pem, _ = s.hatch()
A = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json")); assert A.attest(s)
B = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json"))           # second session, same files
shutil.copytree(d / "org", d / "org_copy")                           # same parent state, two copies
s1 = K.HumbleSeed(d / "org"); s1.load()
s2 = K.HumbleSeed(d / "org_copy"); s2.load()
r1 = s1.dwell_or_propose("verbosity", "evt", "I always prefer shorter answers")
s1.authorize_and_apply(r1["proposal_id"], A.sign_proposal(r1["payload_to_sign"]))
print("A attests branch 1 (seq 1):", A.attest(s1))
r2 = s2.dwell_or_propose("formality", "evt", "I prefer a casual tone always")
s2.authorize_and_apply(r2["proposal_id"], B.sign_proposal(r2["payload_to_sign"]))
try: print("B attests branch 2 (seq 1, same parent):", B.attest(s2))
except Exception as e: print("B refused:", type(e).__name__, e)
w = K.OwnerWitness(d / "witness.json")
for name, seed in (("branch 1", s1), ("branch 2", s2)):
    f = K.HumbleSeed(seed.data_dir); f.load()
    try: w.check_current(f.checkpoint); print(f"fresh witness accepts {name} as current")
    except K.RollbackDetected as e: print(f"fresh witness rejects {name}: {e}")
