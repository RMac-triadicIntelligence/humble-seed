#!/usr/bin/env python3
"""Reproduce from an extracted review bundle. Requires cryptography; no network."""
import hashlib
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
package = root / "package" / "humble_seed_v0_8_1_candidate_BLIND"
for manifest in ("MANIFEST.sha256", "CANDIDATE_v0_8_1_AT_FREEZE.sha256",
                 "DECLARED_v0_8_1.sha256"):
    for line in (package / manifest).read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        got = hashlib.sha256((package / name.lstrip("*")).read_bytes()).hexdigest()
        if got != expected:
            raise SystemExit("Hash mismatch: " + name)
print("Original package manifest and freeze hashes verified", flush=True)
baseline = subprocess.run([sys.executable, "-I", "falsify_v0_8_1.py"], cwd=package)
attacks = subprocess.run([sys.executable, "-I", str(root / "review" / "independent_attacks.py"),
                          str(package)], cwd=root)
print("baseline_exit_code=" + str(baseline.returncode), flush=True)
print("independent_exit_code=" + str(attacks.returncode), flush=True)
sys.exit(1 if baseline.returncode or attacks.returncode else 0)
