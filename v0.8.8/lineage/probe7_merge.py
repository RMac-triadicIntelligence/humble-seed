#!/usr/bin/env python3
"""
v0.7 merge probe — M1..M4.

Each arm runs the SAME attack against all three kernels: Kernel P
(genesis_hash), Kernel A (birth_root, split witness), and the v0.7 merge. An
arm is only evidence for the merge if at least one base kernel accepts what the
merge rejects.

If all three reject, the merge added nothing there and the arm says so.

Usage:  python3 probe7_merge.py
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(alias: str, path: Path):
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


KERNELS: dict[str, object] = {}
for alias, rel in (
    ("P", "kernels/kernel_p.py"),
    ("A", "kernels/kernel_a.py"),
    ("M", "humble_seed_v0_7.py"),
):
    p = HERE / rel
    if p.exists():
        KERNELS[alias] = load(f"hs_{alias}", p)

LABEL = {"P": "Kernel P", "A": "Kernel A", "M": "v0.7 merge"}
RESULTS: list[tuple[str, dict[str, str]]] = []


def hatch(K, d: Path):
    """Hatch an organism. Returns the seed after a successful birth."""
    seed = K.HumbleSeed(d)
    seed.hatch()
    return seed


def arm(name: str, fn) -> None:
    """Run fn(K) for each kernel; record 'rejected: ...' or 'ACCEPTED'."""
    row: dict[str, str] = {}
    for alias, K in KERNELS.items():
        d = Path(tempfile.mkdtemp())
        try:
            fn(K, d)
            row[alias] = "ACCEPTED"
        except Exception as exc:
            msg = str(exc).split("—")[0].strip()
            row[alias] = f"rejected: {msg[:64]}"
        finally:
            shutil.rmtree(d, ignore_errors=True)
    RESULTS.append((name, row))
    print(f"\n{name}")
    for alias in ("P", "A", "M"):
        if alias in row:
            print(f"    {LABEL[alias]:<12} {row[alias]}")


# ---------------------------------------------------------------------------
# M2 — record() must validate before writing.
# ---------------------------------------------------------------------------
def m2_unvalidated_record(K, d: Path):
    """Hand the witness a checkpoint it should refuse and see if it stores it.

    Attack: the witness holds sequence N. Present a checkpoint at a wild
    sequence with an unrelated parent. If record() writes without checking,
    the witness has been made to forget its own head.
    """
    w = K.OwnerWitness(d / "witness.json")
    cp = _fake_checkpoint(K, sequence=0, prev="0" * 64)
    w.record(cp)                                  # legitimate enrollment
    rogue = _fake_checkpoint(K, sequence=99, prev="f" * 64)
    w.record(rogue)                               # must raise
    # If we get here the ledger was overwritten by an invalid checkpoint.
    head = w.ledger[cp.organism_id]["sequence"]
    if head != 99:
        raise AssertionError("record() rejected without raising")


# ---------------------------------------------------------------------------
# M1 — identity pinning.
# ---------------------------------------------------------------------------
def m1_identity_substitution(K, d: Path):
    """A different organism claims an existing identity on the witness.

    Attack: witness holds a chain for organism_id X. Present a checkpoint
    with the same organism_id and the same sequence position, but a different
    birth/genesis root -- a fresh keypair wearing the same name. A witness
    that stores only (sequence, checkpoint_hash) has no field to object with.
    """
    w = K.OwnerWitness(d / "witness.json")
    cp = _fake_checkpoint(K, sequence=0, prev="0" * 64)
    w.record(cp)
    impostor = _fake_checkpoint(K, sequence=1, prev=_cp_hash(K, cp), identity="IMPOSTOR")
    _successor_check(K, w, impostor)


# ---------------------------------------------------------------------------
# M4 — enrollment must be parentless.
# ---------------------------------------------------------------------------
def m4_parented_enrollment(K, d: Path):
    """Enroll at sequence 0 while pointing at a parent nobody has seen."""
    w = K.OwnerWitness(d / "witness.json")
    cp = _fake_checkpoint(K, sequence=0, prev="a" * 64)
    _successor_check(K, w, cp)


# ---------------------------------------------------------------------------
# M3 — exactly one birth event.
# ---------------------------------------------------------------------------
def m3_second_birth_event(K, d: Path):
    """A second birth event later in the trace.

    The chain hash covers it, so this is not a post-hoc forgery -- it is an
    organism that emitted two. Kernel A checks trace[0] only.
    """
    seed = hatch(K, d)
    # Re-emit the birth event through the organism's own append path, so the
    # hash chain stays intact. This is an organism that emitted two births,
    # not a post-hoc edit of the file.
    dup = {k: v for k, v in seed.trace[0].items()
           if k not in ("prev_hash", "entry_hash")}
    seed._append_trace(dup)
    seed.verify()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _identity_field(K) -> str:
    fields = K.Checkpoint.__dataclass_fields__
    return "birth_root" if "birth_root" in fields else "genesis_hash"


def _fake_checkpoint(K, *, sequence: int, prev: str, identity: str = "ORIGIN"):
    fields = K.Checkpoint.__dataclass_fields__
    kw: dict[str, object] = {}
    for name, f in fields.items():
        t = f.type if isinstance(f.type, str) else getattr(f.type, "__name__", "str")
        kw[name] = 0 if "int" in t else (0.0 if "float" in t else "0" * 64)
    kw["organism_id"] = "org-under-test"
    kw["sequence"] = sequence
    kw["prev_checkpoint_hash"] = prev
    kw[_identity_field(K)] = identity
    kw["attested_trace_len"] = 1
    kw["mutation_sequence"] = 0
    kw["timestamp"] = 0.0
    return K.Checkpoint(**kw)


def _cp_hash(K, cp) -> str:
    return K._sha256(K.HumbleSeed.checkpoint_payload(cp))


def _successor_check(K, w, cp) -> None:
    if hasattr(w, "check_successor"):
        w.check_successor(cp)
    else:
        w.check(cp)


if __name__ == "__main__":
    print("=" * 74)
    print("v0.7 MERGE PROBE — same attack against Kernel P, Kernel A, and the merge")
    print("=" * 74)
    print(f"kernels loaded: {', '.join(LABEL[a] for a in KERNELS)}")

    arm("M1  identity substitution on the witness", m1_identity_substitution)
    arm("M2  record() stores a checkpoint it should refuse", m2_unvalidated_record)
    arm("M3  a second birth event in the trace", m3_second_birth_event)
    arm("M4  enrollment at sequence 0 with a nonzero parent", m4_parented_enrollment)

    print("\n" + "=" * 74)
    added = diagnosis = 0
    for name, row in RESULTS:
        if "M" not in row:
            continue
        merge_rejects = row["M"].startswith("rejected")
        base_accepts = any(row.get(a, "").startswith("ACCEPTED") for a in ("P", "A"))
        if not merge_rejects:
            print(f"  MERGE ACCEPTS        {name}  <-- unclosed")
            continue
        if base_accepts:
            added += 1
            print(f"  MERGE ADDS COVERAGE  {name}")
            continue
        # All reject. Do they reject for the SAME reason? A kernel that
        # refuses on an unrelated earlier check has not tested this property.
        merge_reason = row["M"].split(":", 1)[1].strip().lower()[:24]
        same = [a for a in ("P", "A")
                if a in row and merge_reason in row[a].lower()]
        if len(same) == len([a for a in ("P", "A") if a in row]):
            print(f"  all kernels reject   {name}  (merge added nothing here)")
        else:
            diagnosis += 1
            missed = [LABEL[a] for a in ("P", "A")
                      if a in row and merge_reason not in row[a].lower()]
            print(f"  DIAGNOSIS ONLY       {name}")
            print(f"       {', '.join(missed)} refuses on an unrelated earlier check, "
                  f"never reaching this property")
    print(f"\n  {added}/{len(RESULTS)} arms: the merge catches what a base kernel accepts.")
    print(f"  {diagnosis}/{len(RESULTS)} arms: same verdict, but only the merge names the "
          f"actual cause.")
    print("=" * 74)
