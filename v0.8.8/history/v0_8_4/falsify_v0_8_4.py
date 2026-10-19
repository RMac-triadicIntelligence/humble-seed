#!/usr/bin/env python3
"""
Falsification harness for humble_seed_v0_8_4_candidate.py  (v0.8.4)

Written AFTER DECLARED_v0_8_4.json was frozen. The mutants are not defined
here: they are read from the frozen declaration, so the harness cannot drift
from what was predicted.

Discipline:
  #1  No verdict is printed that is not computed against the frozen file;
      exit code non-zero on any mismatch.
  #5  Every control has a mutant that removes it (exceptions listed in the
      declaration). KILLED = a test that PASSES on the candidate FAILS on the
      mutant. A test that ERRORS on a mutant is a crash, never a kill
      (ChatGPT, blind review round 2, finding #5).

Run:  python3 -I falsify_v0_8_4.py
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATE = HERE / "humble_seed_v0_8_4_candidate.py"
PARENT_V07 = HERE / "parent_humble_seed_v0_7_C5.py"
DECL = HERE / "DECLARED_v0_8_4.json"
DECL_SHA = HERE / "DECLARED_v0_8_4.sha256"
DECL_AT = HERE / "DECLARED_v0_8_4.frozen_at"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _cj(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def load_module(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


class Fail(Exception):
    """A declared assertion did not hold."""


def need(cond, msg):
    if not cond:
        raise Fail(msg)


# ---------------------------------------------------------------------------
# Helpers. Expected-success helpers convert only the system's own declared
# refusal types into FAIL; anything else escapes as an ERROR.
# ---------------------------------------------------------------------------

PREF = "I always prefer shorter answers"
CASUAL = "I prefer a casual tone always"
FEWER = "I always prefer you ask fewer questions"


def attest_ok(K, o, s):
    try:
        ok = o.attest(s)
    except (K.AttestationRefused, K.RollbackDetected) as e:
        raise Fail(f"attestation refused: {e}")
    need(ok is True, "attestation returned False")


def born(K, d: Path, **hatch_kw):
    s = K.HumbleSeed(d / "org")
    _, pem, _ = s.hatch(**hatch_kw)
    o = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json"))
    attest_ok(K, o, s)
    return s, o


def propose(s, cat, text=PREF):
    try:
        r = s.dwell_or_propose(cat, "evt", text)
    except ValueError as e:
        raise Fail(f"reading refused: {e}")
    need(r["status"] == "proposal", f"expected a proposal, got {r['status']}")
    return r


def dwell(s, cat, text):
    r = s.dwell_or_propose(cat, "evt", text)
    need(r["status"] == "dwelling", f"expected dwelling, got {r['status']}")


def apply_ok(K, s, o, r, attest=True):
    res = s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
    need(res is not None, f"expected apply, got {s.trace[-1].get('event')}: {s.trace[-1].get('reason')!r}")
    if attest:
        attest_ok(K, o, s)
    return res


def expect_reject(s, pid, sig, sub):
    out = s.authorize_and_apply(pid, sig)
    need(out is None, "expected rejection, but the reading was APPLIED")
    last = s.trace[-1]
    need(last.get("event") == "authorization_rejected",
         f"no rejection event (last event {last.get('event')!r})")
    need(sub in last.get("reason", ""), f"rejected for a different reason: {last.get('reason')!r}")
    return last["reason"]


def expect_hold(s, pid, sig, sub):
    out = s.authorize_and_apply(pid, sig)
    need(out is None, "expected a hold, but the reading was APPLIED")
    last = s.trace[-1]
    need(last.get("event") == "reading_held",
         f"expected reading_held, last event {last.get('event')!r} ({last.get('reason')!r})")
    need(sub in last.get("reason", ""), f"held for a different reason: {last.get('reason')!r}")
    return last["reason"]


def expect_integrity(K, data_dir: Path, sub):
    f = K.HumbleSeed(data_dir)
    try:
        f.load()
    except K.IntegrityError as e:
        need(sub in str(e), f"IntegrityError for a different reason: {str(e)!r}")
        return str(e)
    raise Fail("load ACCEPTED")


def expect_loads(K, data_dir: Path):
    f = K.HumbleSeed(data_dir)
    try:
        f.load()
    except K.IntegrityError as e:
        raise Fail(f"state does not load: {e}")
    return f


def audit_ok(K, o, f):
    try:
        need(o.audit(f) is True, "audit returned False")
    except (K.RollbackDetected, K.IntegrityError) as e:
        raise Fail(f"audit refused: {e}")


def expect_rollback(K, fn, sub):
    try:
        fn()
    except K.RollbackDetected as e:
        need(sub in str(e), f"RollbackDetected for a different reason: {str(e)!r}")
        return str(e)
    raise Fail("audit ACCEPTED")


def expect_refused(K, fn, sub):
    try:
        out = fn()
    except K.AttestationRefused as e:
        need(sub in str(e), f"refused for a different reason: {str(e)!r}")
        return str(e)
    raise Fail(f"attestation ACCEPTED (returned {out!r})")


def expect_value_error(fn, sub):
    try:
        fn()
    except ValueError as e:
        need(sub in str(e), f"ValueError for a different reason: {str(e)!r}")
        return str(e)
    raise Fail("ACCEPTED (no ValueError)")


def near(a, b):
    return abs(float(a) - float(b)) < 1e-12


def snapshot(s):
    return (dict(s.character), dict(s.category_sequence), sorted(s.consumed), s.mutation_sequence)


def _values(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _values(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _values(v)
    else:
        yield obj


SESSION = [
    ("verbosity", PREF),
    ("formality", "hmm ok"),
    ("formality", CASUAL),
    ("curiosity", "sorry, someone's at the door"),
    ("verbosity", "ok"),
    ("curiosity", FEWER),
    ("formality", "thanks"),
    ("verbosity", PREF),
]


def session_readings(s):
    out = []
    for cat, txt in SESSION:
        r = s.dwell_or_propose(cat, "evt", txt)
        if r["status"] == "proposal":
            out.append(r)
    return out


def sign_in_order(K, s, o, readings):
    applied, reasons = 0, []
    for r in readings:
        res = s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
        if res is not None:
            applied += 1
            attest_ok(K, o, s)
        else:
            reasons.append(s.trace[-1].get("reason", ""))
    return applied, reasons


# ---------------------------------------------------------------------------
# Carried tests (T1–T23), adapted to the v0.8.2 interface
# ---------------------------------------------------------------------------

def T1_liveness_intervening_events(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    for cat, txt in [("formality", "hmm ok"), ("verbosity", "ok"),
                     ("curiosity", "sorry, someone's at the door"),
                     ("verbosity", "thanks"), ("formality", "sure")]:
        dwell(s, cat, txt)
    need(s.authorize_and_apply("no-such-proposal", "AAAA") is None, "unknown id applied")
    attest_ok(K, o, s)
    apply_ok(K, s, o, r)
    need(near(s.character["verbosity"], 0.25), f"verbosity {s.character['verbosity']}")
    return "applied after 5 dwellings, 1 rejection event, 1 checkpoint; verbosity 0.25"


def T2_liveness_cross_category(K, d):
    s, o = born(K, d)
    rv = propose(s, "verbosity")
    rf = propose(s, "formality", CASUAL)
    sig_v = o.sign_proposal(rv["payload_to_sign"])
    apply_ok(K, s, o, rf)
    res = s.authorize_and_apply(rv["proposal_id"], sig_v)
    need(res is not None, f"verbosity reading rejected after formality commit: {s.trace[-1].get('reason')!r}")
    attest_ok(K, o, s)
    need(near(s.character["verbosity"], 0.25) and near(s.character["formality"], 0.25),
         f"character {s.character}")
    return "verbosity reading applied after a formality commit; both 0.25"


def T3_stale_same_category(K, d):
    s, o = born(K, d)
    a = propose(s, "verbosity")
    b = propose(s, "verbosity")
    sig_a = o.sign_proposal(a["payload_to_sign"])
    apply_ok(K, s, o, b)
    why = expect_reject(s, a["proposal_id"], sig_a, "category has advanced")
    need(near(s.character["verbosity"], 0.25), f"verbosity {s.character['verbosity']}")
    return why


def T4_second_crossing_at_clamp_floor(K, d):
    s, o = born(K, d)
    apply_ok(K, s, o, propose(s, "verbosity"))
    apply_ok(K, s, o, propose(s, "verbosity"))
    need(near(s.character["verbosity"], 0.0), f"verbosity {s.character['verbosity']}, expected floor")
    c = propose(s, "verbosity")
    e = propose(s, "verbosity")
    sig_c = o.sign_proposal(c["payload_to_sign"])
    apply_ok(K, s, o, e)
    need(near(s.character["verbosity"], 0.0) and s.category_sequence["verbosity"] == 3,
         f"after floor crossing: {s.character['verbosity']}, seq {s.category_sequence['verbosity']}")
    return expect_reject(s, c["proposal_id"], sig_c, "category has advanced")


def T5_payload_carries_no_destination_information(K, d):
    """ChatGPT, blind review round 2, finding #4: check values, not names."""
    s, o = born(K, d)
    r = propose(s, "verbosity")
    p = s.pending[r["proposal_id"]]
    dest = s.derive(p.category, p.distribution, p.prior_value)[2]
    need(near(dest, 0.25), f"derived destination {dest}")
    payload = json.loads(r["payload_to_sign"])
    for v in _values(payload):
        if isinstance(v, bool):
            continue
        need(not (isinstance(v, (int, float)) and near(v, dest)), f"payload carries the destination value {v!r}")
        need(not (isinstance(v, str) and v in (repr(dest), f"{dest:.2f}", f"{dest:.6f}")),
             f"payload carries the destination as text {v!r}")
    missing = {"evidence_root", "distribution_root", "prior_value", "category_sequence",
               "constitution_root"} - set(payload)
    need(not missing, f"payload lacks reading fields: {sorted(missing)}")
    table = s.constitution["derivation"]["label_to_delta"]
    saved = table["preference"]
    table["preference"] = -0.10
    try:
        r2 = propose(s, "verbosity")
    finally:
        table["preference"] = saved
    per_issue = {"proposal_id", "nonce", "timestamp", "expires_at", "constitution_root"}
    a = {k: v for k, v in payload.items() if k not in per_issue}
    b = {k: v for k, v in json.loads(r2["payload_to_sign"]).items() if k not in per_issue}
    diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    need(not diff, f"signed payload depends on the rule: {diff}")
    return f"{len(payload)} signed fields; no destination value; identical under delta -0.25 and -0.10"


