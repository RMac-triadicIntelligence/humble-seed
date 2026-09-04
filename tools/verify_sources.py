#!/usr/bin/env python3
"""Check that all supplied snapshots still match their recorded SHA-256 hashes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    manifest = json.loads((ROOT / "provenance/sources.json").read_text(encoding="utf-8"))
    failures = []
    for item in manifest["files"]:
        path = ROOT / item["repository_path"]
        try:
            content = path.read_bytes()
        except OSError as exc:
            failures.append(f"{item['repository_path']}: {exc}")
            continue
        if len(content) != item["size_bytes"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
            failures.append(f"{item['repository_path']}: differs from supplied snapshot")
    if failures:
        print("\n".join(failures))
        return 1
    print(f"Verified {len(manifest['files'])} unchanged source files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
