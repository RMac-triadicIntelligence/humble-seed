#!/usr/bin/env python3
"""
Two additional arms for the v0.7 lineage. Nothing in the repository is
modified; this file imports probe7_merge for its loader and helpers and
writes all state to temporary directories.

M5   the reverse differential arm. Every arm in probe7_merge tests a property
     Kernel P had and Kernel A lacked. This one tests the opposite direction:
     a property CONVERGENCE.md claims for Kernel A. If Kernel P accepts what
     Kernel A rejects, non-dominance is demonstrated rather than asserted.

R10  sole-objector ablation. The paper claims constitution_root is defence in
     depth and never fires as the only objection. That is currently an
     inspection claim. This arm suppresses earlier bindings one at a time and
     reports how many must go before constitution_root is reached at all.

Usage:  python3 probe7_m5_r10.py   (run from the repo's merge/ directory)
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe7_merge as H  # loader, KERNELS, _fake_checkpoint, _cp_hash

LABEL = H.LABEL


# ---------------------------------------------------------------------------
# M5 — unwitnessed advance presented as the current state
# ---------------------------------------------------------------------------
def m5_unwitnessed_advance(K, d: Path) -> None:
    """
    The witness holds sequence 0. The organism presents a well-formed child at
    sequence 1, correctly parented to the recorded head — a checkpoint the
    witness has never recorded.

    Asked as an AUDIT question ("is the state in front of me the state this
    witness attested?") the correct answer is no. Kernel P has only one
    predicate, which accepts the head or its valid child, so it cannot express
    the question. Kernel A splits check_current from check_successor.
    """
    w = K.OwnerWitness(d / "witness.json")
    head = H._fake_checkpoint(K, sequence=0, prev="0" * 64)
    w.record(head)

    child = H._fake_checkpoint(K, sequence=1, prev=H._cp_hash(K, head))
    # The audit question, expressed with whatever the kernel offers.
    if hasattr(w, "check_current"):
        w.check_current(child)
    else:
        w.check(child)


# ---------------------------------------------------------------------------
# R10 — is constitution_root reachable as a sole objector?
# ---------------------------------------------------------------------------
def r10_ablation() -> None:
    """
    Escalating attacker: repair each local binding the constitution swap
    breaks, and record which check objects at each stage. The question is
    whether constitution_root is ever the thing standing between the attacker
    and success, or whether something else always gets there first.
    """
    K = H.KERNELS.get("M")
    if K is None:
        print("  v0.7 kernel not loaded; skipping")
        return

    d = Path(tempfile.mkdtemp())
    seed = K.HumbleSeed(d)
    oid, pem, genesis_cp = seed.hatch()
    owner = K.OwnerTool(pem, K.OwnerWitness(d / "w.json"))
    owner.attest(seed, genesis_cp)

    stages = [
        ("swap constitution only",              ["constitution"]),
        ("+ repair birth.constitution_hash",    ["constitution", "birth_ch"]),
        ("+ repair birth.genesis_hash",         ["constitution", "birth_ch", "genesis"]),
        ("+ repair birth trace entry",          ["constitution", "birth_ch", "genesis", "trace0"]),
    ]

    pristine = (d / "organism_state.json").read_text()
    results = []
    for label, ops in stages:
        (d / "organism_state.json").write_text(pristine)
        s2 = K.HumbleSeed(d)
        s2.load()
        out = K._reseal_attack(s2, _mutator(K, ops), rechain=True)
        results.append((label, out))

    for n, (label, out) in enumerate(results):
        msg = out.split("—")[0].strip()
        print(f"  [{n}] {label}")
        print(f"      objector: {msg[:86]}")

    reached = any("Constitution does not match the attested" in o for _, o in results)
    print()
    if reached:
        print("  constitution_root FIRED as the sole objector — R10 is too weak a claim")
    else:
        last = results[-1][1]
        print("  constitution_root never fired. Final objector on the fully-repaired path:")
        print(f"    {last.split(':', 1)[-1].strip()[:88]}")
        print("  -> R10 confirmed empirically: the constitution is bound into the birth")
        print("     record, so birth_root reaches the attacker first on every local path.")
        print("     constitution_root is implemented and shadowed, not independently")
        print("     exercised. Repairing birth_root requires the owner key, which is")
        print("     the property actually doing the work.")

    import shutil
    shutil.rmtree(d, ignore_errors=True)


def _mutator(K, ops):
    def mutate(st):
        if "constitution" in ops:
            st["constitution"]["allowed_character_fields"].append("obedience")
            st["constitution"]["invariants"] = ["anything goes"]
        ch = K._sha256(K._canonical_json(st["constitution"]))
        if "birth_ch" in ops:
            st["birth"]["constitution_hash"] = ch
        if "genesis" in ops:
            st["birth"]["genesis_hash"] = K.HumbleSeed._derive_genesis(
                st["birth"]["organism_id"], st["birth"]["public_key_b64"],
                st["birth"]["created_at"], st["birth"]["constitution_hash"],
            )
        if "trace0" in ops:
            st["trace"][0]["constitution_hash"] = st["birth"]["constitution_hash"]
            st["trace"][0]["genesis_hash"] = st["birth"]["genesis_hash"]
    return mutate


if __name__ == "__main__":
    print("=" * 74)
    print("M5 + R10 — reverse differential arm and sole-objector ablation")
    print("=" * 74)
    print(f"kernels loaded: {', '.join(LABEL[a] for a in H.KERNELS)}")

    H.arm("M5  unwitnessed advance presented as the current state",
          m5_unwitnessed_advance)

    print("\n" + "-" * 74)
    print("R10  sole-objector ablation on v0.7 (constitution swapped, "
          "re-chained, resealed)")
    print("-" * 74)
    r10_ablation()
    print("=" * 74)
