"""ChatGPT round-4 probes that no longer fit v0.8.4's interface, adapted minimally by the author:
forged metadata uses the renamed field, and the witness write fails at each of v0.8.4's two
witness writes (intent, then commit) instead of v0.8.3's single write."""
import sys, json, tempfile, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("k", sys.argv[1]); K = importlib.util.module_from_spec(spec)
sys.modules["k"] = K; spec.loader.exec_module(K)
PREF = "I always prefer shorter answers"

def born(d):
    s = K.HumbleSeed(d / "org"); _, pem, _ = s.hatch()
    o = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json")); assert o.attest(s); return s, o, pem

def applied(s, o):
    r = s.dwell_or_propose("verbosity", "evt", PREF)
    assert s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"])) is not None

def rechain(s):
    b = [{k: v for k, v in e.items() if k not in ("prev_hash", "entry_hash")} for e in s.trace]
    s.trace, s._trace_head = [], "0" * 64
    for x in b: s._append_trace(x)
    s._save()

def attempt(fn):
    try: return f"ACCEPTED ({fn()})"
    except (K.AttestationRefused, K.RollbackDetected, K.IntegrityError) as e: return f"refused: {type(e).__name__}: {e}"

# forged_record_metadata, with 'note' -> 'unverified_annotation'
d = Path(tempfile.mkdtemp()); s, o, _ = born(d); applied(s, o)
e = s.trace[-1]; e["record"]["authorized_at"] = "not a timestamp"
e["record"]["unverified_annotation"] = {"forged": "owner said yes; real owner note was empty"}; e["timestamp"] = -123456789.0
rechain(s)
print("forged_record_metadata (adapted) -> attest:", attempt(lambda: o.attest(s))[:200])

# witness_write_failure at each witness write inside attest
for which in (1, 2):
    d = Path(tempfile.mkdtemp()); s, o, pem = born(d); applied(s, o)
    real, calls = o.witness._persist, {"n": 0}
    def fail():
        calls["n"] += 1
        if calls["n"] == which: raise OSError(f"injected failure at witness write {which}")
        real()
    o.witness._persist = fail
    try: o.attest(s); print("no failure happened?")
    except OSError as ex: pass
    o2 = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json"))
    f = K.HumbleSeed(d / "org")
    if which == 1:
        print("witness write 1 (intent) fails -> retry attest:", attempt(lambda: o2.attest(s)),
              "| reload+audit:", attempt(lambda: (f.load(), o2.audit(f))[1]))
    else:
        f.load()
        print("witness write 2 (commit) fails -> reopen audit:", attempt(lambda: o2.audit(f)),
              "| witness seq:", K.OwnerWitness(d / "witness.json").ledger[s.organism_id]["sequence"])
