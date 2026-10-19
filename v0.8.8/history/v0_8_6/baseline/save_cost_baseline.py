#!/usr/bin/env python3
"""P5 baseline: the same dwell-timing loop against v0.8.5 and v0.8.6, back to back, same machine.
Run from hs086/: python3 -I baseline/save_cost_baseline.py"""
import importlib.util, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m
for tag, cand, harn in (("v0.8.5", ROOT / "v0_8_5_record" / "humble_seed_v0_8_5_candidate.py", ROOT / "v0_8_5_record" / "falsify_v0_8_5.py"),
                        ("v0.8.6", ROOT / "humble_seed_v0_8_6_candidate.py", ROOT / "falsify_v0_8_6.py")):
    K = load(cand, "k" + tag.replace(".", "")); H = load(harn, "h" + tag.replace(".", ""))
    with tempfile.TemporaryDirectory() as t:
        s, o = H.born(K, Path(t)); row = []
        for target in (10, 500, 2000):
            while len(s.trace) < target - 20: s.dwell_or_propose("formality", "evt", "hmm ok")
            t0 = time.perf_counter()
            for _ in range(20): s.dwell_or_propose("formality", "evt", "hmm ok")
            row.append(f"len {len(s.trace)}: {(time.perf_counter() - t0) / 20 * 1000:.2f} ms")
        print(tag, " | ".join(row), flush=True)