def T6_rule_comes_from_constitution(K, d):
    saved = copy.deepcopy(K.GENESIS_DERIVATION)
    try:
        s, o = born(K, d)
        K.GENESIS_DERIVATION["label_to_delta"]["preference"] = -0.5
        apply_ok(K, s, o, propose(s, "verbosity"))
        need(near(s.character["verbosity"], 0.25),
             f"destination {s.character['verbosity']} did not use the constitution's rule")
        return "module constant edited to -0.5; destination still 0.25"
    finally:
        K.GENESIS_DERIVATION.clear()
        K.GENESIS_DERIVATION.update(saved)


def T7_constitution_pinned_at_apply(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    sig = o.sign_proposal(r["payload_to_sign"])
    s.constitution["derivation"]["label_to_delta"]["preference"] = 0.25
    return expect_reject(s, r["proposal_id"], sig, "derivation rule changed")


def T8_distribution_bound(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    sig = o.sign_proposal(r["payload_to_sign"])
    s.pending[r["proposal_id"]].distribution = {"preference": 0.9, "confound": 0.05,
                                                "unmodeled_cause": 0.05}
    return expect_reject(s, r["proposal_id"], sig, "envelope inconsistency")


def T9_evidence_bound(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    sig = o.sign_proposal(r["payload_to_sign"])
    s.pending[r["proposal_id"]].evidence = ["fabricated after signature"]
    return expect_reject(s, r["proposal_id"], sig, "envelope inconsistency")


def T10_replay(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    sig = o.sign_proposal(r["payload_to_sign"])
    saved = copy.deepcopy(s.pending[r["proposal_id"]])
    res = s.authorize_and_apply(r["proposal_id"], sig)
    need(res is not None, "first apply failed")
    attest_ok(K, o, s)
    s.pending[r["proposal_id"]] = saved
    return expect_reject(s, r["proposal_id"], sig, "replay")


def T11_expiry(K, d):
    s, o = born(K, d)
    r = propose(s, "curiosity", FEWER)
    p = s.pending[r["proposal_id"]]
    s.clock = lambda: p.expires_at + 1.0
    return expect_reject(s, r["proposal_id"], o.sign_proposal(r["payload_to_sign"]), "expired")


def T12_wrong_key(K, d):
    s, o = born(K, d)
    _, other = born(K, d / "other")
    r = propose(s, "verbosity")
    return expect_reject(s, r["proposal_id"], other.sign_proposal(r["payload_to_sign"]),
                         "invalid signature")


def T13_forged_first_commit(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    p = s.pending[r["proposal_id"]]
    need(p.first_commit is True, "first reading not flagged")
    p.first_commit = False
    p.payload_to_sign = s._reading_payload(p)
    p.payload_hash = K._sha256(p.payload_to_sign)
    return expect_reject(s, p.proposal_id, o.sign_proposal(p.payload_to_sign),
                         "first-commit mismatch")


def T14_forged_character_resealed(K, d):
    s, o = born(K, d)
    apply_ok(K, s, o, propose(s, "verbosity"))
    out = K._reseal_attack(s, lambda st: st["character"].__setitem__("verbosity", 0.99),
                           rechain=True)
    need(out.startswith("rejected:") and "Character does not match" in out, out)
    return out


def T15_category_sequences_resealed(K, d):
    s, o = born(K, d)
    apply_ok(K, s, o, propose(s, "verbosity"))

    def swap(st):
        st["category_sequence"] = {"verbosity": 0, "formality": 1, "curiosity": 0}
    out = K._reseal_attack(s, swap, rechain=True)
    need(out.startswith("rejected:") and "Category sequences do not match the attested" in out, out)
    return out


def T16_permissive_rule_full_birth_repair(K, d):
    s, o = born(K, d)

    def mutate(st):
        st["constitution"]["derivation"]["label_to_delta"]["preference"] = 0.25
        ch = K._sha256(K._canonical_json(st["constitution"]))
        st["birth"]["constitution_hash"] = ch
        st["birth"]["genesis_hash"] = K.HumbleSeed._derive_genesis(
            st["birth"]["organism_id"], st["birth"]["public_key_b64"],
            st["birth"]["created_at"], ch)
        st["trace"][0]["constitution_hash"] = ch
        st["trace"][0]["genesis_hash"] = st["birth"]["genesis_hash"]
    out = K._reseal_attack(s, mutate, rechain=True)
    need(out.startswith("rejected:")
         and "Birth record does not match the attested checkpoint" in out, out)
    return out


def T17_unattested_apply_fails_closed(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    res = s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
    need(res is not None, "apply failed")
    return expect_integrity(K, s.data_dir, "Category sequences do not match the attested")


def T18_rollback_witness_only(K, d):
    s, o = born(K, d)
    apply_ok(K, s, o, propose(s, "verbosity"))
    snap = s._state_path().read_text()
    apply_ok(K, s, o, propose(s, "formality", CASUAL))
    s._state_path().write_text(snap)
    rolled = expect_loads(K, s.data_dir)       # must load: the organism cannot see its rollback
    return expect_rollback(K, lambda: o.audit(rolled), "Rollback")


def T19_identity_replacement_audit(K, d):
    s, o = born(K, d)
    evil, _ = born(K, d / "evil")
    shutil.copy(evil._state_path(), s._state_path())
    replaced = expect_loads(K, s.data_dir)
    need(replaced.organism_id != s.organism_id, "replacement did not take")
    return expect_rollback(K, lambda: o.audit(replaced), "Unknown organism")


def run_session_parent(P, d):
    """v0.7 interface, unchanged from the v0.8.1 harness."""
    s = P.HumbleSeed(d / "org")
    oid, pem, g = s.hatch()
    o = P.OwnerTool(pem, P.OwnerWitness(d / "witness.json"))
    need(o.attest(s, g), "genesis attestation failed")
    readings = []
    for cat, txt in SESSION:
        r = s.dwell_or_propose(cat, "evt", txt)
        if r["status"] == "proposal":
            readings.append(r)
    applied, reasons = 0, []
    for r in readings:
        cp = s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
        if cp is not None:
            applied += 1
            need(o.attest(s, cp), "attestation failed")
        else:
            reasons.append(s.trace[-1].get("reason", ""))
    return len(readings), applied, reasons


def T20_realistic_session(K, d):
    s, o = born(K, d / "v084")
    readings = session_readings(s)
    need(len(readings) == 4, f"{len(readings)} readings issued, expected 4")
    applied, reasons = sign_in_order(K, s, o, readings)
    need(applied == 3, f"applied {applied} of 4, expected 3; reasons {reasons}")
    need(len(reasons) == 1 and "category has advanced" in reasons[0], f"rejections {reasons}")
    ch = s.character
    need(near(ch["verbosity"], 0.25) and near(ch["formality"], 0.25) and near(ch["curiosity"], 0.35),
         f"final character {ch}")
    P = load_module(PARENT_V07, "parent_v07_session")
    pn, papplied, preasons = run_session_parent(P, d / "v07")
    need(pn == 4 and papplied == 0, f"parent v0.7 applied {papplied} of {pn}, expected 0 of 4")
    return (f"v0.8.4 applied {applied}/4 (rejected: {reasons[0]!r}); "
            f"parent v0.7 applied {papplied}/{pn} (first reason: {preasons[0]!r})")


def T21_prior_value_detects_independent_change(K, d):
    """Grok, blind review round 1."""
    s, o = born(K, d)
    r = propose(s, "verbosity")
    s.character["verbosity"] = 0.0
    return expect_reject(s, r["proposal_id"], o.sign_proposal(r["payload_to_sign"]),
                         "category value differs from the value read")


def T22_unattested_tail_check_reachable(K, d):
    """Grok, blind review round 1."""
    s, o = born(K, d)

    def mutate(st):
        st["trace"].append({"event": "authorized_mutation",
                            "record": {"proposal_id": "fake"}, "timestamp": 1.0})
    out = K._reseal_attack(s, mutate, rechain=True)
    need(out.startswith("rejected:") and "Unattested authorizing event" in out, out)
    return out


def T23_tamper_evidence_preserved(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    s.character["verbosity"] = 0.0
    res = s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
    if res is not None:
        attest_ok(K, o, s)
    return expect_integrity(K, s.data_dir, "Character does not match the attested")


# ---------------------------------------------------------------------------
# New tests (T24–T40)
# ---------------------------------------------------------------------------

def T24_nonfinite_reading_refused(K, d):
    """ChatGPT, blind review round 2, finding #1."""
    s, o = born(K, d)
    for bad in (float("nan"), float("inf"), float("-inf")):
        expect_value_error(lambda bad=bad: s._issue_pending_proposal(
            "verbosity", {"preference": bad, "confound": 0.5, "unmodeled_cause": 0.5},
            ["non-finite reading"]), "finite")
    need(not s.pending, "a non-finite reading is pending")
    basin_before = len(s.basin)
    s.interpret = lambda event, transcript: {"preference": float("nan"), "confound": 0.5,
                                             "unmodeled_cause": 0.5}
    r = s.dwell_or_propose("verbosity", "evt", "anything")
    need(r["status"] == "dwelling" and r.get("unreadable") is True, f"interpreter NaN gave {r}")
    need(not s.pending and len(s.basin) == basin_before, "unreadable reading left a trace in pending/basin")
    f = expect_loads(K, s.data_dir)
    audit_ok(K, o, f)
    return "NaN, +inf, -inf refused at issuance; NaN interpreter output held as unreadable"


def T25_clamp_comes_from_constitution(K, d):
    """ChatGPT, blind review round 2, finding #2."""
    saved = K.GENESIS_VALUE_RANGE
    try:
        s, o = born(K, d)
        K.GENESIS_VALUE_RANGE = (0.4, 1.0)
        apply_ok(K, s, o, propose(s, "verbosity"))
        need(near(s.character["verbosity"], 0.25),
             f"destination {s.character['verbosity']}: clamp did not come from the constitution")
        f = expect_loads(K, s.data_dir)
        audit_ok(K, o, f)
        return "module range edited to (0.4, 1.0) after hatch; destination still 0.25"
    finally:
        K.GENESIS_VALUE_RANGE = saved


def T26_attest_refuses_unsigned_change(K, d):
    """ChatGPT, blind review round 2, finding #3 (D4)."""
    s, o = born(K, d)
    r = propose(s, "verbosity")
    sig = o.sign_proposal(r["payload_to_sign"])
    s.character["formality"] = 0.99
    res = s.authorize_and_apply(r["proposal_id"], sig)
    need(res is not None, f"verbosity apply failed: {s.trace[-1].get('reason')!r}")
    why = expect_refused(K, lambda: o.attest(s), "record fields differ from the replay")
    need("formality: recorded 0.99" in why, f"refusal does not name the changed category: {why!r}")
    need(o.witness.ledger[s.organism_id]["sequence"] == 0, "witness advanced")
    expect_integrity(K, s.data_dir, "Category sequences do not match the attested")
    st = json.loads(s._state_path().read_text())
    need(st["character"]["formality"] == 0.99, "tamper not preserved in the stored state")
    return why


def T27_checkpoint_built_at_signing_time(K, d):
    """ChatGPT, blind review round 2, observation."""
    s, o = born(K, d)
    apply_ok(K, s, o, propose(s, "verbosity"), attest=False)
    dwell(s, "formality", "hmm ok")
    attest_ok(K, o, s)
    f = expect_loads(K, s.data_dir)
    audit_ok(K, o, f)
    return "dwelling between apply and attest; attestation and audit succeed"


def T28_reading_survives_a_day(K, d):
    """Author finding: v0.8.1's one-hour lifetime killed same-day signing."""
    saved = K.GENESIS_READING_TTL_SECONDS
    try:
        s, o = born(K, d)
        K.GENESIS_READING_TTL_SECONDS = 3600.0
        readings = session_readings(s)
        need(len(readings) == 4, f"{len(readings)} readings issued, expected 4")
        later = time.time() + 25 * 3600
        s.clock = lambda: later
        applied, reasons = sign_in_order(K, s, o, readings)
        need(applied == 3 and len(reasons) == 1 and "category has advanced" in reasons[0],
             f"signed 25 h later: applied {applied}, rejections {reasons}")
        ch = s.character
        need(near(ch["verbosity"], 0.25) and near(ch["formality"], 0.25) and near(ch["curiosity"], 0.35),
             f"final character {ch}")
    finally:
        K.GENESIS_READING_TTL_SECONDS = saved
    s2, o2 = born(K, d / "two_day", reading_ttl_seconds=172800.0)
    need(s2.constitution["reading_ttl_seconds"] == 172800.0, "chosen lifetime not in the constitution")
    r2 = propose(s2, "verbosity")
    p2 = s2.pending[r2["proposal_id"]]
    need(abs(p2.expires_at - p2.timestamp - 172800.0) < 1e-6, "reading lifetime differs from the chosen one")
    return "signed 25 h after the session: 3/4 applied; a 2-day lifetime chosen at hatch is honoured"


def T29_allowed_fields_come_from_constitution(K, d):
    saved = set(K.GENESIS_ALLOWED_FIELDS)
    try:
        s, o = born(K, d)
        K.GENESIS_ALLOWED_FIELDS = {"verbosity", "formality", "humor"}
        apply_ok(K, s, o, propose(s, "curiosity", FEWER))
        need(near(s.character["curiosity"], 0.35), f"curiosity {s.character['curiosity']}")
        f = expect_loads(K, s.data_dir)
        audit_ok(K, o, f)
        expect_value_error(lambda: s.dwell_or_propose("humor", "evt", PREF), "Unknown character category")
        return "module fields edited after hatch; curiosity still allowed, humor still refused"
    finally:
        K.GENESIS_ALLOWED_FIELDS = saved


def T30_D1_owner_no_holds(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    pid = r["proposal_id"]
    before = snapshot(s)
    ans = s.record_owner_answer(pid, "no", "no, I like detail")
    need(ans.get("authorizes") is False, f"answer response {ans}")
    sig = o.sign_proposal(r["payload_to_sign"])
    why = expect_hold(s, pid, sig, "owner's position")
    need(set(s.pending) == {pid}, f"pending after hold: {sorted(s.pending)}")
    need(snapshot(s) == before, "state changed on a hold")
    f = expect_loads(K, s.data_dir)
    audit_ok(K, o, f)
    expect_hold(s, pid, sig, "owner's position")
    return why


def T31_D1_hold_never_crosses_or_reproposes(K, d):
    s, o = born(K, d)
    s.reader = lambda reading, terrain, since: "test reader: always objects"
    readings = session_readings(s)
    need(len(readings) == 4, f"{len(readings)} readings issued, expected 4")
    ids = {r["proposal_id"] for r in readings}
    for r in readings:
        expect_hold(s, r["proposal_id"], o.sign_proposal(r["payload_to_sign"]), "always objects")
    need(set(s.pending) == ids, f"pending changed: {len(s.pending)} readings")
    need(s.character == s.constitution["genesis_character"], f"character {s.character}")
    need(all(n == 0 for n in s.category_sequence.values()) and not s.consumed
         and s.mutation_sequence == 0, "a hold advanced the state")
    f = expect_loads(K, s.data_dir)
    audit_ok(K, o, f)
    return "4 signed readings, 4 holds, 0 crossings, 0 new readings"


def T32_D1_reader_failure_holds(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    pid, sig = r["proposal_id"], o.sign_proposal(r["payload_to_sign"])

    def boom(*a):
        raise RuntimeError("reader crashed")
    s.reader = boom
    first = expect_hold(s, pid, sig, "reader failed")
    s.reader = lambda *a: 42
    expect_hold(s, pid, sig, "not a reason")
    s.reader = lambda *a: "   "
    expect_hold(s, pid, sig, "not a reason")
    need(near(s.character["verbosity"], 0.5) and pid in s.pending and s.mutation_sequence == 0,
         "a failing reader let something through")
    return first


def T33_D1_reader_cannot_alter_reading(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    payload = json.loads(r["payload_to_sign"])

    def hostile(reading, terrain, since):
        reading["distribution"]["preference"] = 0.99
        reading["distribution"]["confound"] = 0.01
        reading["distribution"]["unmodeled_cause"] = 0.0
        reading["prior_value"] = 1.0
        reading["evidence"].append("planted by the reader")
        terrain.clear()
        for e in since:
            e["event"] = "planted"
        return None
    s.reader = hostile
    res = apply_ok(K, s, o, r, attest=False)
    rec = res["record"]
    need(K._sha256(K._canonical_json(rec["distribution"])) == payload["distribution_root"],
         "applied distribution differs from the signed one")
    need(K._sha256(K._canonical_json(rec["evidence"])) == payload["evidence_root"],
         "applied evidence differs from the signed evidence")
    need(rec["prior_value"] == payload["prior_value"], f"applied prior {rec['prior_value']}")
    need(near(s.character["verbosity"], 0.25), f"verbosity {s.character['verbosity']}")
    attest_ok(K, o, s)
    return "reader mutated its copies; applied record matches the signed reading"


def T34_D1_unrelated_answers_do_not_hold(K, d):
    s, o = born(K, d)
    rv = propose(s, "verbosity")
    rf = propose(s, "formality", CASUAL)
    s.record_owner_answer(rf["proposal_id"], "no")
    s.record_owner_answer(rv["proposal_id"], "yes")
    apply_ok(K, s, o, rv)
    need(near(s.character["verbosity"], 0.25), f"verbosity {s.character['verbosity']}")
    rf2 = propose(s, "formality", CASUAL)
    apply_ok(K, s, o, rf2)
    need(near(s.character["formality"], 0.25), f"formality {s.character['formality']}")
    return "'no' in another category and 'yes' do not hold; an earlier 'no' does not hold a later reading"


def T35_D2_answer_is_evidence_not_authority(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    pid = r["proposal_id"]
    before = snapshot(s)
    ans = s.record_owner_answer(pid, "yes", "yes, shorter please")
    need(ans.get("authorizes") is False, f"answer response {ans}")
    need(snapshot(s) == before, "an answer changed the state")
    need(pid in s.pending and s.pending[pid].payload_to_sign == r["payload_to_sign"],
         "an answer altered the pending reading")
    last = s.trace[-1]
    need(last.get("event") == "owner_answer" and last.get("answer") == "yes", f"last event {last.get('event')}")
    b = s.basin[-1]
    need(b.source == "owner_answer" and b.answer == "yes" and b.about == pid and b.category == "verbosity",
         f"newest basin entry {asdict(b)}")
    f = expect_loads(K, s.data_dir)
    audit_ok(K, o, f)
    apply_ok(K, s, o, r)
    need(near(s.character["verbosity"], 0.25), f"verbosity {s.character['verbosity']}")
    return "answer recorded as non-authorizing evidence; signature still the only authority"


def T36_D2_prompts_separate_and_deterministic(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    pid = r["proposal_id"]
    q, a = r["question"], r["authorization_prompt"]
    need(q != a, "question and authorization are the same text")
    pr = K.render_prompts(asdict(s.pending[pid]), s.constitution)
    need(pr["question"] == q and pr["authorization"] == a, "prompts are not render_prompts of the reading")
    f = expect_loads(K, s.data_dir)
    need(K.render_prompts(asdict(f.pending[pid]), f.constitution) == pr, "prompts differ after reload")
    need(PREF in q and q.endswith("(yes / no / unsure)"), f"question {q!r}")
    for piece in ("verbosity", "0.00–1.00", "7 days", "does not choose where it lands"):
        need(piece in a, f"authorization lacks {piece!r}: {a!r}")
    return a


def T37_D3_nothing_before_signing_depends_on_rule(K, d):
    s, o = born(K, d)
    r1 = propose(s, "verbosity")
    p = s.pending[r1["proposal_id"]]
    dest = s.derive(p.category, p.distribution, p.prior_value)[2]
    table = s.constitution["derivation"]["label_to_delta"]
    saved = table["preference"]
    table["preference"] = -0.10
    try:
        r2 = propose(s, "verbosity")
    finally:
        table["preference"] = saved

    def strip(r):
        return {k: v for k, v in r.items() if k not in ("proposal_id", "payload_to_sign")}
    a, b = strip(r1), strip(r2)
    diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    need(not diff, f"owner-facing response depends on the rule: {diff}")
    for v in _values(a):
        if isinstance(v, bool):
            continue
        need(not (isinstance(v, (int, float)) and near(v, dest)), f"response carries {v!r}")
        need(not (isinstance(v, str) and (f"{dest:.2f}" in v or repr(dest) in v)),
             f"response text carries the destination: {v!r}")
    return "owner-facing response identical under delta -0.25 and -0.10; no destination in it"


def T38_D3_consequence_rendered_from_record(K, d):
    s, o = born(K, d)
    res = apply_ok(K, s, o, propose(s, "verbosity"))
    f = expect_loads(K, s.data_dir)
    rec = [e["record"] for e in f.trace if e.get("event") == "authorized_mutation"][-1]
    need(res["consequence"] == K.render_consequence(rec), "consequence is not rendered from the record")
    need("verbosity 0.50 → 0.25" in res["consequence"], f"consequence {res['consequence']!r}")
    apply_ok(K, s, o, propose(s, "verbosity"))
    res3 = apply_ok(K, s, o, propose(s, "verbosity"))
    need("already at the edge of its range" in res3["consequence"], f"floor consequence {res3['consequence']!r}")
    return res["consequence"]


def T39_D4_attest_refuses_forged_reading(K, d):
    s, o = born(K, d)
    _, stranger = born(K, d / "stranger")
    r = propose(s, "formality", CASUAL)
    p = s.pending[r["proposal_id"]]
    sig = stranger.sign_proposal(p.payload_to_sign)
    lead, delta, dest = s.derive(p.category, p.distribution, p.prior_value)
    prior = dict(s.character)
    s.character["formality"] = dest
    s.category_sequence["formality"] += 1
    s.consumed.add(f"{p.proposal_id}|{p.nonce}")
    s.mutation_sequence += 1
    del s.pending[p.proposal_id]
    rec = K.MutationRecord(
        proposal_id=p.proposal_id, category="formality", lead=lead, delta=delta,
        prior_value=p.prior_value, change={"formality": dest}, distribution=p.distribution,
        evidence=p.evidence, first_commit=p.first_commit,
        category_sequence=s.category_sequence["formality"], mutation_sequence=s.mutation_sequence,
        authorized_at=time.time(), signature_b64=sig, signed_payload=p.payload_to_sign,
        prior_character_snapshot=prior)
    s._append_trace({"event": "authorized_mutation", "record": asdict(rec), "timestamp": rec.authorized_at})
    s._save()
    why = expect_refused(K, lambda: o.attest(s), "does not verify under the owner's key")
    need(o.witness.ledger[s.organism_id]["sequence"] == 0, "witness advanced")
    return why


def T40_nonfinite_never_parsed_or_written(K, d):
    """ChatGPT finding #1 at the parse and write boundaries; 1e999 variant: author."""
    for raw in ('{"preference": NaN, "confound": 0.5, "unmodeled_cause": 0.5}',
                '{"preference": Infinity, "confound": 0.0, "unmodeled_cause": 0.0}',
                '{"preference": -Infinity, "confound": 0.5, "unmodeled_cause": 0.5}',
                '{"preference": 1e999, "confound": 0.0, "unmodeled_cause": 0.0}'):
        expect_value_error(lambda raw=raw: K.parse_reading_json(raw), "non-finite constant")
    s, o = born(K, d / "a")
    st = json.loads(s._state_path().read_text())
    st["character"]["verbosity"] = float("nan")
    s._state_path().write_text(json.dumps(st, sort_keys=True, separators=(",", ":")))
    expect_integrity(K, s.data_dir, "non-finite constant")
    s2, o2 = born(K, d / "b")
    before = s2._state_path().read_text()
    s2.character["verbosity"] = float("nan")
    expect_value_error(lambda: s2._save(), "not JSON compliant")
    need(s2._state_path().read_text() == before, "state file changed")
    return "refused at parse (4 literals), at load, and at write"


TESTS = [T1_liveness_intervening_events, T2_liveness_cross_category, T3_stale_same_category,
         T4_second_crossing_at_clamp_floor, T5_payload_carries_no_destination_information,
         T6_rule_comes_from_constitution, T7_constitution_pinned_at_apply,
         T8_distribution_bound, T9_evidence_bound, T10_replay, T11_expiry, T12_wrong_key,
         T13_forged_first_commit, T14_forged_character_resealed,
         T15_category_sequences_resealed, T16_permissive_rule_full_birth_repair,
         T17_unattested_apply_fails_closed, T18_rollback_witness_only,
         T19_identity_replacement_audit, T20_realistic_session,
         T21_prior_value_detects_independent_change, T22_unattested_tail_check_reachable,
         T23_tamper_evidence_preserved, T24_nonfinite_reading_refused,
         T25_clamp_comes_from_constitution, T26_attest_refuses_unsigned_change,
         T27_checkpoint_built_at_signing_time, T28_reading_survives_a_day,
         T29_allowed_fields_come_from_constitution, T30_D1_owner_no_holds,
         T31_D1_hold_never_crosses_or_reproposes, T32_D1_reader_failure_holds,
         T33_D1_reader_cannot_alter_reading, T34_D1_unrelated_answers_do_not_hold,
         T35_D2_answer_is_evidence_not_authority, T36_D2_prompts_separate_and_deterministic,
         T37_D3_nothing_before_signing_depends_on_rule, T38_D3_consequence_rendered_from_record,
         T39_D4_attest_refuses_forged_reading, T40_nonfinite_never_parsed_or_written]


# ---------------------------------------------------------------------------
# New in v0.8.3 (T41–T48): the owner keeps its own record
# ---------------------------------------------------------------------------

def rechain(s):
    bodies = [{k: v for k, v in e.items() if k not in ("prev_hash", "entry_hash")} for e in s.trace]
    s.trace, s._trace_head = [], "0" * 64
    for b in bodies:
        s._append_trace(b)
    s._save()


def witness_seq(o, s):
    return o.witness.ledger[s.organism_id]["sequence"]


def T41_owner_ledger_refuses_held_crossing(K, d):
    """ChatGPT, round 3, F1b — answer given through the owner tool."""
    s, o = born(K, d)
    r = propose(s, "verbosity")
    pid = r["proposal_id"]
    sig = o.sign_proposal(r["payload_to_sign"])
    o.answer(s, pid, "no", "no")
    expect_hold(s, pid, sig, "owner's position")
    s.reader = None
    res = s.authorize_and_apply(pid, sig)
    need(res is not None, f"organism did not apply with its reader off: {s.trace[-1].get('reason')!r}")
    o2 = K.OwnerTool(o._pem, K.OwnerWitness(d / "witness.json"))        # rebuilt from its files
    why = expect_refused(K, lambda: o2.attest(s), "owner's position")
    need(witness_seq(o2, s) == 0, "witness advanced")
    return why


def T42_owner_clock_lifetime(K, d):
    """ChatGPT round 3 F1a; author R19 — lifetime on the owner's clock."""
    s, o = born(K, d)
    apply_ok(K, s, o, propose(s, "verbosity"), attest=False)
    later = time.time() + K.policy_ttl(s.constitution) + 60.0
    o.clock = lambda: later
    why = expect_refused(K, lambda: o.attest(s), "past its lifetime by the owner's clock")
    need(witness_seq(o, s) == 0, "witness advanced")
    return why


def T43_organism_expiry_record_honored(K, d):
    """ChatGPT, round 3, F1a — the organism's own 'expired' record is a veto."""
    s, o = born(K, d)
    r = propose(s, "verbosity")
    pid = r["proposal_id"]
    sig = o.sign_proposal(r["payload_to_sign"])
    exp, t0 = s.pending[pid].expires_at, s.pending[pid].timestamp
    s.clock = lambda: exp + 60.0
    expect_reject(s, pid, sig, "expired")
    s.clock = lambda: t0 + 1.0
    res = s.authorize_and_apply(pid, sig)
    need(res is not None, f"wound-back apply failed: {s.trace[-1].get('reason')!r}")
    s.clock = time.time
    why = expect_refused(K, lambda: o.attest(s), "recorded this reading as expired")
    need(witness_seq(o, s) == 0, "witness advanced")
    return why


def T44_replay_checks_every_record_field(K, d):
    """ChatGPT, round 3, F2."""
    out = []
    for field in ("prior_value", "first_commit", "prior_character_snapshot"):
        s, o = born(K, d / field)
        apply_ok(K, s, o, propose(s, "verbosity"), attest=False)
        rec = s.trace[-1]["record"]
        if field == "prior_value":
            rec["prior_value"] = 0.0
        elif field == "first_commit":
            rec["first_commit"] = False
        else:
            rec["prior_character_snapshot"]["verbosity"] = 0.0
        rechain(s)
        out.append(expect_refused(K, lambda: o.attest(s), "record fields differ from the replay"))
    return " | ".join(out)


def T45_D2_corrected_answer_releases_hold(K, d):
    """Author finding, round 3; ruling 3."""
    s, o = born(K, d / "a")
    r = propose(s, "verbosity")
    o.answer(s, r["proposal_id"], "no")
    o.answer(s, r["proposal_id"], "yes")
    apply_ok(K, s, o, r)
    need(near(s.character["verbosity"], 0.25), f"verbosity {s.character['verbosity']}")

    s, o = born(K, d / "b")
    x, y = propose(s, "verbosity"), propose(s, "verbosity")
    o.answer(s, x["proposal_id"], "no")
    o.answer(s, y["proposal_id"], "yes")
    expect_hold(s, x["proposal_id"], o.sign_proposal(x["payload_to_sign"]),
                "latest answer to this reading is 'no'")

    s, o = born(K, d / "c")
    x, y = propose(s, "verbosity"), propose(s, "verbosity")
    o.answer(s, x["proposal_id"], "yes")
    o.answer(s, y["proposal_id"], "no")
    expect_hold(s, x["proposal_id"], o.sign_proposal(x["payload_to_sign"]),
                "latest answer in this category since the reading was taken is 'no'")
    return "no->yes applies; no(X)+yes(Y) holds X; yes(X)+no(Y) holds X"


def T46_reading_must_be_signed_through_owner_tool(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    sig = K.owner_sign_external(o._pem, r["payload_to_sign"])
    res = s.authorize_and_apply(r["proposal_id"], sig)
    need(res is not None, f"apply failed: {s.trace[-1].get('reason')!r}")
    return expect_refused(K, lambda: o.attest(s), "not signed through this owner tool")


def T47_forged_yes_does_not_reach_attestation(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    pid = r["proposal_id"]
    sig = o.sign_proposal(r["payload_to_sign"])
    o.answer(s, pid, "no", "no")
    s.record_owner_answer(pid, "yes", "forged: written to the organism, not by the owner")
    res = s.authorize_and_apply(pid, sig)
    need(res is not None, f"organism did not release on its latest answer: {s.trace[-1].get('reason')!r}")
    why = expect_refused(K, lambda: o.attest(s), "owner's position")
    need(witness_seq(o, s) == 0, "witness advanced")
    return why


def T48_organism_recorded_no_honored(K, d):
    """ChatGPT, round 3, F1b — its exact case: the 'no' reaches the organism only."""
    s, o = born(K, d)
    r = propose(s, "verbosity")
    pid = r["proposal_id"]
    sig = o.sign_proposal(r["payload_to_sign"])
    s.record_owner_answer(pid, "no", "no")
    expect_hold(s, pid, sig, "owner's position")
    s.reader = None
    res = s.authorize_and_apply(pid, sig)
    need(res is not None, f"organism did not apply with its reader off: {s.trace[-1].get('reason')!r}")
    why = expect_refused(K, lambda: o.attest(s), "organism's own record holds this reading")
    need(witness_seq(o, s) == 0, "witness advanced")
    return why


TESTS = TESTS + [T41_owner_ledger_refuses_held_crossing, T42_owner_clock_lifetime,
                 T43_organism_expiry_record_honored, T44_replay_checks_every_record_field,
                 T45_D2_corrected_answer_releases_hold, T46_reading_must_be_signed_through_owner_tool,
                 T47_forged_yes_does_not_reach_attestation, T48_organism_recorded_no_honored]


# ---------------------------------------------------------------------------
# New in v0.8.4 (T49–T56): one owner authority, recoverable commit, provenance
# ---------------------------------------------------------------------------

def reopen(K, o, d):
    return K.OwnerTool(o._pem, K.OwnerWitness(d / "witness.json"))


def fresh_witness_seq(K, d, s):
    return K.OwnerWitness(d / "witness.json").ledger[s.organism_id]["sequence"]


def T49_stale_session_cannot_bypass_owner_no(K, d):
    """ChatGPT, round 4, F1 (stale_owner_veto_bypass)."""
    s, o = born(K, d)
    r = propose(s, "verbosity")
    pid = r["proposal_id"]
    sig = o.sign_proposal(r["payload_to_sign"])
    b = reopen(K, o, d)
    b.answer(s, pid, "no", "no")
    s.record_owner_answer(pid, "yes", "forged: written to the organism only")
    res = s.authorize_and_apply(pid, sig)
    need(res is not None, f"organism did not apply: {s.trace[-1].get('reason')!r}")
    why = expect_refused(K, lambda: o.attest(s), "owner's position")
    need(fresh_witness_seq(K, d, s) == 0, "witness advanced")
    return why


def T50_stale_session_keeps_other_sessions_records(K, d):
    """ChatGPT, round 4, F1 (stale_owner_erases_signature); author A2."""
    s, o = born(K, d)
    b = reopen(K, o, d)                      # opened before A signs
    r = propose(s, "verbosity")
    pid = r["proposal_id"]
    sig = o.sign_proposal(r["payload_to_sign"])
    b.answer(s, pid, "yes", "yes")
    res = s.authorize_and_apply(pid, sig)
    need(res is not None, f"organism did not apply: {s.trace[-1].get('reason')!r}")
    attest_ok(K, reopen(K, o, d), s)
    need(near(s.character["verbosity"], 0.25), f"verbosity {s.character['verbosity']}")
    return "signature survived another session's write; fresh session attests"


def T51_stale_witness_cannot_fork(K, d):
    """ChatGPT, round 4, F2 (stale_witness_fork)."""
    s, o = born(K, d)
    b = reopen(K, o, d)
    shutil.copytree(s.data_dir, d / "org_copy")
    s1 = expect_loads(K, s.data_dir)
    s2 = expect_loads(K, d / "org_copy")
    apply_ok(K, s1, o, propose(s1, "verbosity"))
    r2 = propose(s2, "formality", CASUAL)
    res = s2.authorize_and_apply(r2["proposal_id"], b.sign_proposal(r2["payload_to_sign"]))
    need(res is not None, f"branch 2 did not apply: {s2.trace[-1].get('reason')!r}")
    why = expect_rollback(K, lambda: b.attest(s2), "Non-successor")
    try:
        K.OwnerWitness(d / "witness.json").check_current(s1.checkpoint)
    except K.RollbackDetected as e:
        raise Fail(f"fresh witness rejects the legitimate branch: {e}")
    return why


def T52_record_metadata_validated(K, d):
    """ChatGPT, round 4, F3; author A1."""
    cases = [
        ("finite", "authorized_at is not a finite number"),
        ("window", "authorized_at outside the reading's own window"),
        ("event", "event timestamp differs from authorized_at"),
        ("annotation", "unverified_annotation is not a short string"),
    ]
    out = []
    for name, expect in cases:
        s, o = born(K, d / name)
        apply_ok(K, s, o, propose(s, "verbosity"), attest=False)
        entry = s.trace[-1]
        rec = entry["record"]
        pl = json.loads(rec["signed_payload"])
        if name == "finite":
            rec["authorized_at"] = entry["timestamp"] = "not a timestamp"
        elif name == "window":
            rec["authorized_at"] = entry["timestamp"] = float(pl["timestamp"]) - 1000.0
        elif name == "event":
            entry["timestamp"] = -123456789.0
        else:
            rec["unverified_annotation"] = {"forged": "owner said yes"}
        rechain(s)
        why = expect_refused(K, lambda: o.attest(s), "record metadata invalid")
        need(expect in why, f"{name}: refused without naming it: {why!r}")
        out.append(name)
    return "refused: " + ", ".join(out)


def T53_lifetime_runs_from_first_signing(K, d):
    """ChatGPT, round 4, F1 (stale_signer_refreshes_lifetime) and its control."""
    s, o = born(K, d, reading_ttl_seconds=10.0)
    b = reopen(K, o, d)                      # opened before the first signing
    r = propose(s, "verbosity")
    t0 = time.time()
    o.clock = lambda: t0
    sig = o.sign_proposal(r["payload_to_sign"])
    b.clock = lambda: t0 + 11.0
    b.sign_proposal(r["payload_to_sign"])
    o.sign_proposal(r["payload_to_sign"])
    res = s.authorize_and_apply(r["proposal_id"], sig)
    need(res is not None, f"organism did not apply: {s.trace[-1].get('reason')!r}")
    o.clock = lambda: t0 + 11.0
    return expect_refused(K, lambda: o.attest(s), "past its lifetime by the owner's clock")


def T54_commit_recovers_after_organism_install(K, d):
    """ChatGPT, round 4, F4 (witness_write_failure)."""
    s, o = born(K, d)
    apply_ok(K, s, o, propose(s, "verbosity"), attest=False)
    real = s.install_checkpoint

    def crash_after(cp, sig):
        real(cp, sig)
        raise OSError("interrupted after the organism installed")
    s.install_checkpoint = crash_after
    try:
        o.attest(s)
    except OSError:
        pass
    else:
        raise Fail("injected interruption did not happen")
    f = expect_loads(K, s.data_dir)
    o2 = reopen(K, o, d)
    audit_ok(K, o2, f)
    need(fresh_witness_seq(K, d, f) == 1, "witness did not complete the commit")
    apply_ok(K, f, o2, propose(f, "formality", CASUAL))
    return "audit completed the interrupted commit; next crossing attested"


def T55_commit_recovers_before_organism_install(K, d):
    s, o = born(K, d)
    apply_ok(K, s, o, propose(s, "verbosity"), attest=False)
    real = s.install_checkpoint

    def crash_before(cp, sig):
        raise OSError("interrupted before the organism installed")
    s.install_checkpoint = crash_before
    try:
        o.attest(s)
    except OSError:
        pass
    else:
        raise Fail("injected interruption did not happen")
    s.install_checkpoint = real
    attest_ok(K, o, s)
    f = expect_loads(K, s.data_dir)
    audit_ok(K, o, f)
    return "retry abandoned the stale intent and attested"


LOCK_PROBE = ("import fcntl, os, sys\n"
              "fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600)\n"
              "try:\n"
              "    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
              "    print('free')\n"
              "except BlockingIOError:\n"
              "    print('locked')\n")


def T56_owner_lock_excludes_other_processes(K, d):
    s, o = born(K, d)
    apply_ok(K, s, o, propose(s, "verbosity"), attest=False)

    def probe():
        return subprocess.run([sys.executable, "-I", "-c", LOCK_PROBE, str(o.lock_path)],
                              capture_output=True, text=True, timeout=30).stdout.strip()
    seen = []

    def clock():
        seen.append(probe())
        return time.time()
    o.clock = clock
    attest_ok(K, o, s)
    o.clock = time.time
    need(seen and all(x == "locked" for x in seen), f"another process could take the owner lock during attest: {seen}")
    after = probe()
    need(after == "free", f"lock still held after attest: {after!r}")
    return f"held during attest ({len(seen)} probe(s)); free after"


TESTS = TESTS + [T49_stale_session_cannot_bypass_owner_no, T50_stale_session_keeps_other_sessions_records,
                 T51_stale_witness_cannot_fork, T52_record_metadata_validated,
                 T53_lifetime_runs_from_first_signing, T54_commit_recovers_after_organism_install,
                 T55_commit_recovers_before_organism_install, T56_owner_lock_excludes_other_processes]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def build_mutant(name, edits, where: Path):
    src = CANDIDATE.read_text(encoding="utf-8")
    for old, new in edits:
        n = src.count(old)
        if n != 1:
            raise SystemExit(f"mutant {name}: anchor occurs {n} times (must be exactly 1)")
        src = src.replace(old, new)
    path = where / f"{name}.py"
    path.write_text(src, encoding="utf-8")
    return load_module(path, f"mut_{name}")


def run_suite(K):
    out = {}
    for t in TESTS:
        d = Path(tempfile.mkdtemp(prefix="hs084_"))
        try:
            detail = t(K, d)
            out[t.__name__] = {"status": "PASS", "detail": str(detail)}
        except Fail as f:
            out[t.__name__] = {"status": "FAIL", "detail": str(f)}
        except Exception as e:  # a crash: never a kill
            out[t.__name__] = {"status": "ERROR",
                               "detail": f"{type(e).__name__}: {e}",
                               "where": traceback.format_exc(limit=3).splitlines()[-3:]}
        finally:
            shutil.rmtree(d, ignore_errors=True)
    return out


def main():
    want = DECL_SHA.read_text().split()[0]
    if _sha(DECL) != want:
        raise SystemExit("DECLARED_v0_8_4.json differs from its frozen hash; refusing to run")
    declared = json.loads(DECL.read_text(encoding="utf-8"))
    if _sha(CANDIDATE) != declared["candidate_sha256_at_freeze"]:
        raise SystemExit("candidate differs from the one the declaration was frozen against; refusing to run")
    names = [t.__name__ for t in TESTS]
    if names != list(declared["tests"]):
        raise SystemExit("harness tests differ from the declared tests; refusing to run")

    print("=" * 78)
    print("Humble Seed v0.8.4 CANDIDATE — falsification harness")
    print(f"declared {want[:16]}… frozen {DECL_AT.read_text().strip()}")
    print(f"candidate {_sha(CANDIDATE)[:16]}…  parent v0.7 {_sha(PARENT_V07)[:16]}…")
    print("=" * 78)

    K = load_module(CANDIDATE, "hs084_candidate")
    base = run_suite(K)

    mismatches = 0
    print(f"\n{'TEST':48s} {'DECLARED':9s} {'MEASURED':9s} VERDICT")
    for name, spec in declared["tests"].items():
        got = base.get(name, {"status": "MISSING"})["status"]
        ok = (got == spec["expect"])
        mismatches += (not ok)
        print(f"{name:48s} {spec['expect']:9s} {got:9s} {'MATCH' if ok else 'MISMATCH'}")
        if got != "PASS":
            print(f"    -> {base.get(name, {}).get('detail', '')}")

    passing = {n for n, r in base.items() if r["status"] == "PASS"}
    mut_results = {}
    tmp = Path(tempfile.mkdtemp(prefix="hs084_mutants_"))
    try:
        print(f"\n{'MUTANT':44s} {'DECLARED':9s} {'MEASURED':9s} VERDICT   killed by (crashed)")
        for name, spec in declared["mutants"].items():
            M = build_mutant(name, [tuple(e) for e in spec["edits"]], tmp)
            res = run_suite(M)
            new_fail = sorted(n for n in passing if res[n]["status"] == "FAIL")
            new_err = sorted(n for n in passing if res[n]["status"] == "ERROR")
            status = "KILLED" if new_fail else ("CRASHED" if new_err else "SURVIVES")
            ok = (status == spec["expect"]) and (
                spec["expect"] != "KILLED" or spec["killer"] in new_fail)
            if "exact_kill_set" in spec:
                ok = ok and (sorted(spec["exact_kill_set"]) == new_fail)
            mismatches += (not ok)
            mut_results[name] = {
                "status": status, "new_failures": new_fail, "new_errors": new_err,
                "failure_details": {n: res[n]["detail"] for n in new_fail},
                "error_details": {n: res[n]["detail"] for n in new_err},
            }
            short = ", ".join(x.split("_")[0] for x in new_fail) or "-"
            if new_err:
                short += f"  ({len(new_err)} crashed)"
            print(f"{name:44s} {spec['expect']:9s} {status:9s} {'MATCH' if ok else 'MISMATCH':9s} {short}")
            if not ok and "exact_kill_set" in spec:
                print(f"    declared exact {sorted(spec['exact_kill_set'])}")
                print(f"    measured       {new_fail}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    normalized = {"tests": {n: r["status"] for n, r in base.items()},
                  "mutants": {n: {"status": r["status"], "new_failures": r["new_failures"],
                                  "new_errors": r["new_errors"]}
                              for n, r in mut_results.items()}}
    receipt = hashlib.sha256(_cj(normalized).encode()).hexdigest()
    results = {"declared_sha256": want, "candidate_sha256": _sha(CANDIDATE),
               "parent_v07_sha256": _sha(PARENT_V07), "tests": base, "mutants": mut_results,
               "mismatches": mismatches, "receipt": receipt}
    (HERE / "RESULTS_v0_8_4.json").write_text(json.dumps(results, indent=2, sort_keys=True))

    print("\n" + "=" * 78)
    print(f"mismatches vs declared: {mismatches}")
    print(f"receipt (statuses only, run-independent): {receipt}")
    print("RESULTS_v0_8_4.json written. Exit code is non-zero if any mismatch.")
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
