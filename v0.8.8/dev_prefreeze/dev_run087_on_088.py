import importlib.util, sys, json, tempfile, shutil
from pathlib import Path
def load(p, n):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); sys.modules[n] = m; s.loader.exec_module(m); return m
H = load(sys.argv[1], "h087")
K = load(sys.argv[2], "k088")
res = H.run_suite(K)
bad = {n: r for n, r in res.items() if r["status"] != "PASS"}
print(len(res), "tests;", len(bad), "not passing")
for n, r in bad.items(): print(n, r)
d = Path(tempfile.mkdtemp()); 
try: print("S1", H.S1_two_threads_stress(K, d))
finally: shutil.rmtree(d, ignore_errors=True)
