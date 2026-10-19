#!/usr/bin/env python3
"""P6 re-run (not scored). The first run of author_probe_v0_8_8.py errored in P6 on a probe bug: it loaded a
second object after an unattested crossing, and an unattested state does not load, by design (T17). This
version attests first; nothing else changes. The first run's output is kept unchanged in AUTHOR_PROBE_v0_8_8.txt.
Run from hs088/: python3 -I author_probe_v0_8_8_P6_rerun.py"""
import json, sys, tempfile, importlib.util
from pathlib import Path
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ap", HERE / "author_probe_v0_8_8.py"); AP = importlib.util.module_from_spec(spec)
sys.modules["ap"] = AP; spec.loader.exec_module(AP)
K, H, outcome = AP.K, AP.H, AP.outcome


def P6_thread_state_after_refusals(d):
    """As in author_probe_v0_8_8.py, with an attest after the apply so that a second object can load."""
    s, o = H.born(K, d)
    a = outcome(lambda: s.dwell_or_propose("no_such_category", "evt", "hmm ok"))
    def reader(reading, terrain, events):
        reader.got = outcome(lambda: o.sign_proposal(reading["payload_to_sign"]))
        return None
    r = H.propose(s, "verbosity"); sig = o.sign_proposal(r["payload_to_sign"])
    s.reader = reader
    applied = outcome(lambda: s.authorize_and_apply(r["proposal_id"], sig) is not None)
    s.reader = K.contradiction_only_reader
    first_attest = outcome(lambda: o.attest(s))                    # the fix: attest, so the state loads
    other = H.expect_loads(K, s.data_dir)
    real = K._durable_write; fired = []
    def write(path, text):
        if Path(path) == s._state_path() and not fired:
            fired.append(outcome(lambda: other.dwell_or_propose("curiosity", "evt", "hmm ok")))
        return real(path, text)
    K._durable_write = write
    try:
        outer = outcome(lambda: s.dwell_or_propose("formality", "evt", "hmm ok")["status"])
    finally:
        K._durable_write = real
    after = {"organism_held": getattr(K._THREAD, "organism_held", None), "saving": sorted(getattr(K._THREAD, "saving", set()))}
    z = H.propose(s, "curiosity", "I always prefer you ask fewer questions")
    ans = outcome(lambda: o.answer(s, z["proposal_id"], "unsure")["status"])
    att = outcome(lambda: o.attest(s))
    return {"unknown_category": a, "reader_owner_call": getattr(reader, "got", None), "apply_with_that_reader": applied,
            "first_attest": first_attest, "nested_save": fired, "outer_dwell": outer, "thread_state_after": after,
            "answer": ans, "attest": att, "fresh_audit": outcome(lambda: o.audit(H.expect_loads(K, s.data_dir)))}


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="hs088_ap6_") as t:
        dd = Path(t) / "case"; dd.mkdir()
        print(json.dumps({"P6_thread_state_after_refusals": P6_thread_state_after_refusals(dd)}, indent=2, sort_keys=True))
