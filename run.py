#!/usr/bin/env python3
"""Run a supplied snapshot with its matching imports in an isolated directory."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Case:
    script: str
    imports: str
    description: str


CASES = {
    "demo": Case("humble_seed_v0_6.py", ".", "Primary v0.6 demonstration"),
    "validate": Case("probes/probe6_validation.py", ".", "Supplied v0.6 assertion suite"),
    "example": Case("examples/owner_authorization.py", ".", "Owner authorization walkthrough"),
    "demo-v03": Case("history/v0_3/humble_seed_v0_3.py", "history/v0_3", "Historical v0.3 demo"),
    "demo-v04": Case("history/v0_4/humble_seed_v0_4.py", "history/v0_4", "Historical v0.4 demo"),
    "probe-v04": Case("history/v0_4/probe4.py", "history/v0_4", "Historical v0.4 observations"),
    "demo-v05": Case("history/v0_5/humble_seed_v0_5.py", "history/v0_5", "Historical v0.5 demo"),
    "probe-v05": Case("history/v0_5/probe5.py", "history/v0_5", "Historical v0.5 observations"),
    "demo-v06-birth-root": Case(
        "variants/v0_6_birth_root/humble_seed_v0_6.py", "variants/v0_6_birth_root",
        "Alternative v0.6 birth-root demo",
    ),
    "probe-v06-birth-root": Case(
        "variants/v0_6_birth_root/probe6.py", "variants/v0_6_birth_root",
        "Alternative v0.6 observations",
    ),
    "triage-v06-birth-root": Case(
        "variants/v0_6_birth_root/triage6.py", "variants/v0_6_birth_root",
        "Alternative v0.6 triage observations",
    ),
}

# -I ignores ambient PYTHONPATH and PYTHONOPTIMIZE. Explicit import directories
# prevent the two identically named v0.6 modules from being mixed accidentally.
CHILD = """
from pathlib import Path
import runpy
import sys
script, imports = sys.argv[1:]
sys.path.insert(0, str(Path(imports).resolve()))
sys.argv = [script]
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
runpy.run_path(script, run_name='__main__')
"""


def execute(name: str, workspace: Path) -> int:
    case = CASES[name]
    working = workspace / name
    working.mkdir()
    print(f"\n[{name}] {case.description}", flush=True)
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-c", CHILD,
             str(ROOT / case.script), str(ROOT / case.imports)],
            cwd=working, capture_output=True, text=True, encoding="utf-8",
            timeout=60, check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"[{name}] timed out after 60 seconds", file=sys.stderr)
        return 1
    output = result.stdout + result.stderr
    (workspace / f"{name}.log").write_text(output, encoding="utf-8")
    print(output, end="" if output.endswith("\n") else "\n", flush=True)
    print(f"[{name}] exit {result.returncode}", flush=True)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", default="demo", choices=[*CASES, "all", "list"])
    parser.add_argument(
        "--output-dir", type=Path,
        help="Preserve logs and data in a NEW directory; existing paths are refused.",
    )
    args = parser.parse_args()
    if args.target == "list":
        for name, case in CASES.items():
            print(f"{name:25} {case.description}")
        return 0
    selected = list(CASES) if args.target == "all" else [args.target]
    if args.output_dir:
        output_dir = args.output_dir.expanduser().resolve()
        try:
            output_dir.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            parser.error(f"Cannot create a new output directory: {exc}")
        context = nullcontext(str(output_dir))
    else:
        context = tempfile.TemporaryDirectory(prefix="humble-seed-")
    with context as directory:
        codes = [execute(name, Path(directory)) for name in selected]
        print(f"\n{sum(code == 0 for code in codes)}/{len(codes)} scripts completed without process errors.")
        print("Printed observations are not assertions; see docs/VALIDATION.md.")
        if args.output_dir:
            print(f"Logs and data: {directory}")
    return 1 if any(codes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
