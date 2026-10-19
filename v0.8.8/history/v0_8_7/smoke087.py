#!/usr/bin/env python3
"""Pre-freeze smoke for v0.8.7: the basic flow, and restore's accepting path. Nothing else."""
import importlib.util, sys, tempfile
from pathlib import Path
spec = importlib.util.spec_from_file_location("k087", sys.argv[1]); K = importlib.util.module_from_spec(spec)
sys.modules["k087"] = K; spec.loader.exec_module(K)
PREF = "I always prefer shorter answers"
with tempfile.TemporaryDirectory() as t:
    d = Path(t)
    s = K.HumbleSeed(d / "org"); _, pem, _ = s.hatch()
    o = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json")); assert o.attest(s)
    r = s.dwell_or_propose("verbosity", "evt", PREF); assert r["status"] == "proposal"
    assert s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"])) is not None
    assert o.attest(s)
    f = K.HumbleSeed(d / "org"); f.load(); assert o.audit(f)
    print("basic flow ok: verbosity", f.character["verbosity"], "checkpoint", f.checkpoint.sequence)
    r = f.dwell_or_propose("formality", "evt", "I prefer a casual tone always"); assert r["status"] == "proposal"
    assert f.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"])) is not None
    res = o.restore(f)
    g = K.HumbleSeed(d / "org"); g.load(); assert o.audit(g)
    print("restore ok:", res, "formality", g.character["formality"], "checkpoint", g.checkpoint.sequence)
