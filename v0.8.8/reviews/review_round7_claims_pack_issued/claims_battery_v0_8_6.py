#!/usr/bin/env python3
"""Claims battery for Humble Seed v0.8.6: a scaffold for checking whether each documented claim
in the candidate's docstring is accurate as stated.

The claims are in CLAIMS.json, quoted verbatim from the docstring. For each claim there is one
check_<ID>(d) function below. Fill it in, so that it returns:
    {"verdict": "HOLDS" | "HOLDS WITH CAVEATS" | "WRONG" | "NOT TESTED",
     "evidence": <anything JSON-serializable: what you ran and what it returned>}
Open questions Q1 and Q2 have check_Q1 and check_Q2; a "verdict" there is "FOUND" or "NOT FOUND".
Anything else you find goes in a function named extra_<name>(d); it is run and reported too.

Each function gets a fresh, empty temporary directory d (a pathlib.Path).
Run:  python3 -I claims_battery_v0_8_6.py
Output: a table on stdout, and CLAIMS_RESULTS_v0_8_6.json next to this file.
"""
import importlib.util, json, os, stat, subprocess, sys, tempfile, threading, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAND = HERE / "humble_seed_v0_8_6_candidate.py"
CLAIMS = json.loads((HERE / "CLAIMS.json").read_text())


