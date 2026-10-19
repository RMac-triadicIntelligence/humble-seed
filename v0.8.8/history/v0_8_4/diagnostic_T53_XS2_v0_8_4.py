"""Diagnostic after the scored run (not scored): ChatGPT's lifetime-refresh case with the
sign-off made by a FRESH session, on the candidate and on the XS2 mutant."""
import json, sys, time, tempfile, importlib.util
from pathlib import Path
here = Path(sys.argv[1]).resolve()
decl = json.loads((here / "DECLARED_v0_8_4.json").read_text())
def load(path, alias):
    spec = importlib.util.spec_from_file_location(alias, path); m = importlib.util.module_from_spec(spec)
    sys.modules[alias] = m; spec.loader.exec_module(m); return m
src = (here / "humble_seed_v0_8_4_candidate.py").read_text()
for old, new in decl["mutants"]["XS2_ledger_not_reread"]["edits"]:
    assert src.count(old) == 1; src = src.replace(old, new)
tmp = Path(tempfile.mkdtemp()); (tmp / "xs2.py").write_text(src)
for label, K in (("candidate", load(here / "humble_seed_v0_8_4_candidate.py", "cand")), ("XS2 mutant", load(tmp / "xs2.py", "xs2"))):
    d = Path(tempfile.mkdtemp())
    s = K.HumbleSeed(d / "org"); _, pem, _ = s.hatch(reading_ttl_seconds=10.0)
    a = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json")); assert a.attest(s)
    b = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json"))
    r = s.dwell_or_propose("verbosity", "evt", "I always prefer shorter answers")
    t0 = time.time(); a.clock = lambda: t0; sig = a.sign_proposal(r["payload_to_sign"])
    b.clock = lambda: t0 + 11.0; b.sign_proposal(r["payload_to_sign"])
    assert s.authorize_and_apply(r["proposal_id"], sig) is not None
    fresh = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json")); fresh.clock = lambda: t0 + 11.0
    try: out = f"ACCEPTED ({fresh.attest(s)})"
    except K.AttestationRefused as e: out = f"refused: {e}"
    print(f"{label}: fresh session at t0+11 -> {out}")
