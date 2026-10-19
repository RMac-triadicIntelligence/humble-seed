#!/usr/bin/env python3
"""DIAGNOSTIC, NOT SCORED (v0.8.5 DEVIATIONS E1). T57 as frozen expected the audit's
IntegrityError to say 'Unattested authorizing event'; the candidate refuses earlier with
'Category sequences do not match the attested checkpoint'. This runs T57 with only that
message expectation changed (any IntegrityError naming 'the attested checkpoint'), on the
candidate and on the three mutants whose declared kill sets included T57."""
import importlib.util, json, shutil, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("falsify_v0_8_5", HERE / "falsify_v0_8_5.py")
H = importlib.util.module_from_spec(spec); sys.modules["falsify_v0_8_5"] = H; spec.loader.exec_module(H)

def T57_corrected(K, d):
    s, o = H.born(K, d)
    H.apply_ok(K, s, o, H.propose(s, "verbosity"), attest=False)
    real = s._save
    def failing_save():
        raise OSError("injected: the checkpoint save failed before writing")
    s._save = failing_save
    try:
        o.attest(s)
    except OSError:
        pass
    else:
        raise H.Fail("injected save failure did not happen")
    finally:
        s._save = real
    H.need(s.checkpoint.sequence == 0 and H.saved_seq(s) == 0,
           f"after the failed save: object at {s.checkpoint.sequence}, saved state at {H.saved_seq(s)}")
    try:
        o.audit(s); got = "audit returned"
    except (K.IntegrityError, K.RollbackDetected) as e:
        got = f"{type(e).__name__}: {e}"
    H.need(got.startswith("IntegrityError") and "the attested checkpoint" in got, f"audit after the failed save: {got}")
    w = K.OwnerWitness(d / "witness.json")
    H.need(w.ledger[s.organism_id]["sequence"] == 0 and w.pending_for(s.organism_id) is None,
           "the witness advanced past the saved state, or kept the intent")
    H.attest_ok(K, o, s)
    f = H.expect_loads(K, s.data_dir)
    H.audit_ok(K, H.reopen(K, o, d), f)
    H.need(H.fresh_witness_seq(K, d, f) == 1, "witness not at 1 after the retry")
    return f"PASS ({got})"

def run(K):
    d = Path(tempfile.mkdtemp(prefix="hs085_diag_"))
    try:
        return T57_corrected(K, d)
    except H.Fail as e:
        return f"FAIL: {e}"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
    finally:
        shutil.rmtree(d, ignore_errors=True)

dec = json.loads((HERE / "DECLARED_v0_8_5.json").read_text())
K = H.load_module(H.CANDIDATE, "diag_candidate")
out = {"candidate": run(K)}
tmp = Path(tempfile.mkdtemp(prefix="hs085_diag_mut_"))
for name in ("XR4_install_keeps_memory_on_failed_save", "XR2_recovery_never_abandons",
             "X10_unattested_tail_check_removed", "XR5_recovery_trusts_the_object"):
    M = H.build_mutant(name, [tuple(e) for e in dec["mutants"][name]["edits"]], tmp)
    out[name] = run(M)
shutil.rmtree(tmp, ignore_errors=True)
for k, v in out.items():
    print(f"{k:42s} {v}")
