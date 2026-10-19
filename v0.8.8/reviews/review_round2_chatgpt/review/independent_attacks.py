#!/usr/bin/env python3
"""Blind, executable additions to the supplied v0.8.1 tests. No network.

Usage: python3 -I independent_attacks.py PATH_TO_UNPACKED_BLIND_DIRECTORY
Every ATTACK_REPRODUCED result asserts a counterexample, not product safety.
Temporary organisms and freshly generated private keys are deleted on exit.
"""
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile


ROOT = Path(sys.argv[1]).resolve()
CANDIDATE = ROOT / "humble_seed_v0_8_1_candidate.py"


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


K = module(CANDIDATE, "independent_candidate")


def born(d):
    s = K.HumbleSeed(d / "org")
    _, pem, cp = s.hatch()
    o = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json"))
    assert o.attest(s, cp)
    return s, o


def proposal(s, category="verbosity"):
    r = s.dwell_or_propose(category, "evt", "I always prefer shorter answers")
    assert r["status"] == "proposal"
    return r


def reload_audit(s, o):
    f = K.HumbleSeed(s.data_dir)
    f.load()
    assert o.audit(f)
    return f


def finite_distribution_boundary(d):
    """New test absent from DECLARED: non-finite weights must not cross."""
    s, o = born(d)
    dist = {"preference": float("nan"), "confound": 0.5,
            "unmodeled_cause": 0.5}
    validated = s._validate_distribution(dist)
    assert math.isnan(validated["preference"])
    p = s._issue_pending_proposal("verbosity", dist, ["non-finite reading"])
    signed = json.loads(p.payload_to_sign)
    cp = s.authorize_and_apply(p.proposal_id, o.sign_proposal(p.payload_to_sign))
    assert cp is not None and o.attest(s, cp)
    f = reload_audit(s, o)
    assert f.character["verbosity"] == 0.25
    return {"validator_accepted_nan": True, "lead_weight_is_finite": False,
            "applied": True, "destination": f.character["verbosity"],
            "fresh_load_and_owner_audit": True,
            "signed_distribution_root_unchanged": signed["distribution_root"] == p.distribution_root}


def unsigned_clamp_rule(d):
    s, o = born(d)
    r = proposal(s)
    p = s.pending[r["proposal_id"]]
    sig = o.sign_proposal(r["payload_to_sign"])
    initial_constitution = copy.deepcopy(s.constitution)
    initial_checkpoint_root = s.checkpoint.constitution_root
    baseline = s.derive(p.category, p.distribution, p.prior_value)[2]
    saved = K.VALUE_MIN
    try:
        K.VALUE_MIN = 0.4  # only runtime constant changes; constitution and reading untouched
        new_destination = s.derive(p.category, p.distribution, p.prior_value)[2]
        cp = s.authorize_and_apply(r["proposal_id"], sig)
        assert cp is not None and o.attest(s, cp)
    finally:
        K.VALUE_MIN = saved
    assert s.constitution == initial_constitution
    assert s.checkpoint.constitution_root == initial_checkpoint_root
    f = reload_audit(s, o)  # original clamp restored before reload/audit
    assert baseline == 0.25 and new_destination == f.character["verbosity"] == 0.4
    return {"original_destination": baseline, "actual_destination": new_destination,
            "constitution_value_range": f.constitution["value_range"],
            "constitution_and_signed_reading_unchanged": True,
            "original_reading_signature_accepted": True,
            "fresh_load_and_audit_with_original_constants": True}


def cross_category_tamper_laundered(d):
    s, o = born(d)
    r = proposal(s)
    sig = o.sign_proposal(r["payload_to_sign"])
    s.character["formality"] = 0.99  # no formality reading/signature
    cp = s.authorize_and_apply(r["proposal_id"], sig)
    assert cp is not None and o.attest(s, cp)
    f = reload_audit(s, o)
    authorized = [e["record"]["category"] for e in f.trace
                  if e["event"] == "authorized_mutation"]
    assert f.character["formality"] == 0.99 and f.category_sequence["formality"] == 0
    assert authorized == ["verbosity"]
    return {"unsigned_formality": f.character["formality"],
            "formality_category_sequence": f.category_sequence["formality"],
            "authorized_mutation_categories": authorized,
            "owner_attested_checkpoint": True, "fresh_load_and_owner_audit": True}


