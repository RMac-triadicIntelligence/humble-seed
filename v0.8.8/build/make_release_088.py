#!/usr/bin/env python3
"""Assembles the publication release of Humble Seed v0.8.8 (work in progress)."""
import hashlib, json, os, shutil, sys, zipfile
from pathlib import Path

S = Path(__file__).resolve().parent
NAME = "Humble_Seed_v0.8.8"
OUT = S / "release" / NAME
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
SKIP_DIRS = {"__pycache__"}


def copytree(src: Path, dst: Path, skip=lambda p: False):
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if any(part in SKIP_DIRS for part in rel.parts) or skip(rel):
            continue
        q = dst / rel
        if p.is_dir():
            q.mkdir(parents=True, exist_ok=True)
        elif p.is_symlink():
            raise SystemExit(f"symlink in release source: {p}")
        else:
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q)
            os.chmod(q, 0o644)


# 1. The current version, laid out exactly as it ran.
H = S / "hs088"
copytree(H, OUT, skip=lambda r: r.parts[0] in ("README.md",) or r.name == "FREEZE_v0_8_8.log")
shutil.copy2(H / "README.md", OUT / "README_v0_8_8.md")

# 2. Public documents and the quick start.
D = S / "release_draft"
for f in ("README.md", "CREDITS.md"):
    shutil.copy2(D / f, OUT / f)
res = json.loads((H / "RESULTS_v0_8_8.json").read_text())
ch = (D / "CHANGELOG.md").read_text()
for k, v in {"__V088_TESTS__": "87/88", "__V088_MUTANTS__": "85/87", "__V088_MISMATCHES__": "3 (one cause)",
             "__V088_RECEIPT__": res["receipt"][:8] + "…" + res["receipt"][-4:]}.items():
    assert ch.count(k) == 1, k
    ch = ch.replace(k, v)
assert res["mismatches"] == 3 and res["receipt"].startswith("3d3b3d1a")
(OUT / "CHANGELOG.md").write_text(ch)
shutil.copy2(S / "qs" / "quickstart.py", OUT / "quickstart.py")

# 3. Build scripts.
B = OUT / "build"; B.mkdir()
for f in ("make_candidate_088.py", "make_declared_088.py", "make_harness_088.py", "run_regression_088.sh",
          "make_release_088.py"):
    shutil.copy2(S / f, B / f)
shutil.copy2(H / "FREEZE_v0_8_8.log", B / "FREEZE_v0_8_8.log")
(B / "README.md").write_text(
    "# Build scripts (as run)\n\n"
    "- `make_candidate_088.py <v0.8.7 candidate> <out>`: derives the v0.8.8 candidate by exact-once edits.\n"
    "- `make_declared_088.py <dir>`: writes and freezes `DECLARED_v0_8_8.json`. It refuses if the harness or a\n"
    "  declaration already exists, and if any KILLED mutant's `killer` is outside its exact kill set.\n"
    "  `FREEZE_v0_8_8.log` is its output.\n"
    "- `make_harness_088.py <v0.8.7 harness> <out>`: derives `falsify_v0_8_8.py`. It was run after the freeze.\n"
    "- `run_regression_088.sh`: the unscored regression run. Its paths are the author's working paths.\n"
    "- `make_release_088.py`: assembles this release. Its paths are the author's working paths.\n")

# 4. Lineage probes used by the regression.
copytree(S / "lin088", OUT / "lineage")

# 5. History: each earlier version as it was frozen and scored.
HIST = OUT / "history"
VERS = [("hs08", "v0_8"), ("hs081", "v0_8_1"), ("hs082", "v0_8_2"), ("hs083", "v0_8_3"), ("hs084", "v0_8_4"),
        ("hs085", "v0_8_5"), ("hs086", "v0_8_6"), ("hs087", "v0_8_7")]
REVIEW_DIRS = {}
for src, tag in VERS:
    def skip(rel, src=src):
        top = rel.parts[0]
        if top.endswith("_record") or top.startswith("review_round") or top == "claims_battery":
            return True
        if rel.suffix == ".png":
            return True
        return False
    copytree(S / src, HIST / tag, skip=skip)
    for p in sorted((S / src).iterdir()):
        if p.is_dir() and (p.name.startswith("review_round") or p.name == "claims_battery"):
            REVIEW_DIRS[p] = p.name
# v0.8.1's T0 compares against the v0.8 candidate in v0_8_record/.
(HIST / "v0_8_1" / "v0_8_record").mkdir()
shutil.copy2(S / "hs081" / "v0_8_record" / "humble_seed_v0_8_candidate.py",
             HIST / "v0_8_1" / "v0_8_record" / "humble_seed_v0_8_candidate.py")
