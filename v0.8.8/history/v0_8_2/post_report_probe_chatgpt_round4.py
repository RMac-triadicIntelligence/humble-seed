"""Author reproduction of ChatGPT round-4 findings, from its in-progress description
(its run was stopped by its provider before packaging). Credit: ChatGPT."""
import sys, json, time, tempfile, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("k", sys.argv[1]); K = importlib.util.module_from_spec(spec)
sys.modules["k"] = K; spec.loader.exec_module(K)
PREF = "I always prefer shorter answers"

def born(d):
    s = K.HumbleSeed(d / "org"); _, pem, _ = s.hatch()
    o = K.OwnerTool(pem, K.OwnerWitness(d / "w.json")); assert o.attest(s); return s, o

def rechain(s):
    bodies = [{k: v for k, v in e.items() if k not in ("prev_hash", "entry_hash")} for e in s.trace]
    s.trace, s._trace_head = [], "0" * 64
    for b in bodies: s._append_trace(b)
    s._save()

def reload_audit(s, o):
    f = K.HumbleSeed(s.data_dir); f.load(); return o.audit(f), f

def attest(o, s):
    try: return o.attest(s)
    except K.AttestationRefused as e: return f"REFUSED: {e}"

# F1a: expired reading — live apply rejects; organism applies it anyway; owner attests
d = Path(tempfile.mkdtemp()); s, o = born(d)
r = s.dwell_or_propose("verbosity", "evt", PREF); pid = r["proposal_id"]; sig = o.sign_proposal(r["payload_to_sign"])
s.clock = lambda: s.pending[pid].expires_at + 60
assert s.authorize_and_apply(pid, sig) is None and "expired" in s.trace[-1]["reason"]
s.reader = None; real = s.clock; t0 = s.pending[pid].timestamp; s.clock = lambda: t0 + 1   # organism bypasses its own expiry
assert s.authorize_and_apply(pid, sig) is not None; s.clock = time.time
a = attest(o, s); ok, f = reload_audit(s, o) if a is True else (None, None)
print("F1a expired reading applied anyway  -> attest:", a, "| reload+audit:", ok,
      "| 'expired' rejection in history:", any("expired" in e.get("reason", "") for e in s.trace))

# F1b: held reading — owner said no, live apply holds; organism applies it anyway; owner attests
d = Path(tempfile.mkdtemp()); s, o = born(d)
r = s.dwell_or_propose("verbosity", "evt", PREF); pid = r["proposal_id"]; sig = o.sign_proposal(r["payload_to_sign"])
s.record_owner_answer(pid, "no", "no")
assert s.authorize_and_apply(pid, sig) is None and s.trace[-1]["event"] == "reading_held"
s.reader = None                                                                    # organism skips its reader
assert s.authorize_and_apply(pid, sig) is not None
a = attest(o, s); ok, f = reload_audit(s, o) if a is True else (None, None)
print("F1b held reading applied anyway     -> attest:", a, "| reload+audit:", ok,
      "| 'no' + hold in history:", any(e.get("answer") == "no" for e in s.trace), any(e["event"] == "reading_held" for e in s.trace))

# F2: false consequence — record fields replay does not check
d = Path(tempfile.mkdtemp()); s, o = born(d)
r = s.dwell_or_propose("verbosity", "evt", PREF)
res = s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
print("F2 honest consequence :", res["consequence"])
rec = s.trace[-1]["record"]; rec["prior_value"] = 0.0; rec["first_commit"] = False
rec["prior_character_snapshot"]["verbosity"] = 0.0
rechain(s)
a = attest(o, s); ok, f = reload_audit(s, o) if a is True else (None, None)
shown = K.render_consequence([e for e in f.trace if e["event"] == "authorized_mutation"][-1]["record"]) if f else None
print("F2 after record edit -> attest:", a, "| reload+audit:", ok)
print("F2 rendered consequence:", shown)
