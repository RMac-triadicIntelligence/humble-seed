"""Diagnostic, after the scored run (not scored): T26's remaining assertions with the
objector that actually fired."""
import sys, json, importlib.util
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
spec = importlib.util.spec_from_file_location("h", Path(sys.argv[1]) / "falsify_v0_8_3.py"); H = importlib.util.module_from_spec(spec); sys.modules["h"] = H; spec.loader.exec_module(H)
K = H.load_module(H.CANDIDATE, "diag_k")
import tempfile
d = Path(tempfile.mkdtemp())
s, o = H.born(K, d)
r = H.propose(s, "verbosity"); sig = o.sign_proposal(r["payload_to_sign"])
s.character["formality"] = 0.99
assert s.authorize_and_apply(r["proposal_id"], sig) is not None
why = H.expect_refused(K, lambda: o.attest(s), "record fields differ from the replay")
print("objector:", why)
print("witness still at 0:", o.witness.ledger[s.organism_id]["sequence"] == 0)
print("load fails:", H.expect_integrity(K, s.data_dir, "Category sequences do not match the attested"))
print("tamper preserved:", json.loads(s._state_path().read_text())["character"]["formality"] == 0.99)