def destination_alias_survives_suite(d):
    H = module(ROOT / "falsify_v0_8_1.py", "independent_supplied_harness")
    anchor = '            "kind": "reading_authorization",\n'
    src = CANDIDATE.read_text()
    assert src.count(anchor) == 1
    alias_src = src.replace(anchor, anchor +
        '            "landing_value": self.derive(p.category, p.distribution, p.prior_value)[2],\n')
    mutant_path = d / "destination_alias_mutant.py"
    mutant_path.write_text(alias_src)
    M = module(mutant_path, "independent_destination_alias")
    results = H.run_suite(M)
    failed = {n: v for n, v in results.items() if v["status"] != "PASS"}
    assert not failed, failed
    # Also show the exact destination is present and signed in this mutant.
    m, owner = H.born(M, d / "alias_case")
    r = H.propose(m, "verbosity")
    payload = json.loads(r["payload_to_sign"])
    assert payload["landing_value"] == r["preview_destination"]["verbosity"] == 0.25
    H.apply_ok(m, owner, r)
    return {"signed_landing_value": payload["landing_value"],
            "T5": results["T5_payload_names_no_destination"]["status"],
            "suite_tests_passed": len(results), "new_failures": [],
            "mutant_verdict_using_supplied_rule": "SURVIVES"}


def error_counted_as_kill(d):
    H = module(ROOT / "falsify_v0_8_1.py", "independent_error_harness")
    # Add an unrelated failure before the rule is read, retaining the control itself.
    src = CANDIDATE.read_text()
    anchor = '        return self.constitution["derivation"]\n'
    assert src.count(anchor) == 1
    path = d / "crash_mutant.py"
    path.write_text(src.replace(anchor, '        raise RuntimeError("unrelated injected crash")\n' + anchor))
    M = module(path, "independent_crash_mutant")
    base = H.run_suite(K)
    results = H.run_suite(M)
    # Verbatim predicate from the supplied harness's new_fail computation.
    passing = {n for n, r in base.items() if r["status"] == "PASS"}
    new_fail = sorted(n for n in passing if results[n]["status"] != "PASS")
    kinds = {kind: sum(results[n]["status"] == kind for n in new_fail)
             for kind in ["FAIL", "ERROR"]}
    assert kinds["ERROR"] > 0 and kinds["FAIL"] == 0
    return {"actual_failure_kinds": kinds,
            "T6_status": results["T6_rule_comes_from_constitution"]["status"],
            "T6_detail": results["T6_rule_comes_from_constitution"]["detail"],
            "supplied_kill_predicate": 'res[n]["status"] != "PASS"',
            "mutant_verdict_using_supplied_rule": "KILLED" if new_fail else "SURVIVES"}


def normal_checkpoint_interleaving(d):
    s, o = born(d)
    r = proposal(s)
    cp = s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
    assert cp is not None
    assert s.dwell_or_propose("formality", "evt", "hmm ok")["status"] == "dwelling"
    accepted = o.attest(s, cp)
    assert not accepted
    f = K.HumbleSeed(s.data_dir)
    try:
        f.load()
    except K.IntegrityError as e:
        load_error = str(e)
    else:
        raise AssertionError("expected fail-closed load")
    recovered = o.attest(s, s.checkpoint_request())
    assert recovered and reload_audit(s, o)
    return {"ordinary_dwell_after_apply": True, "original_checkpoint_accepted": accepted,
            "load_before_recovery": load_error,
            "fresh_checkpoint_recovery": recovered,
            "classification": "checkpoint interleaving observation; related to disclosed R6, not a new reading-staleness finding"}


def result_commitment_observation(d):
    s, o = born(d)
    r = proposal(s)
    p = s.pending[r["proposal_id"]]
    derived = s.derive(p.category, p.distribution, p.prior_value)[2]
    cp = s.authorize_and_apply(r["proposal_id"], o.sign_proposal(r["payload_to_sign"]))
    expected_character = {"verbosity": derived, "formality": 0.5, "curiosity": 0.6}
    assert cp.character_root == K._sha256(K._canonical_json(expected_character))
    altered = copy.deepcopy(cp)
    altered.character_root = K._sha256(K._canonical_json({**expected_character, "verbosity": 0.3}))
    assert K.HumbleSeed.checkpoint_payload(altered) != K.HumbleSeed.checkpoint_payload(cp)
    assert o.attest(s, cp)
    return {"destination_derivable_from_bound_inputs_and_rule": derived,
            "second_signature_binds_exact_result_character_root": True,
            "classification": "design characterization, not a new security break or a preview leak into the original reading"}


TESTS = [finite_distribution_boundary, unsigned_clamp_rule,
         cross_category_tamper_laundered, destination_alias_survives_suite,
         error_counted_as_kill, normal_checkpoint_interleaving,
         result_commitment_observation]


def main():
    results = {}
    for test in TESTS:
        with tempfile.TemporaryDirectory(prefix="hs081_independent_") as tmp:
            try:
                detail = test(Path(tmp))
                status = "ATTACK_REPRODUCED" if test in TESTS[:5] else "OBSERVED"
            except Exception:
                import traceback
                results[test.__name__] = {"status": "REPRO_ERROR", "detail": traceback.format_exc()}
            else:
                results[test.__name__] = {"status": status, "detail": detail}
        print(test.__name__ + " " + json.dumps(results[test.__name__], sort_keys=True))
    (Path(__file__).parent / "independent_results.json").write_text(
        json.dumps(results, sort_keys=True, indent=2) + "\n")
    return 1 if any(r["status"] == "REPRO_ERROR" for r in results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
