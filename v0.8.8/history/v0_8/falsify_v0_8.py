#!/usr/bin/env python3
"""
Falsification harness for humble_seed_v0_8_candidate.py

Written AFTER DECLARED.json was frozen (see DECLARED.sha256 / DECLARED.frozen_at).

Discipline (the two recurring bugs this harness exists to avoid):
  #1  No verdict is printed that is not computed. Every row compares MEASURED
      to the frozen DECLARED.json; the exit code is non-zero on any mismatch.
  #5  Every new control ships with a mutant that removes it. A mutant is
      KILLED when at least one test that PASSES on the candidate FAILS on the
      mutant (the standard mutation-testing definition). One mutant (X4) is
      declared in advance to SURVIVE, and X0 (an identical copy) must survive.

A rejection counts only through its declared mechanism. Any other exception is
an ERROR, never a rejection (the lineage harness's "bare Exception counted as a
rejection" blocker does not recur here).

Run:  python3 -I falsify_v0_8.py
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATE = HERE / "humble_seed_v0_8_candidate.py"
PARENT = HERE / "parent_humble_seed_v0_7_C5.py"
DECL = HERE / "DECLARED.json"


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
# Helpers — each rejection is recognised only through its declared mechanism
# ---------------------------------------------------------------------------

PREF = "I always prefer shorter answers"


def born(K, d: Path):
    s = K.HumbleSeed(d / "org")
    oid, pem, g = s.hatch()
    o = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json"))
    need(o.attest(s, g) is True, "genesis attestation failed")
    return s, o


def propose(s, cat, text=PREF):
    r = s.dwell_or_propose(cat, "evt", text)
    need(r["status"] == "proposal", f"expected a proposal, got {r['status']}")
    return r


def dwell(s, cat, text):
    r = s.dwell_or_propose(cat, "evt", text)
    need(r["status"] == "dwelling", f"expected dwelling, got {r['status']}")


def apply_ok(s, o, r, attest=True):
    cp = s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
    need(cp is not None, f"expected apply, rejected: {s.trace[-1].get('reason')!r}")
    if attest:
        need(o.attest(s, cp) is True, "attestation after apply failed")
    return cp


def expect_reject(s, pid, sig, sub):
    out = s.authorize_and_apply(pid, sig)
    need(out is None, "expected rejection, but the reading was APPLIED")
    last = s.trace[-1]
    need(last.get("event") == "authorization_rejected",
         f"no rejection event (last event {last.get('event')!r})")
    need(sub in last.get("reason", ""), f"rejected for a different reason: {last.get('reason')!r}")
    return last["reason"]


def expect_integrity(K, data_dir: Path, sub):
    f = K.HumbleSeed(data_dir)
    try:
        f.load()
    except K.IntegrityError as e:
        need(sub in str(e), f"IntegrityError for a different reason: {str(e)!r}")
        return str(e)
    raise Fail("load ACCEPTED")


def expect_rollback(K, fn, sub):
    try:
        fn()
    except K.RollbackDetected as e:
        need(sub in str(e), f"RollbackDetected for a different reason: {str(e)!r}")
        return str(e)
    raise Fail("audit ACCEPTED")


def near(a, b):
    return abs(float(a) - float(b)) < 1e-12


# ---------------------------------------------------------------------------
# Tests (T1–T20, exactly as declared)
# ---------------------------------------------------------------------------

def T1_liveness_intervening_events(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    for cat, txt in [("formality", "hmm ok"), ("verbosity", "ok"),
                     ("curiosity", "sorry, someone's at the door"),
                     ("verbosity", "thanks"), ("formality", "sure")]:
        dwell(s, cat, txt)
    need(s.authorize_and_apply("no-such-proposal", "AAAA") is None, "unknown id applied")
    need(o.attest(s, s.checkpoint_request()) is True, "mid-session attestation failed")
    apply_ok(s, o, r)
    need(near(s.character["verbosity"], 0.25), f"verbosity {s.character['verbosity']}")
    return "applied after 5 dwellings, 1 rejection event, 1 checkpoint; verbosity 0.25"


def T2_liveness_cross_category(K, d):
    s, o = born(K, d)
    rv = propose(s, "verbosity")
    rf = propose(s, "formality", "I prefer a casual tone always")
    sig_v = o.sign_proposal(rv["payload_to_sign"])
    apply_ok(s, o, rf)
    cp = s.authorize_and_apply(rv["proposal_id"], sig_v)
    need(cp is not None, f"verbosity reading rejected after formality commit: {s.trace[-1].get('reason')!r}")
    need(o.attest(s, cp) is True, "attestation failed")
    need(near(s.character["verbosity"], 0.25) and near(s.character["formality"], 0.25),
         f"character {s.character}")
    return "verbosity reading applied after a formality commit; both 0.25"


def T3_stale_same_category(K, d):
    s, o = born(K, d)
    a = propose(s, "verbosity")
    b = propose(s, "verbosity")
    sig_a = o.sign_proposal(a["payload_to_sign"])
    apply_ok(s, o, b)
    why = expect_reject(s, a["proposal_id"], sig_a, "category has advanced")
    need(near(s.character["verbosity"], 0.25), f"verbosity {s.character['verbosity']}")
    return why


def T4_second_crossing_at_clamp_floor(K, d):
    s, o = born(K, d)
    apply_ok(s, o, propose(s, "verbosity"))
    apply_ok(s, o, propose(s, "verbosity"))
    need(near(s.character["verbosity"], 0.0), f"verbosity {s.character['verbosity']}, expected floor")
    c = propose(s, "verbosity")
    e = propose(s, "verbosity")
    sig_c = o.sign_proposal(c["payload_to_sign"])
    apply_ok(s, o, e)
    need(near(s.character["verbosity"], 0.0) and s.category_sequence["verbosity"] == 3,
         f"after floor crossing: {s.character['verbosity']}, seq {s.category_sequence['verbosity']}")
    return expect_reject(s, c["proposal_id"], sig_c, "category has advanced")


def T5_payload_names_no_destination(K, d):
    s, o = born(K, d)
    r = propose(s, "verbosity")
    keys = set(json.loads(r["payload_to_sign"]))
    banned = keys & {"change", "change_hash", "destination", "preview_destination"}
    need(not banned, f"payload names a destination: {sorted(banned)}")
    missing = {"evidence_root", "distribution_root", "prior_value", "category_sequence",
               "constitution_root"} - keys
    need(not missing, f"payload lacks reading fields: {sorted(missing)}")
    return f"{len(keys)} signed fields; no destination field"


def T6_rule_comes_from_constitution(K, d):
    saved = copy.deepcopy(K.GENESIS_DERIVATION)
    try:
        s, o = born(K, d)
        K.GENESIS_DERIVATION["label_to_delta"]["preference"] = -0.5
        apply_ok(s, o, propose(s, "verbosity"))
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
    cp = s.authorize_and_apply(r["proposal_id"], sig)
    need(cp is not None and o.attest(s, cp), "first apply failed")
    s.pending[r["proposal_id"]] = saved
    return expect_reject(s, r["proposal_id"], sig, "replay")


def T11_expiry(K, d):
    s, o = born(K, d)
    p = s._issue_pending_proposal("curiosity", {"preference": 0.68, "confound": 0.12,
                                                "unmodeled_cause": 0.20}, ["e"], ttl=-1.0)
    return expect_reject(s, p.proposal_id, o.sign_proposal(p.payload_to_sign), "expired")


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
    apply_ok(s, o, propose(s, "verbosity"))
    out = K._reseal_attack(s, lambda st: st["character"].__setitem__("verbosity", 0.99),
                           rechain=True)
    need(out.startswith("rejected:") and "Character does not match" in out, out)
    return out


def T15_category_sequences_resealed(K, d):
    s, o = born(K, d)
    apply_ok(s, o, propose(s, "verbosity"))

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
    cp = s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
    need(cp is not None, "apply failed")
    return expect_integrity(K, s.data_dir, "Unattested authorizing event")


def T18_rollback_witness_only(K, d):
    s, o = born(K, d)
    apply_ok(s, o, propose(s, "verbosity"))
    snap = s._state_path().read_text()
    apply_ok(s, o, propose(s, "formality", "I prefer a casual tone always"))
    s._state_path().write_text(snap)
    rolled = K.HumbleSeed(s.data_dir)
    rolled.load()                        # must load: the organism cannot see its rollback
    return expect_rollback(K, lambda: o.audit(rolled), "Rollback")


def T19_identity_replacement_audit(K, d):
    s, o = born(K, d)
    evil, _ = born(K, d / "evil")
    shutil.copy(evil._state_path(), s._state_path())
    replaced = K.HumbleSeed(s.data_dir)
    replaced.load()
    need(replaced.organism_id != s.organism_id, "replacement did not take")
    return expect_rollback(K, lambda: o.audit(replaced), "Unknown organism")


SESSION = [
    ("verbosity", PREF),
    ("formality", "hmm ok"),
    ("formality", "I prefer a casual tone always"),
    ("curiosity", "sorry, someone's at the door"),
    ("verbosity", "ok"),
    ("curiosity", "I always prefer you ask fewer questions"),
    ("formality", "thanks"),
    ("verbosity", PREF),
]


def run_session(M, d):
    s = M.HumbleSeed(d / "org")
    oid, pem, g = s.hatch()
    o = M.OwnerTool(pem, M.OwnerWitness(d / "witness.json"))
    need(o.attest(s, g), "genesis attestation failed")
    readings = []
    for cat, txt in SESSION:
        r = s.dwell_or_propose(cat, "evt", txt)
        if r["status"] == "proposal":
            readings.append(r)
    applied, reasons = 0, []
    for r in readings:                       # owner signs at session end, in issue order
        cp = s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
        if cp is not None:
            applied += 1
            need(o.attest(s, cp), "attestation failed")
        else:
            reasons.append(s.trace[-1].get("reason", ""))
    return len(readings), applied, reasons, dict(s.character)


def T20_realistic_session(K, d):
    n, applied, reasons, ch = run_session(K, d / "v08")
    need(n == 4, f"{n} readings issued, expected 4")
    need(applied == 3, f"v0.8 applied {applied} of 4, expected 3; reasons {reasons}")
    need(len(reasons) == 1 and "category has advanced" in reasons[0], f"rejections {reasons}")
    need(near(ch["verbosity"], 0.25) and near(ch["formality"], 0.25) and near(ch["curiosity"], 0.35),
         f"final character {ch}")
    P = load_module(PARENT, "parent_v07_session")
    pn, papplied, preasons, _ = run_session(P, d / "v07")
    need(pn == 4 and papplied == 0, f"parent v0.7 applied {papplied} of {pn}, expected 0 of 4")
    return (f"v0.8 applied {applied}/{n} (rejected: {reasons[0]!r}); "
            f"parent v0.7 applied {papplied}/{pn} (first reason: {preasons[0]!r})")


TESTS = [T1_liveness_intervening_events, T2_liveness_cross_category, T3_stale_same_category,
         T4_second_crossing_at_clamp_floor, T5_payload_names_no_destination,
         T6_rule_comes_from_constitution, T7_constitution_pinned_at_apply,
         T8_distribution_bound, T9_evidence_bound, T10_replay, T11_expiry, T12_wrong_key,
         T13_forged_first_commit, T14_forged_character_resealed,
         T15_category_sequences_resealed, T16_permissive_rule_full_birth_repair,
         T17_unattested_apply_fails_closed, T18_rollback_witness_only,
         T19_identity_replacement_audit, T20_realistic_session]


# ---------------------------------------------------------------------------
# Mutants (#5): each removes exactly one new control
# ---------------------------------------------------------------------------

K1_ANCHOR = ("        # [K1-ANCHOR] non-authorizing events and other categories' "
             "commits do not expire a reading.\n")

MUTANTS = {
    "X0_NULL_identical_copy": [],
    "X1_K1_trace_head_staleness_restored": [(K1_ANCHOR,
        "        if p.issued_trace_head != self._trace_head:\n"
        "            self._reject(proposal_id, \"stale proposal: trace has advanced since issuance\")\n"
        "            return None\n")],
    "X2_K1_global_sequence_staleness_restored": [(K1_ANCHOR,
        "        if p.issued_mutation_sequence != self.mutation_sequence:\n"
        "            self._reject(proposal_id, \"stale proposal: mutation sequence has advanced\")\n"
        "            return None\n")],
    "X3_K1_category_sequence_check_removed": [(
        "        if p.category_sequence != current_seq:\n", "        if False:\n")],
    "X4_K1_prior_value_check_removed": [(
        "        if float(p.prior_value) != float(self.character[p.category]):\n",
        "        if False:\n")],
    "X5_K2_destination_back_in_payload": [(
        '            "kind": "reading_authorization",\n',
        '            "kind": "reading_authorization",\n'
        '            "destination": self.derive(p.category, p.distribution, p.prior_value)[2],\n')],
    "X6_K2_rule_read_from_module_constant": [(
        '        return self.constitution["derivation"]\n',
        '        return GENESIS_DERIVATION\n')],
    "X7_K2_constitution_pin_removed": [(
        "        if p.constitution_root != self._constitution_root():\n", "        if False:\n")],
    "X8_K2_distribution_root_not_rehashed": [(
        '            "distribution_root": _sha256(_canonical_json(p.distribution)),\n',
        '            "distribution_root": p.distribution_root,\n')],
    "X9_C5_unknown_organism_audit_returns": [(
        '            raise RollbackDetected("Unknown organism: explicit sequence-zero enrollment is required")\n',
        '            return\n')],
}


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


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_suite(K):
    out = {}
    for t in TESTS:
        d = Path(tempfile.mkdtemp(prefix="hs08_"))
        try:
            detail = t(K, d)
            out[t.__name__] = {"status": "PASS", "detail": str(detail)}
        except Fail as f:
            out[t.__name__] = {"status": "FAIL", "detail": str(f)}
        except Exception as e:  # never counted as a rejection
            out[t.__name__] = {"status": "ERROR",
                               "detail": f"{type(e).__name__}: {e}",
                               "where": traceback.format_exc(limit=3).splitlines()[-3:]}
        finally:
            shutil.rmtree(d, ignore_errors=True)
    return out


def main():
    want = (HERE / "DECLARED.sha256").read_text().split()[0]
    if _sha(DECL) != want:
        raise SystemExit("DECLARED.json differs from its frozen hash; refusing to run")
    declared = json.loads(DECL.read_text())

    print("=" * 78)
    print("Humble Seed v0.8 CANDIDATE — falsification harness")
    print(f"declared {want[:16]}… frozen {(HERE / 'DECLARED.frozen_at').read_text().strip()}")
    print(f"candidate {_sha(CANDIDATE)[:16]}…  parent {_sha(PARENT)[:16]}…")
    print("=" * 78)

    K = load_module(CANDIDATE, "hs08_candidate")
    base = run_suite(K)

    mismatches = 0
    print(f"\n{'TEST':42s} {'DECLARED':9s} {'MEASURED':9s} VERDICT")
    for name, spec in declared["tests"].items():
        got = base.get(name, {"status": "MISSING"})["status"]
        ok = (got == spec["expect"])
        mismatches += (not ok)
        print(f"{name:42s} {spec['expect']:9s} {got:9s} {'MATCH' if ok else 'MISMATCH'}")
        if got != "PASS":
            print(f"    -> {base.get(name, {}).get('detail', '')}")

    passing = {n for n, r in base.items() if r["status"] == "PASS"}
    mut_results = {}
    tmp = Path(tempfile.mkdtemp(prefix="hs08_mutants_"))
    try:
        print(f"\n{'MUTANT':44s} {'DECLARED':9s} {'MEASURED':9s} VERDICT   killed by")
        for name, edits in MUTANTS.items():
            M = build_mutant(name, edits, tmp)
            res = run_suite(M)
            new_fail = sorted(n for n in passing if res[n]["status"] != "PASS")
            status = "KILLED" if new_fail else "SURVIVES"
            spec = declared["mutants"][name]
            ok = (status == spec["expect"]) and (
                spec["expect"] != "KILLED" or spec["killer"] in new_fail)
            mismatches += (not ok)
            mut_results[name] = {"status": status, "new_failures": new_fail,
                                 "killer_detail": (res[spec["killer"]]["detail"]
                                                   if spec.get("killer") in res else None)}
            short = ", ".join(x.split("_")[0] for x in new_fail) or "-"
            print(f"{name:44s} {spec['expect']:9s} {status:9s} {'MATCH' if ok else 'MISMATCH':9s} {short}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    normalized = {"tests": {n: r["status"] for n, r in base.items()},
                  "mutants": {n: {"status": r["status"], "new_failures": r["new_failures"]}
                              for n, r in mut_results.items()}}
    receipt = hashlib.sha256(_cj(normalized).encode()).hexdigest()
    results = {"declared_sha256": want, "candidate_sha256": _sha(CANDIDATE),
               "parent_sha256": _sha(PARENT), "tests": base, "mutants": mut_results,
               "mismatches": mismatches, "receipt": receipt}
    (HERE / "RESULTS.json").write_text(json.dumps(results, indent=2, sort_keys=True))

    print("\n" + "=" * 78)
    print(f"mismatches vs declared: {mismatches}")
    print(f"receipt (statuses only, run-independent): {receipt}")
    print("RESULTS.json written. Exit code is non-zero if any mismatch.")
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
