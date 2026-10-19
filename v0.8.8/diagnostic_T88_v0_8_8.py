#!/usr/bin/env python3
"""Diagnostic for DEVIATIONS_v0_8_8 E1 (not scored; run after the scored run).

T88 as frozen loads `b` through the symlink BEFORE the verbosity reading is issued. Issuing the
reading saves, so `b` is stale when the reader runs; b's dwell raises StaleOrganism inside the
reader, the organism holds (a reader that fails holds, D1), and apply returns None. That is the
candidate behaving as designed; the test's setup was wrong.

This script runs T88_corrected, which differs only in loading `b` after the reading is issued and
signed (as T76 does), on the candidate and on every declared mutant, and prints which mutants it
kills. The scored result is not changed by this script.

Run from hs088/:  python3 -I diagnostic_T88_v0_8_8.py
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import falsify_v0_8_8 as H  # noqa: E402


def T88_corrected(K, d):
    s, o = H.born(K, d)
    link = d / "org_link"
    os.symlink(s.data_dir, link)
    r = H.propose(s, "verbosity")
    sig = o.sign_proposal(r["payload_to_sign"])
    b = H.expect_loads(K, link)                 # the only change: loaded after the issue, so b is current
    calls = []

    def reader(reading, terrain, events_since):
        if not calls:
            calls.append(b.dwell_or_propose("formality", "evt", "hmm ok")["status"])
        return None
    s.reader = reader
    a = H._start(lambda: s.authorize_and_apply(r["proposal_id"], sig), "T88c-A")
    H.need(a["done"].wait(5), "the apply did not finish within 5 s (deadlock)")
    why = H.judge_outcome(K, a, K.StaleOrganism, "stale organism object")
    H.need(calls == ["dwelling"], f"the reader's write did not happen as set up: {calls}")
    st = H.saved_state(s)
    ds = [e.get("category") for e in st["trace"] if e.get("event") == "dwelling"]
    H.need("formality" in ds and st["mutation_sequence"] == 0,
           f"saved dwellings {ds}, mutation_sequence {st['mutation_sequence']}")
    H.audit_ok(K, o, H.expect_loads(K, s.data_dir))
    return why


def T88_as_frozen_detail(K, d):
    """What the frozen T88 met on the candidate: the reader's own exception."""
    s, o = H.born(K, d)
    link = d / "org_link"
    os.symlink(s.data_dir, link)
    b = H.expect_loads(K, link)
    r = H.propose(s, "verbosity")
    sig = o.sign_proposal(r["payload_to_sign"])
    seen = []

    def reader(reading, terrain, events_since):
        try:
            b.dwell_or_propose("formality", "evt", "hmm ok")
            seen.append("returned")
        except BaseException as e:
            seen.append(f"{type(e).__name__}: {e}")
            raise
        return None
    s.reader = reader
    out = s.authorize_and_apply(r["proposal_id"], sig)
    return {"apply_returned": out, "reader": seen, "last_event": s.trace[-1].get("event"),
            "reason": s.trace[-1].get("reason")}


def run(test, K):
    d = Path(tempfile.mkdtemp(prefix="hs088_diag_"))
    try:
        return {"status": "PASS", "detail": str(test(K, d))}
    except H.Fail as f:
        return {"status": "FAIL", "detail": str(f)}
    except Exception as e:
        return {"status": "ERROR", "detail": f"{type(e).__name__}: {e}"}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    declared = json.loads(H.DECL.read_text(encoding="utf-8"))
    K = H.load_module(H.CANDIDATE, "diag_candidate")
    d = Path(tempfile.mkdtemp(prefix="hs088_diag_"))
    try:
        print("Frozen T88 on the candidate, with the reader's exception shown:")
        print("  ", T88_as_frozen_detail(K, d))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    base = run(T88_corrected, K)
    print(f"\nT88_corrected on the candidate: {base['status']}  ({base['detail']})")
    if base["status"] != "PASS":
        return
    tmp = Path(tempfile.mkdtemp(prefix="hs088_diag_mutants_"))
    killed = []
    try:
        for name, spec in declared["mutants"].items():
            M = H.build_mutant(name, [tuple(e) for e in spec["edits"]], tmp)
            res = run(T88_corrected, M)
            if res["status"] != "PASS":
                print(f"  {name:44s} {res['status']:5s} {res['detail'][:110]}")
            if res["status"] == "FAIL":
                killed.append(name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nT88_corrected fails on {len(killed)} mutants: {killed}")
    print("Declared mutants naming T88 in their exact kill set:",
          sorted(n for n, m in declared["mutants"].items() if "T88_a_symlinked_path_shares_the_organism_lock"
                 in m.get("exact_kill_set", [])))


if __name__ == "__main__":
    main()
