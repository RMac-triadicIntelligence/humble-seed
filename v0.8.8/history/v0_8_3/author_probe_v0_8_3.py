"""Author probes on v0.8.3, written while ChatGPT's sighted round was in progress
(after Grok's round-4 report, before ChatGPT's). Sealed before ChatGPT reports."""
import sys, json, tempfile, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("k", sys.argv[1]); K = importlib.util.module_from_spec(spec)
sys.modules["k"] = K; spec.loader.exec_module(K)
PREF = "I always prefer shorter answers"

def born(d):
    s = K.HumbleSeed(d / "org"); _, pem, _ = s.hatch()
    o = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json")); assert o.attest(s); return s, o, pem

def rechain(s):
    bodies = [{k: v for k, v in e.items() if k not in ("prev_hash", "entry_hash")} for e in s.trace]
    s.trace, s._trace_head = [], "0" * 64
    for b in bodies: s._append_trace(b)
    s._save()

def attest(o, s):
    try: return o.attest(s)
    except K.AttestationRefused as e: return f"REFUSED: {e}"

# A1: the docstring says the replay checks "every field". Two are not checked.
d = Path(tempfile.mkdtemp()); s, o, _ = born(d)
r = s.dwell_or_propose("verbosity", "evt", PREF)
s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
rec = s.trace[-1]["record"]; rec["note"] = "owner approved a 0.99 setting"; rec["authorized_at"] = "not a time"
rechain(s)
print("A1 record note + authorized_at rewritten -> attest:", attest(o, s))

# A2: two owner sessions on the same files. Each holds its own copy of the ledger in
# memory and writes the whole copy back, so one session's write can erase the other's.
d = Path(tempfile.mkdtemp()); s, o, pem = born(d)
A = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json"))
B = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json"))      # both open before anything happens
r = s.dwell_or_propose("verbosity", "evt", PREF); pid = r["proposal_id"]
sig = A.sign_proposal(r["payload_to_sign"])                    # A writes: signature
B.answer(s, pid, "no", "no")                                   # B writes its copy: answer only
fresh = K.OwnerLedger(d / "owner_ledger.json")
print("A2 after A signs, B answers 'no': ledger on disk has signature:",
      fresh.signed(s.organism_id, K._sha256(r["payload_to_sign"])) is not None,
      "| has the 'no':", fresh.answers_to(s.organism_id, pid))
r2 = s.dwell_or_propose("formality", "evt", "I prefer a casual tone always")
A.sign_proposal(r2["payload_to_sign"])                         # A writes its stale copy back
fresh = K.OwnerLedger(d / "owner_ledger.json")
print("A2 after A signs again: ledger on disk still has the 'no':", fresh.answers_to(s.organism_id, pid))
# With an honest organism the 'no' is still in its trace, so the organism-record veto holds.
# If the organism also hides that event, nothing is left to refuse the crossing:
s.reader = None
assert s.authorize_and_apply(pid, sig) is not None
s.trace = [e for e in s.trace if e.get("event") != "owner_answer"]; rechain(s)
C = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json"))      # a later session, from disk
print("A2 lost 'no' + organism hides its record -> attest:", attest(C, s))
