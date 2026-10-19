"""Post-report author probe (after Grok round 3): a corrected owner answer."""
import sys, tempfile, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("k", sys.argv[1]); K = importlib.util.module_from_spec(spec)
sys.modules["k"] = K; spec.loader.exec_module(K)
d = Path(tempfile.mkdtemp())
s = K.HumbleSeed(d / "org"); _, pem, _ = s.hatch()
o = K.OwnerTool(pem, K.OwnerWitness(d / "w.json")); assert o.attest(s)
r = s.dwell_or_propose("verbosity", "evt", "I always prefer shorter answers")
pid, sig = r["proposal_id"], o.sign_proposal(r["payload_to_sign"])
s.record_owner_answer(pid, "no", "no")
s.record_owner_answer(pid, "yes", "sorry, misread the question - yes")
out = s.authorize_and_apply(pid, sig)
print("after no -> yes, signed apply:", "APPLIED" if out else f"{s.trace[-1]['event']}: {s.trace[-1].get('reason')}")
print("any way to retract the 'no'? trace is append-only; reader checks for ANY 'no' since issuance")
s.clock = lambda: s.pending[pid].expires_at + 1
s.authorize_and_apply(pid, sig)
print("terminal state:", s.trace[-1]["event"], "-", s.trace[-1].get("reason"))
