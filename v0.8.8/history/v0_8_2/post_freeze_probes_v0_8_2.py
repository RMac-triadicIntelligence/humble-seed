#!/usr/bin/env python3
"""
POST-FREEZE PROBES — v0.8.2 candidate. NOT part of the scored run.

Written by the author after the scored run (0 mismatches), to look at paths
no declared test exercises. Each probe states what it expects; outcomes are
reported as found. A probe that shows a gap is a finding for the record, not
something fixed silently.

Run:  python3 -I post_freeze_probes_v0_8_2.py
"""
import json
import importlib.util
import shutil
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("k082", HERE / "humble_seed_v0_8_2_candidate.py")
K = importlib.util.module_from_spec(spec)
sys.modules["k082"] = K
spec.loader.exec_module(K)

PREF = "I always prefer shorter answers"


def born(d):
    s = K.HumbleSeed(d / "org")
    _, pem, _ = s.hatch()
    o = K.OwnerTool(pem, K.OwnerWitness(d / "w.json"))
    assert o.attest(s)
    return s, o


def outcome(fn):
    try:
        r = fn()
        return f"ACCEPTED ({r!r})"
    except (K.AttestationRefused, K.IntegrityError, K.RollbackDetected) as e:
        return f"refused: {type(e).__name__}: {e}"


def P1_other_owner(d):
    """Expect refused: an owner tool must not attest an organism keyed to someone else."""
    s, _ = born(d / "a")
    _, other = born(d / "b")
    return outcome(lambda: other.attest(s))


def P1b_other_owner_at_enrollment(d):
    """Expect refused by the key check: P1 was stopped by the witness first, so try a
    freshly hatched, never-attested organism, which the other owner's witness would enroll."""
    s = K.HumbleSeed(d / "fresh")
    s.hatch()
    _, other = born(d / "b")
    return outcome(lambda: other.attest(s))


def P2_history_rewritten(d):
    """Expect refused: an attested dwelling's reason is rewritten and the chain rebuilt."""
    s, o = born(d)
    s.dwell_or_propose("formality", "evt", "hmm ok")
    assert o.attest(s)
    s.trace[2]["reason"] = "rewritten"
    bodies = [{k: v for k, v in e.items() if k not in ("prev_hash", "entry_hash")} for e in s.trace]
    s.trace, s._trace_head = [], "0" * 64
    for b in bodies:
        s._append_trace(b)
    return outcome(lambda: o.attest(s))


def P3_recorded_change_off_rule(d):
    """Expect refused: organism applies a signed reading but lands it at 0.40,
    and records 0.40 consistently (what a tampered derive would do)."""
    s, o = born(d)
    r = s.dwell_or_propose("verbosity", "evt", PREF)
    assert s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
    s.character["verbosity"] = 0.40
    rec = s.trace[-1]["record"]
    rec["change"] = {"verbosity": 0.40}
    bodies = [{k: v for k, v in e.items() if k not in ("prev_hash", "entry_hash")} for e in s.trace]
    s.trace, s._trace_head = [], "0" * 64
    for b in bodies:
        s._append_trace(b)
    return outcome(lambda: o.attest(s))


def P4_expired_reading_applied(d):
    """Expect ACCEPTED (a limit, not a fix): the organism's clock is wound back to
    apply a reading after its lifetime; the owner replay does not check lifetimes."""
    s, o = born(d)
    r = s.dwell_or_propose("verbosity", "evt", PREF)
    p = s.pending[r["proposal_id"]]
    sig = o.sign_proposal(r["payload_to_sign"])
    s.clock = lambda: p.expires_at + 10.0
    assert s.authorize_and_apply(r["proposal_id"], sig) is None          # honest clock: expired
    s.clock = lambda: p.timestamp + 1.0                                   # wound back
    applied = s.authorize_and_apply(r["proposal_id"], sig) is not None
    return f"applied with wound-back clock: {applied}; attest: " + outcome(lambda: o.attest(s))


def P5_destination_derivable_from_what_is_shown(d):
    """D3 says nothing SHOWN names the destination. It does not say the destination
    is unknowable: the rule is in the attested constitution the owner can read."""
    s, o = born(d)
    r = s.dwell_or_propose("verbosity", "evt", PREF)
    c = s.constitution
    p = json.loads(r["payload_to_sign"])
    derivable = min(c["value_range"][1], max(c["value_range"][0],
                    p["prior_value"] + c["derivation"]["label_to_delta"]["preference"]))
    res = s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
    return f"computed from prompt + constitution: {derivable}; applied: {res['record']['change']}"


def P6_r10_consistent_constitution_swap(d):
    """Extends lineage R10: the attacker keeps the swapped constitution internally
    consistent (new field in genesis_character, character and category_sequence),
    repairs the birth record, genesis hash and birth trace, re-chains and reseals."""
    s, o = born(d)

    def mutate(st):
        c = st["constitution"]
        c["allowed_character_fields"] = sorted(c["allowed_character_fields"] + ["obedience"])
        c["genesis_character"]["obedience"] = 1.0
        c["invariants"] = ["anything goes"]
        st["character"]["obedience"] = 1.0
        st["category_sequence"]["obedience"] = 0
        ch = K._sha256(K._canonical_json(c))
        st["birth"]["constitution_hash"] = ch
        st["birth"]["genesis_hash"] = K.HumbleSeed._derive_genesis(
            st["birth"]["organism_id"], st["birth"]["public_key_b64"], st["birth"]["created_at"], ch)
        st["trace"][0]["constitution_hash"] = ch
        st["trace"][0]["genesis_hash"] = st["birth"]["genesis_hash"]
    return K._reseal_attack(s, mutate, rechain=True)


PROBES = [P1_other_owner, P1b_other_owner_at_enrollment, P2_history_rewritten, P3_recorded_change_off_rule,
          P4_expired_reading_applied, P5_destination_derivable_from_what_is_shown,
          P6_r10_consistent_constitution_swap]

if __name__ == "__main__":
    print("POST-FREEZE PROBES — v0.8.2 candidate (not scored)\n")
    for p in PROBES:
        d = Path(tempfile.mkdtemp(prefix="hs082_probe_"))
        try:
            print(f"{p.__name__}\n  expect: {p.__doc__.strip().splitlines()[0]}\n  found:  {p(d)}\n")
        finally:
            shutil.rmtree(d, ignore_errors=True)
