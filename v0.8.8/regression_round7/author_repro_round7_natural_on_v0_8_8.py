#!/usr/bin/env python3
"""Q1 with no patching of the candidate: two real threads share one organism object (A dwells,
B applies and attests). The only change is the interpreter's thread switch interval, set short so
preemption is frequent (as on a loaded machine, or with no GIL at all on free-threaded Python).
Run from hs086/: python3 -I review_round7_chatgpt/author_repro_round7_natural.py <switch_interval> <seconds>"""
import importlib.util, json, sys, tempfile
from pathlib import Path
sys.path_hooks  # no-op; keep -I semantics
spec = importlib.util.spec_from_file_location("rp", Path(__file__).with_name("author_repro_round7_on_v0_8_8.py"))
R = importlib.util.module_from_spec(spec); sys.modules["rp"] = R; spec.loader.exec_module(R)
interval, seconds = float(sys.argv[1]), float(sys.argv[2])
sys.setswitchinterval(interval)
runs = []
for i in range(3):
    with tempfile.TemporaryDirectory() as t:
        d = Path(t) / "c"; d.mkdir()
        r = R.Q1c_two_real_threads(d, seconds)
        runs.append(r)
print(json.dumps({"switch_interval": interval, "seconds_per_run": seconds, "runs": runs}, indent=1, default=str))
