#!/usr/bin/env python3
"""Writes CLAIMS.json for the v0.8.6 claims battery. Every claim is quoted verbatim from the
frozen candidate's docstring (whitespace-normalized), and the script refuses if one is not."""
import ast, json, re, sys
from pathlib import Path

cand, out = Path(sys.argv[1]), Path(sys.argv[2])
doc = re.sub(r"\s+", " ", ast.get_docstring(ast.parse(cand.read_text(encoding="utf-8"))))

CLAIMS = [
    ("O1", "O", "The saved state carries a generation number."),
    ("O2", "O", "Every save runs under the organism's own lock (organism.lock, POSIX flock, reentrant within a thread)."),
    ("O3", "O", "It writes only if the saved generation is still the one this object last loaded or wrote. Otherwise it raises StaleOrganism, and the object must reload."),
    ("O4", "O", "A new hatch cannot overwrite an existing organism."),
    ("O5", "O", "attest holds the organism lock from recovery to the witness commit."),
    ("O6", "O", "It refuses a stale object before signing anything."),
    ("I1", "I", "A save can fail after its replace has already landed: the directory fsync comes last. On a failure, the saved generation is re-read."),
    ("I2", "I", "install_checkpoint rolls memory back only if the new state did not land, so memory always matches disk."),
    ("C1", "C", "A pending intent counts as installed only if the saved state names it and also loads and verifies on its own."),
    ("C2", "C", "A saved state that claims the intent but does not verify is neither completed nor abandoned."),
    ("C3", "C", "Abandoning still requires the saved checkpoint to be the witness head."),
    ("M1", "M", "The owner's refusal names its own window (\"its latest answer in verbosity since it signed the previous verbosity crossing is 'no'\"), not the organism's."),
    ("R30a", "R30", "Recovery completes an intent only from a saved state that verifies, and abandons one only if the saved checkpoint is the witness head."),
    ("R30b", "R30", "An edit made outside the protocol (writing the file directly) is not prevented."),
    ("R30c", "R30", "A rewind to the exact pre-install file looks the same as an install that never happened, and is abandoned."),
    ("R31a", "R31", "Only install_checkpoint is transactional in memory."),
    ("R31b", "R31", "If another operation's save fails before landing, the object is ahead of its disk and its next save writes that state."),
    ("R31c", "R31", "Because of the generation check, no other object can write over it."),
    ("R32a", "R32", "The organism lock is POSIX flock, like the owner lock (R26)."),
    ("R32b", "R32", "Writers that bypass HumbleSeed._save are not serialized."),
    ("R33a", "R33", "A stale object must reload, and its unsaved changes are lost."),
    ("R33b", "R33", "An answer given through a stale object reaches the owner's ledger, which is authoritative, but not the organism."),
    ("R34", "R34", "Every save re-reads the saved state to check its generation, a cost that grows with the trace"),
    ("W1", "W", "answers given before the owner signed the previous crossing were already checked when that crossing was attested, so the window holds without assuming when the organism issued the reading."),
]
for cid, _, text in CLAIMS:
    if re.sub(r"\s+", " ", text) not in doc:
        raise SystemExit(f"{cid} is not verbatim in the docstring: {text}")

QUESTIONS = [
    ("Q1", "Is there any interleaving of processes, threads or organism objects that loses a saved update, "
           "or leaves the witness and the saved file in a state that recovery cannot resolve?"),
    ("Q2", "Is there any failed or interrupted save that leaves a state that can never be signed off, "
           "or that lets something be signed off that the owner did not approve?"),
]
out.write_text(json.dumps({"source": cand.name, "claims": [{"id": c, "group": g, "text": t} for c, g, t in CLAIMS],
                           "open_questions": [{"id": q, "text": t} for q, t in QUESTIONS]}, indent=2) + "\n")
print(f"{len(CLAIMS)} claims verified verbatim; {len(QUESTIONS)} open questions; written {out}")
