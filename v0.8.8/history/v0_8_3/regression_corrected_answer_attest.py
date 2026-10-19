"""v0.8.3 follow-up to the corrected-answer probe: same case, through to attestation and reload."""
import sys, tempfile, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("k", sys.argv[1]); K = importlib.util.module_from_spec(spec)
sys.modules["k"] = K; spec.loader.exec_module(K)
for via in ("organism only", "owner tool"):
    d = Path(tempfile.mkdtemp()); s = K.HumbleSeed(d / "org"); _, pem, _ = s.hatch()
    o = K.OwnerTool(pem, K.OwnerWitness(d / "w.json")); assert o.attest(s)
    r = s.dwell_or_propose("verbosity", "evt", "I always prefer shorter answers"); pid = r["proposal_id"]
    sig = o.sign_proposal(r["payload_to_sign"])
    for a in ("no", "yes"):
        (s.record_owner_answer(pid, a) if via == "organism only" else o.answer(s, pid, a))
    applied = s.authorize_and_apply(pid, sig) is not None
    attested = o.attest(s)
    f = K.HumbleSeed(d / "org"); f.load()
    print(f"answers no->yes via {via}: applied {applied}, attested {attested}, reload+audit {o.audit(f)}, verbosity {f.character['verbosity']}")