(HIST / "README.md").write_text(
    "# History: every earlier v0.8 version\n\n"
    "Each folder is that version's working directory as frozen and scored: its candidate, frozen declaration,\n"
    "harness, results, stdout, deviations (from v0.8.3 on, plus v0.8's `DEVIATIONS.md`), author probes and\n"
    "findings, opened seals, regression outputs and README. Run a harness from inside its folder, for example\n"
    "`cd v0_8_6 && python3 -I falsify_v0_8_6.py`. Each `REVIEWS.md` is the log as it stood at that version;\n"
    "the cumulative log is `../REVIEWS.md`.\n\n"
    "Omitted:\n"
    "- the `v0_8_X_record/` copies of the previous version, since each has its own folder here. The exception\n"
    "  is v0.8.1's `v0_8_record/humble_seed_v0_8_candidate.py`, which its T0 needs;\n"
    "- review archives and screenshots, which are in `../reviews/`.\n\n"
    "Some author probes and adapters refer to a previous version's record folder or to the author's working\n"
    "paths. Their outputs are kept as they were produced.\n")

# 6. Reviews, as received, with the author's re-runs.
R = OUT / "reviews"; R.mkdir()
for p, name in REVIEW_DIRS.items():
    dst = name if name != "claims_battery" else "review_round7_claims_pack_issued"
    copytree(p, R / dst)
copytree(S / "chatgpt_review", R / "review_round2_chatgpt")
shots = R / "review_round3_chatgpt_screenshots"; shots.mkdir()
seen = set()
for src in ("hs082", "hs083"):
    for png in sorted((S / src).glob("*.png")):
        h = hashlib.sha256(png.read_bytes()).hexdigest()
        if h not in seen:
            seen.add(h); shutil.copy2(png, shots / png.name)
(R / "README.md").write_text(
    "# Review archives\n\n"
    "| Folder | Round | Version reviewed |\n|---|---|---|\n"
    "| `review_round2_chatgpt` | 2 | v0.8.1 |\n"
    "| `review_round3_grok`, `review_round3_chatgpt_screenshots` | 3 | v0.8.2 |\n"
    "| `review_round4_chatgpt`, `review_round4_grok` | 4 | v0.8.3 |\n"
    "| `review_round5_chatgpt`, `review_round5_grok` | 5 | v0.8.4 |\n"
    "| `review_round6_chatgpt`, `review_round6_grok` | 6 | v0.8.5 |\n"
    "| `review_round7_chatgpt`, `review_round7_grok`, `review_round7_claims_pack_issued` | 7 | v0.8.6 |\n"
    "| `review_round8_chatgpt`, `review_round8_grok` | 8 | v0.8.7 |\n\n"
    "Round 1 (v0.8) and Grok's round 2 were reported as text only. They are recorded in `../REVIEWS.md`, as\n"
    "is every finding, its reproduction and its credit. Archives are kept as received, and the author's re-runs\n"
    "are beside them. The round-3 screenshots are files named \"round4\": ChatGPT's in-progress screen from\n"
    "round 3 on v0.8.2, reproduced by the author (`../REVIEWS.md`, round 3).\n\n"
    "`review_round8_grok/GROK_full_report_v0_8_7.zip` holds a throwaway test key: Grok's battery printed\n"
    "a `hatch()` return value from a temporary test folder. The key controls nothing.\n")

# 7a. The clean-extraction verification of the previous build (code files unchanged since; see below).
shutil.copy2(S / "release" / "VERIFY_CLEAN_EXTRACTION_v0_8_8.txt", OUT / "RELEASE_VERIFICATION.txt")

# 7. License notice.
(OUT / "LICENSE_NOTICE.md").write_text(
    "# License\n\nNot yet set. Copyright in this work is held by Soulshine (Tulsa, OK). A license will be chosen\n"
    "before or at publication; until one is added, no license is granted.\n")

# 8. Clean, then manifest.
for p in list(OUT.rglob("__pycache__")):
    shutil.rmtree(p)
for p in OUT.rglob("*.pyc"):
    p.unlink()
files = sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "MANIFEST.sha256")
lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(OUT).as_posix()}" for p in files]
(OUT / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")

# 9. Zip.
Z = S / "release" / f"{NAME}_release.zip"
if Z.exists():
    Z.unlink()
with zipfile.ZipFile(Z, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            z.write(p, f"{NAME}/{p.relative_to(OUT).as_posix()}")
print(len(files) + 1, "files;", Z, round(Z.stat().st_size / 1e6, 2), "MB")
print("zip sha256", hashlib.sha256(Z.read_bytes()).hexdigest())