def _load(path, alias):
    spec = importlib.util.spec_from_file_location(alias, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[alias] = m          # needed: the candidate defines dataclasses
    spec.loader.exec_module(m)
    return m


K = _load(CAND, "hs086")

# ---------------------------------------------------------------------------
# Helpers (use, change or ignore them; nothing below is part of the candidate)
# ---------------------------------------------------------------------------
PREF = "I always prefer shorter answers"   # the stub interpreter reads this as a preference -> a proposal
PLAIN = "hmm ok"                           # read as unclear -> the organism dwells (a non-authorizing event)


def born(d):
    """A hatched organism whose genesis the owner has attested. Returns (seed, owner)."""
    seed = K.HumbleSeed(d / "org")
    _, pem, _ = seed.hatch()
    owner = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json"))
    assert owner.attest(seed) is True
    return seed, owner


def reading(seed, category="verbosity"):
    r = seed.dwell_or_propose(category, "evt", PREF)
    assert r["status"] == "proposal", r["status"]
    return r


def apply(seed, owner, r, attest=True):
    """Owner signs the reading; organism applies it; optionally the owner attests the result."""
    res = seed.authorize_and_apply(r["proposal_id"], owner.sign_proposal(r["payload_to_sign"]))
    assert res is not None, seed.trace[-1]
    if attest:
        assert owner.attest(seed) is True
    return res


def dwell(seed, category="formality"):
    r = seed.dwell_or_propose(category, "evt", PLAIN)
    assert r["status"] == "dwelling", r["status"]
    return r


def reload(seed_or_dir):
    """A new organism object loaded from the saved file (raises if the file does not load)."""
    data_dir = seed_or_dir.data_dir if hasattr(seed_or_dir, "data_dir") else Path(seed_or_dir)
    f = K.HumbleSeed(data_dir)
    f.load()
    return f


def saved(seed):
    """The organism's saved file, parsed."""
    return json.loads(seed._state_path().read_text())


def reopen_owner(owner):
    """A new owner session over the same witness file and key."""
    return K.OwnerTool(owner._pem, K.OwnerWitness(owner.witness.path))


def witness_seq(owner, seed):
    return K.OwnerWitness(owner.witness.path).ledger[seed.organism_id]["sequence"]


def intent_pending(owner, seed):
    return K.OwnerWitness(owner.witness.path).pending_for(seed.organism_id) is not None


def outcome(fn):
    """Run fn(); return what it returned or what it raised, as data."""
    try:
        return {"returned": fn()}
    except Exception as e:
        return {"exception": type(e).__name__, "message": str(e)}


LOADER = ("import importlib.util, sys\n"
          "spec = importlib.util.spec_from_file_location('hs086', sys.argv[1])\n"
          "K = importlib.util.module_from_spec(spec); sys.modules['hs086'] = K; spec.loader.exec_module(K)\n")


def python_subprocess(code, *args, timeout=300, wait=True):
    """Run `LOADER + code` in a separate Python process. Inside it, K is the candidate and
    sys.argv[2:] are *args (as strings). With wait=False, returns the Popen object."""
    cmd = [sys.executable, "-I", "-c", LOADER + code, str(CAND), *map(str, args)]
    if not wait:
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return {"rc": p.returncode, "stdout": p.stdout[-4000:], "stderr": p.stderr[-4000:]}


NOT_TESTED = {"verdict": "NOT TESTED", "evidence": None}


# ---------------------------------------------------------------------------
# Worked example
# ---------------------------------------------------------------------------

def check_O1(d):
    """The saved state carries a generation number. (Example: checked here for hatch, attest, dwell.)"""
    seed = K.HumbleSeed(d / "org")
    _, pem, _ = seed.hatch()
    gens = [saved(seed).get("generation")]
    owner = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json"))
    owner.attest(seed)
    gens.append(saved(seed).get("generation"))
    for _ in range(3):
        dwell(seed)
        gens.append(saved(seed).get("generation"))
    ints = all(isinstance(g, int) and not isinstance(g, bool) for g in gens)
    steps = [b - a for a, b in zip(gens, gens[1:])] if ints else None
    verdict = "HOLDS" if ints and steps == [1] * len(steps) else "WRONG"
    return {"verdict": verdict, "evidence": {"generations_after_each_save": gens, "steps": steps}}


# ---------------------------------------------------------------------------
# Claims to check (texts from CLAIMS.json). Replace `return NOT_TESTED`.
# ---------------------------------------------------------------------------

def check_O2(d): return NOT_TESTED
def check_O3(d): return NOT_TESTED
def check_O4(d): return NOT_TESTED
def check_O5(d): return NOT_TESTED
def check_O6(d): return NOT_TESTED
def check_I1(d): return NOT_TESTED
def check_I2(d): return NOT_TESTED
def check_C1(d): return NOT_TESTED
def check_C2(d): return NOT_TESTED
def check_C3(d): return NOT_TESTED
def check_M1(d): return NOT_TESTED
def check_R30a(d): return NOT_TESTED
def check_R30b(d): return NOT_TESTED
def check_R30c(d): return NOT_TESTED
def check_R31a(d): return NOT_TESTED
def check_R31b(d): return NOT_TESTED
def check_R31c(d): return NOT_TESTED
def check_R32a(d): return NOT_TESTED
def check_R32b(d): return NOT_TESTED
def check_R33a(d): return NOT_TESTED
def check_R33b(d): return NOT_TESTED
def check_R34(d): return NOT_TESTED
def check_W1(d): return NOT_TESTED

# Open questions: return {"verdict": "FOUND" | "NOT FOUND" | "NOT TESTED", "evidence": ...}
def check_Q1(d): return NOT_TESTED
def check_Q2(d): return NOT_TESTED

# Anything else: define extra_<name>(d) returning {"verdict": <your label>, "evidence": ...}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
CLAIM_VERDICTS = {"HOLDS", "HOLDS WITH CAVEATS", "WRONG", "NOT TESTED"}
QUESTION_VERDICTS = {"FOUND", "NOT FOUND", "NOT TESTED"}


def _run(fn):
    with tempfile.TemporaryDirectory(prefix="hs086_claims_") as t:
        d = Path(t) / "case"
        d.mkdir()
        t0 = time.time()
        try:
            r = fn(d)
        except Exception as e:
            r = {"verdict": "ERROR", "evidence": f"{type(e).__name__}: {e}",
                 "traceback": traceback.format_exc()[-2000:]}
        r["seconds"] = round(time.time() - t0, 2)
        return r


def main():
    results = {"python": sys.version.split()[0], "candidate": CAND.name, "claims": {}, "open_questions": {}, "extra": {}}
    try:
        import cryptography
        results["cryptography"] = cryptography.__version__
    except Exception:
        pass
    rows = []
    for section, items, allowed in (("claims", CLAIMS["claims"], CLAIM_VERDICTS),
                                    ("open_questions", CLAIMS["open_questions"], QUESTION_VERDICTS)):
        for c in items:
            fn = globals().get(f"check_{c['id']}")
            r = _run(fn) if fn else {"verdict": "ERROR", "evidence": f"no check_{c['id']} defined"}
            if r.get("verdict") not in allowed | {"ERROR"}:
                r["verdict_not_in_allowed_set"] = r.get("verdict")
            r["claim"] = c["text"]
            results[section][c["id"]] = r
            rows.append((c["id"], r.get("verdict")))
    for name in sorted(n for n in globals() if n.startswith("extra_") and callable(globals()[n])):
        r = _run(globals()[name])
        results["extra"][name] = r
        rows.append((name, r.get("verdict")))
    out = HERE / "CLAIMS_RESULTS_v0_8_6.json"
    out.write_text(json.dumps(results, indent=2, sort_keys=True, default=repr))
    print(f"Humble Seed v0.8.6 claims battery  (Python {results['python']}, cryptography {results.get('cryptography')})")
    for cid, v in rows:
        print(f"  {cid:<28} {v}")
    print(f"written {out.name}")


if __name__ == "__main__":
    main()
