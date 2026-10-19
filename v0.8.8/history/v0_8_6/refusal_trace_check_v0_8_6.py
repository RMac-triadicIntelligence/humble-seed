#!/usr/bin/env python3
"""Not scored. Checks the declaration's refusal_trace against where each exception actually
originated in the candidate, for T57 and T62-T68. Run: python3 -I refusal_trace_check_v0_8_6.py"""
import importlib.util, json, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
CAND = HERE / "humble_seed_v0_8_6_candidate.py"
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m
H = load(HERE / "falsify_v0_8_6.py", "rt_harness")
K = H.load_module(CAND, "rt_candidate")
DECL = json.loads((HERE / "DECLARED_v0_8_6.json").read_text())
lines = CAND.read_text().splitlines()
WANT = (K.StaleOrganism, K.RollbackDetected, K.IntegrityError, K.AttestationRefused, OSError)

for name, spec in DECL["tests"].items():
    if "refusal_trace" not in spec:
        continue
    seen, origins = set(), []
    def local(frame, event, arg):
        if event == "exception":
            exc = arg[1]
            if isinstance(exc, WANT) and id(exc) not in seen:
                seen.add(id(exc))
                origins.append((frame.f_lineno, frame.f_code.co_name, type(exc).__name__, str(exc)[:70]))
        return local
    def glob(frame, event, arg):
        return local if frame.f_code.co_filename == str(CAND) else None
    fn = getattr(H, name)
    with tempfile.TemporaryDirectory() as t:
        sys.settrace(glob)
        try:
            fn(K, Path(t)); status = "PASS"
        except Exception as e:
            status = f"{type(e).__name__}: {e}"
        finally:
            sys.settrace(None)
    print(f"{name}: {status}")
    print(f"  declared: {spec['refusal_trace']}")
    for ln, fname, et, msg in origins:
        print(f"  raised at L{ln} in {fname}: {et}: {msg}")
        print(f"      L{ln}: {lines[ln - 1].strip()[:100]}")
