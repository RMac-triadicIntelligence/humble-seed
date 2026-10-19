#!/usr/bin/env python3
"""
Humble Seed v0.8.6 CANDIDATE — One Organism Persistence Protocol
================================================================

STATUS: candidate, not canonical. Parent: humble_seed_v0_8_5_candidate.py
(sha256 e505d432...). Round 6 (ChatGPT, blind) showed that the organism's saved
file had many writers and no protocol, and that recovery trusted it. A stale
organism object's ordinary save could erase newer, signed-off state. Everything
not listed is carried from v0.8.5 unchanged: the three rulings, the serialized
owner authority, saved-state recovery (V), apply = replay (A) and the
owner-verifiable category window (W).

CHANGES

  O  ONE ORGANISM PERSISTENCE PROTOCOL.
     - The saved state carries a generation number.
     - Every save runs under the organism's own lock (organism.lock, POSIX flock,
       reentrant within a thread). It writes only if the saved generation is still
       the one this object last loaded or wrote. Otherwise it raises
       StaleOrganism, and the object must reload.
     - A new hatch cannot overwrite an existing organism.
     - attest holds the organism lock from recovery to the witness commit. It
       refuses a stale object before signing anything.

  I  INDETERMINATE SAVES ARE RESOLVED, NOT ASSUMED. A save can fail after its
     replace has already landed: the directory fsync comes last. On a failure,
     the saved generation is re-read. install_checkpoint rolls memory back only
     if the new state did not land, so memory always matches disk.

  C  RECOVERY COMPLETES ONLY FROM A SAVED STATE THAT VERIFIES. A pending intent
     counts as installed only if the saved state names it and also loads and
     verifies on its own. A saved state that claims the intent but does not
     verify is neither completed nor abandoned. Abandoning still requires the
     saved checkpoint to be the witness head.

  M  The owner's refusal names its own window ("its latest answer in verbosity
     since it signed the previous verbosity crossing is 'no'"), not the
     organism's.

  H  HOUSEKEEPING (declaration). T57 expects the check that actually fires
     first; X10's set is {T22}. Every declared refusal now records the line
     traced to raise it.

FINDINGS CLOSED
  ChatGPT r6 F1  A stale object's ordinary save erased newer saved state. All
                 three schedules: sequential; during attest; interrupted commit
                 followed by a stale write -> O.
  ChatGPT r6 F2  A failure after the replace left memory behind disk -> I.
  Author  A1     Recovery completed from a saved file that does not load -> C.
                 Sealed 2026-10-19T12:34Z, before round 6.
  Author  A2     The owner's refusal text contradicted itself -> M.

LIMITS. R1-R29 as in v0.8.5, except:
  R30 (revised) Recovery completes an intent only from a saved state that
      verifies, and abandons one only if the saved checkpoint is the witness
      head. An edit made outside the protocol (writing the file directly) is not
      prevented. A rewind to the exact pre-install file looks the same as an
      install that never happened, and is abandoned.
  R31 (revised) Only install_checkpoint is transactional in memory. If another
      operation's save fails before landing, the object is ahead of its disk and
      its next save writes that state. Because of the generation check, no other
      object can write over it.
  R32 The organism lock is POSIX flock, like the owner lock (R26). Writers that
      bypass HumbleSeed._save are not serialized.
  R33 A stale object must reload, and its unsaved changes are lost. An answer
      given through a stale object reaches the owner's ledger, which is
      authoritative, but not the organism.
  R34 Every save re-reads the saved state to check its generation, a cost that
      grows with the trace (see also the apply-side replay, author A3).
  W's justification, corrected: answers given before the owner signed the
  previous crossing were already checked when that crossing was attested, so
  the window holds without assuming when the organism issued the reading.

Run the falsification harness:  python3 -I falsify_v0_8_6.py
"""

from __future__ import annotations

import base64
import contextlib
import copy
import fcntl
import functools
import hashlib
import json
import math
import os
import secrets
import threading
import time
import uuid
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


SCHEMA_VERSION = "0.8.6-candidate"

# GENESIS INPUTS ONLY. hatch() copies these into the constitution. After hatch
# the organism and the owner replay read policy from the attested
# constitution, never from these constants (K2, ChatGPT round 2 #2).
GENESIS_ALLOWED_FIELDS = {"verbosity", "formality", "curiosity"}
GENESIS_VALUE_RANGE = (0.0, 1.0)
GENESIS_READING_TTL_SECONDS = 7 * 24 * 3600.0     # R15: the owner's choice at hatch
GENESIS_CHARACTER = {"verbosity": 0.5, "formality": 0.5, "curiosity": 0.6}
GENESIS_DERIVATION = {
    "rule": ("destination = clamp(prior_value + label_to_delta[lead], value_range); "
             "a crossing is possible only if lead weight >= min_lead_weight"),
    "label_to_delta": {"preference": -0.25},
    "min_lead_weight": 0.60,
}

NON_AUTHORIZING_EVENTS = {"dwelling", "authorization_rejected", "checkpoint", "owner_answer", "reading_held"}

OWNER_ANSWERS = ("yes", "no", "unsure")

# Display text only. Carries no authority; nothing reads it except render_consequence.
CONSEQUENCE_FLAVOR = {
    ("verbosity", "down"): "I'll keep my answers shorter.",
    ("verbosity", "up"): "I'll give fuller answers.",
    ("formality", "down"): "I'll write more casually.",
    ("formality", "up"): "I'll write more formally.",
    ("curiosity", "down"): "I'll ask fewer questions.",
    ("curiosity", "up"): "I'll ask more questions.",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canonical_json(obj: Any) -> str:
    # allow_nan=False: a non-finite number can never be hashed, signed or saved.
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _refuse_constant(name: str):
    raise ValueError(f"non-finite constant {name} refused")


def _finite_float(text: str) -> float:
    v = float(text)
    if not math.isfinite(v):
        raise ValueError(f"non-finite constant {text} refused")
    return v


def _strict_loads(text: str) -> Any:
    """json.loads that refuses NaN, Infinity, -Infinity and overflowing literals."""
    return json.loads(text, parse_constant=_refuse_constant, parse_float=_finite_float)


def _sha256(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _fixed(t: float) -> str:
    return f"{t:.6f}"


def _chain_head(entries: List[Dict[str, Any]]) -> str:
    return entries[-1]["entry_hash"] if entries else "0" * 64


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_finite_number(v: Any) -> bool:
    return _is_number(v) and math.isfinite(float(v))


def _check_chain(trace: List[Dict[str, Any]]) -> str:
    """Return the chain head, or raise ValueError naming the first break."""
    prev = "0" * 64
    for i, entry in enumerate(trace):
        if entry.get("prev_hash") != prev:
            raise ValueError(f"Hash chain broken at index {i}: prev_hash mismatch")
        body = {k: v for k, v in entry.items() if k != "entry_hash"}
        if entry.get("entry_hash") != _sha256(_canonical_json(body)):
            raise ValueError(f"Hash chain broken at index {i}: entry_hash mismatch")
        prev = entry["entry_hash"]
    return prev


def _duration(seconds: float) -> str:
    if seconds % 86400 == 0:
        n = int(seconds // 86400)
        return f"{n} day" + ("" if n == 1 else "s")
    if seconds % 3600 == 0:
        n = int(seconds // 3600)
        return f"{n} hour" + ("" if n == 1 else "s")
    return f"{seconds:g} seconds"


def _durable_write(path: Path, text: str) -> None:
    """Atomic, fsynced replace. Nothing partial is ever visible at `path`."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    dfd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


class _OwnerLock:
    """Exclusive owner lock: POSIX flock across processes, reentrant within a
    thread, serialized across threads (v0.8.4, S)."""
    _registry: Dict[str, Dict[str, Any]] = {}
    _guard = threading.Lock()

    def __init__(self, path: Path | str):
        self.path = os.path.abspath(str(path))

    def __enter__(self):
        with _OwnerLock._guard:
            entry = _OwnerLock._registry.setdefault(
                self.path, {"rlock": threading.RLock(), "fd": None, "depth": 0})
        entry["rlock"].acquire()
        if entry["depth"] == 0:
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
            entry["fd"] = fd
        entry["depth"] += 1
        return self

    def __exit__(self, *exc) -> bool:
        entry = _OwnerLock._registry[self.path]
        entry["depth"] -= 1
        if entry["depth"] == 0:
            fcntl.flock(entry["fd"], fcntl.LOCK_UN)
            os.close(entry["fd"])
            entry["fd"] = None
        entry["rlock"].release()
        return False


def _owner_locked(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with _OwnerLock(self.lock_path):
            return method(self, *args, **kwargs)
    return wrapper


class IntegrityError(RuntimeError):
    """Persisted state failed a structural or attestation check."""


class RollbackDetected(RuntimeError):
    """External witness observed a sequence regression or fork."""


class StaleOrganism(RuntimeError):
    """v0.8.6: this organism object is not the saved state's latest reader or writer."""


class AttestationRefused(RuntimeError):
    """The owner tool refused to attest: the presented state is not the
    mechanical consequence of readings this owner signed (D4)."""


# ---------------------------------------------------------------------------
# Policy — read from the attested constitution (ChatGPT round 2 #2)
# ---------------------------------------------------------------------------

def policy_fields(constitution: Dict[str, Any]) -> Set[str]:
    return set(constitution["allowed_character_fields"])


def policy_range(constitution: Dict[str, Any]) -> Tuple[float, float]:
    lo, hi = constitution["value_range"]
    return float(lo), float(hi)


def policy_ttl(constitution: Dict[str, Any]) -> float:
    return float(constitution["reading_ttl_seconds"])


def validate_distribution(distribution: Any) -> Dict[str, float]:
    if not isinstance(distribution, dict) or not distribution:
        raise ValueError("Distribution must be a non-empty mapping")
    out = {}
    for k, v in distribution.items():
        if not isinstance(k, str) or not _is_finite_number(v) or float(v) < 0.0:
            raise ValueError(f"Distribution entry {k!r} must map a label to a finite non-negative number")
        out[k] = float(v)
    if abs(sum(out.values()) - 1.0) > 1e-6:
        raise ValueError("Distribution must sum to 1")
    return out


def parse_reading_json(raw: str) -> Dict[str, float]:
    """Parse an interpreter's (e.g. a model's) JSON reading. Refuses non-finite
    literals at parse time, then validates (ChatGPT round 2 #1)."""
    return validate_distribution(_strict_loads(raw))


def derive_destination(constitution: Dict[str, Any], distribution: Dict[str, float],
                       prior_value: float) -> Tuple[str, float, float]:
    """(lead, delta, destination) under the attested rule. Raises ValueError if
    the reading does not support a crossing. Shared by the organism and the
    owner replay (R14)."""
    der = constitution["derivation"]
    distribution = validate_distribution(distribution)
    lead = max(distribution, key=distribution.get)
    weight = float(distribution[lead])
    table = der["label_to_delta"]
    if lead not in table:
        raise ValueError(f"lead read {lead!r} has no sanctioned mapping")
    if weight < float(der["min_lead_weight"]):
        raise ValueError(f"lead weight {weight:.3f} below {der['min_lead_weight']}")
    delta = float(table[lead])
    lo, hi = policy_range(constitution)
    destination = min(hi, max(lo, float(prior_value) + delta))
    if not math.isfinite(destination):
        raise ValueError("derived destination is not finite")
    return lead, delta, destination


# ---------------------------------------------------------------------------
# Rendering — deterministic, display only (D2, D3)
# ---------------------------------------------------------------------------

def render_prompts(reading: Dict[str, Any], constitution: Dict[str, Any]) -> Dict[str, str]:
    """The two prompts for a pending reading. A pure function of the reading
    and the attested policy. It never consults the derivation rule, so nothing
    in it can say where the change would land (D3)."""
    cat = reading["category"]
    dist = reading["distribution"]
    lead = max(dist, key=dist.get).replace("_", " ")
    weights = " · ".join(
        f"{k.replace('_', ' ')} {v:.2f}"
        for k, v in sorted(dist.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    quote = reading["evidence"][-1] if reading["evidence"] else ""
    lo, hi = policy_range(constitution)
    first = (f" This would be the first change ever made to {cat}."
             if reading["first_commit"] else "")
    question = (f"I read “{quote}” as a {lead} about {cat} ({weights}). "
                f"Did I read you right? (yes / no / unsure)")
    authorization = (
        f"May I change my {cat} for you on the strength of this reading? "
        f"Only {cat} can change, only within {lo:.2f}–{hi:.2f}, and only by the rule "
        f"attested at my birth; it is {float(reading['prior_value']):.2f} now.{first} "
        f"This authorization lapses {_duration(policy_ttl(constitution))} after the reading was taken. "
        f"Signing says yes to this one reading; it does not choose where it lands."
    )
    return {"question": question, "authorization": authorization}


def render_consequence(record: Dict[str, Any]) -> str:
    """After the crossing: what changed, rendered from the MutationRecord alone (D3)."""
    cat = record["category"]
    prior = float(record["prior_value"])
    new = float(record["change"][cat])
    if new < prior:
        head = CONSEQUENCE_FLAVOR.get((cat, "down"), f"I'll lower my {cat}.")
    elif new > prior:
        head = CONSEQUENCE_FLAVOR.get((cat, "up"), f"I'll raise my {cat}.")
    else:
        head = (f"My {cat} was already at the edge of its range ({new:.2f}); "
                f"the reading was applied with no movement.")
    weight = float(record["distribution"].get(record["lead"], 0.0))
    first = f" This was the first change ever made to {cat}." if record["first_commit"] else ""
    return (f"{head} ({cat} {prior:.2f} → {new:.2f}; lead read: "
            f"{record['lead'].replace('_', ' ')} {weight:.2f}; rule step {float(record['delta']):+.2f}).{first}")


# ---------------------------------------------------------------------------
# Ruling 3: an answer is the owner's current position (shared by both sides)
# ---------------------------------------------------------------------------

def answer_position(to_reading: List[str], in_category_since: List[str]) -> Optional[str]:
    """Each list holds answers in the order given. Only the latest counts.
    Returns a reason to hold, or None."""
    if to_reading and to_reading[-1] == "no":
        return "the owner's latest answer to this reading is 'no'"
    if in_category_since and in_category_since[-1] == "no":
        return "the owner's latest answer in this category since the reading was taken is 'no'"
    return None


def _answers_in_window(reading: Dict[str, Any], events: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    answers = [e for e in events if e.get("event") == "owner_answer"]
    return ([e.get("answer") for e in answers if e.get("proposal_id") == reading["proposal_id"]],
            [e.get("answer") for e in answers if e.get("category") == reading["category"]])


# ---------------------------------------------------------------------------
# D1 default reader — contradiction-only
# ---------------------------------------------------------------------------

def contradiction_only_reader(reading: Dict[str, Any], terrain: List[Dict[str, Any]],
                              events_since: List[Dict[str, Any]]) -> Optional[str]:
    """Hold only on an explicit contradiction: the owner's current position,
    from the answers given since the reading was taken, is "no"."""
    held = answer_position(*_answers_in_window(reading, events_since))
    return None if held is None else f"owner's position: {held}"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BirthRecord:
    organism_id: str
    public_key_b64: str
    genesis_hash: str
    created_at: float
    constitution_hash: str


@dataclass
class PreTrace:
    category: str
    distribution: Dict[str, float]
    evidence: List[str]
    salience: float
    created_at: float
    source: str = "interaction"          # "interaction" | "owner_answer" (D2)
    answer: Optional[str] = None         # owner answers only
    about: Optional[str] = None          # proposal_id the answer refers to


@dataclass
class PendingProposal:
    """A pending READING. It names no destination (K2)."""
    proposal_id: str
    organism_id: str
    category: str
    distribution: Dict[str, float]
    distribution_root: str
    evidence: List[str]
    evidence_root: str
    first_commit: bool
    prior_value: float            # K1/K2: the value the reading was taken from
    category_sequence: int        # K1: per-category staleness
    constitution_root: str        # K2: pins the derivation rule and policy
    issued_trace_head: str        # provenance; D1 reads events after it
    issued_mutation_sequence: int # provenance only; never a rejection condition
    nonce: str
    timestamp: float
    expires_at: float
    payload_to_sign: str
    payload_hash: str


@dataclass
class MutationRecord:
    proposal_id: str
    category: str
    lead: str
    delta: float
    prior_value: float
    change: Dict[str, float]      # derived at apply time, recorded here
    distribution: Dict[str, float]
    evidence: List[str]
    first_commit: bool
    category_sequence: int
    mutation_sequence: int
    authorized_at: float
    signature_b64: str
    signed_payload: str           # D4: the exact reading the owner signed
    prior_character_snapshot: Dict[str, float]
    unverified_annotation: str = ""   # written by the organism; never the owner's words (v0.8.4, P)


_RECORD_FIELDS = {f.name for f in fields(MutationRecord)}


@dataclass
class Checkpoint:
    """Owner-signed attestation over a specific organism state."""
    organism_id: str
    sequence: int
    prev_checkpoint_hash: str
    birth_root: str
    constitution_root: str
    gates_root: str
    character_root: str
    consumed_root: str
    trace_head: str
    attested_trace_len: int
    mutation_sequence: int
    timestamp: float


# ---------------------------------------------------------------------------
# The organism
#
# Contains NO signing primitive. Verification only.
# ---------------------------------------------------------------------------

Reader = Callable[[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]], Optional[str]]


class HumbleSeed:

    def __init__(self, data_dir: Path | str = "./seed_data_v082c",
                 reader: Optional[Reader] = contradiction_only_reader):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reader = reader              # D1: can only hold (R12)
        self.clock: Callable[[], float] = time.time

        self.organism_id: Optional[str] = None
        self.public_key: Optional[Ed25519PublicKey] = None
        self.birth: Optional[BirthRecord] = None
        self.constitution: Dict[str, Any] = {}
        self.character: Dict[str, float] = {}
        self.basin: List[PreTrace] = []
        self.pending: Dict[str, PendingProposal] = {}
        self.consumed: Set[str] = set()
        self.trace: List[Dict[str, Any]] = []
        self.category_sequence: Dict[str, int] = {}
        self.mutation_sequence: int = 0
        self.checkpoint: Optional[Checkpoint] = None
        self.checkpoint_sig: Optional[str] = None
        self._trace_head: str = "0" * 64
        self._generation: Optional[int] = None   # v0.8.6: the saved generation this object last saw

    # ------------------------------------------------------------------
    # Roots
    # ------------------------------------------------------------------

    def _character_root(self) -> str:
        return _sha256(_canonical_json(self.character))

    def _consumed_root(self) -> str:
        return _sha256(_canonical_json(sorted(self.consumed)))

    def _birth_root(self) -> str:
        return _sha256(_canonical_json(asdict(self.birth) if self.birth else {}))

    def _constitution_root(self) -> str:
        return _sha256(_canonical_json(self.constitution))

    def _gates_root(self) -> str:
        return _sha256(_canonical_json(self.category_sequence))

    # ------------------------------------------------------------------
    # K2: the derivation rule and policy come from the attested constitution
    # ------------------------------------------------------------------

    def _allowed_fields(self) -> Set[str]:
        return policy_fields(self.constitution)

    def derive(self, category: str, distribution: Dict[str, float],
               prior_value: float) -> Tuple[str, float, float]:
        """Return (lead, delta, destination). Raises ValueError if the reading
        does not support a crossing under the attested rule."""
        return derive_destination(self.constitution, distribution, prior_value)

    # ------------------------------------------------------------------
    # Birth
    # ------------------------------------------------------------------

    def hatch(self, reading_ttl_seconds: float = GENESIS_READING_TTL_SECONDS
              ) -> Tuple[str, str, Checkpoint]:
        """Returns (organism_id, owner_private_pem, genesis checkpoint request).

        The organism is NOT loadable until the owner attests (OwnerTool.attest).
        reading_ttl_seconds is the owner's choice (R15) and is attested.
        """
        if self.organism_id is not None:
            raise RuntimeError("This seed has already hatched.")
        if not _is_finite_number(reading_ttl_seconds) or float(reading_ttl_seconds) <= 0.0:
            raise ValueError("reading_ttl_seconds must be a finite positive number")

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii")
        public_b64 = base64.urlsafe_b64encode(
            public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ).decode("ascii")

        organism_id = str(uuid.uuid4())
        created_at = self.clock()

        constitution = {
            "schema_version": SCHEMA_VERSION,
            "rule": "The organism can propose its own growth but cannot authorize its own growth.",
            "theorem": "External Authorization is Necessary (McMurray 2026)",
            "invariants": [
                "No character change on a misread",
                "When unreadable, ask rather than guess",
                "Private authorization material never stored by organism",
                "The signature binds the reading: its evidence, distribution, prior value, "
                "category sequence and constitution; it never names a destination",
                "The destination is derived at apply time from signed inputs and the attested derivation rule",
                "A pending reading goes stale only when its own category advances",
                "A re-read at apply time may only hold; it never re-proposes, re-derives or crosses",
                "The owner's answer to a question is evidence, never authorization",
                "Nothing shown before signing names where a change would land",
                "The owner attests only a state that replays from signed readings",
                "Readings, policy and character values are finite numbers",
                "Replay and same-category reordering of authorizations forbidden",
                "Mutation values are numbers in range, never interpretation labels",
                "A change may only touch the category it was read under",
                "The first commitment in any category is visibly flagged to the owner",
                "Character never advances without an owner-signed attestation of the result",
                "The organism cannot detect its own rollback; an external witness must",
                "Birth, constitution, and category sequences are owner-attested",
                "First-commit flags are strict Booleans derived from live state",
                "The witness distinguishes a recorded current head from a candidate successor",
            ],
            "allowed_character_fields": sorted(GENESIS_ALLOWED_FIELDS),
            "value_range": [float(GENESIS_VALUE_RANGE[0]), float(GENESIS_VALUE_RANGE[1])],
            "reading_ttl_seconds": float(reading_ttl_seconds),
            "genesis_character": dict(GENESIS_CHARACTER),
            "derivation": copy.deepcopy(GENESIS_DERIVATION),
        }
        constitution_hash = _sha256(_canonical_json(constitution))
        genesis_hash = self._derive_genesis(
            organism_id, public_b64, created_at, constitution_hash
        )

        self.organism_id = organism_id
        self.public_key = public_key
        self.constitution = constitution
        self._verify_policy()
        self.birth = BirthRecord(
            organism_id=organism_id,
            public_key_b64=public_b64,
            genesis_hash=genesis_hash,
            created_at=created_at,
            constitution_hash=constitution_hash,
        )
        self.character = dict(constitution["genesis_character"])
        self.category_sequence = {c: 0 for c in sorted(self._allowed_fields())}
        self._append_trace({
            "event": "birth",
            "organism_id": organism_id,
            "genesis_hash": genesis_hash,
            "constitution_hash": constitution_hash,
            "timestamp": created_at,
        })

        del private_key
        self._save()
        return organism_id, private_pem, self.checkpoint_request()

    @staticmethod
    def _derive_genesis(
        organism_id: str, public_b64: str, created_at: float, constitution_hash: str
    ) -> str:
        return _sha256("|".join(
            [organism_id, public_b64, _fixed(created_at), constitution_hash]
        ))

    # ------------------------------------------------------------------
    # Trace
    # ------------------------------------------------------------------

    def _append_trace(self, entry: Dict[str, Any]) -> None:
        entry = dict(entry)
        entry["prev_hash"] = self._trace_head
        entry["entry_hash"] = _sha256(_canonical_json(entry))
        self.trace.append(entry)
        self._trace_head = entry["entry_hash"]

    def _verify_chain(self) -> None:
        if not self.trace:
            if self._trace_head != "0" * 64:
                raise IntegrityError("Empty trace but non-genesis trace_head")
            return
        try:
            head = _check_chain(self.trace)
        except ValueError as why:
            raise IntegrityError(str(why))
        if head != self._trace_head:
            raise IntegrityError("trace_head does not match final entry_hash")

    def _verify_birth_trace(self) -> None:
        """Bind the active birth record to the unique genesis trace event."""
        if self.birth is None:
            raise IntegrityError("No birth record")
        if not self.trace:
            raise IntegrityError("Birth trace is missing")

        birth_events = [
            (i, entry) for i, entry in enumerate(self.trace)
            if entry.get("event") == "birth"
        ]
        if len(birth_events) != 1 or birth_events[0][0] != 0:
            raise IntegrityError(
                "Trace must contain exactly one birth event at index zero"
            )

        event = birth_events[0][1]
        expected = {
            "organism_id": self.organism_id,
            "genesis_hash": self.birth.genesis_hash,
            "constitution_hash": self.birth.constitution_hash,
            "timestamp": self.birth.created_at,
        }
        for field_name, expected_value in expected.items():
            if event.get(field_name) != expected_value:
                raise IntegrityError(
                    f"Birth trace {field_name} does not match active birth record"
                )

    # ------------------------------------------------------------------
    # Checkpoints — the external authority
    # ------------------------------------------------------------------

    @staticmethod
    def checkpoint_payload(cp: Checkpoint) -> str:
        return _canonical_json({
            "schema_version": SCHEMA_VERSION,
            "kind": "checkpoint",
            **{k: (_fixed(v) if k == "timestamp" else v) for k, v in asdict(cp).items()},
        })

    def checkpoint_request(self) -> Checkpoint:
        """Describe the CURRENT state for the owner to attest."""
        if self.birth is None:
            raise RuntimeError("Organism has not hatched.")
        prev_hash = (
            _sha256(self.checkpoint_payload(self.checkpoint))
            if self.checkpoint else "0" * 64
        )
        return Checkpoint(
            organism_id=self.organism_id or "",
            sequence=(self.checkpoint.sequence + 1) if self.checkpoint else 0,
            prev_checkpoint_hash=prev_hash,
            birth_root=self._birth_root(),
            constitution_root=self._constitution_root(),
            gates_root=self._gates_root(),
            character_root=self._character_root(),
            consumed_root=self._consumed_root(),
            trace_head=self._trace_head,
            attested_trace_len=len(self.trace),
            mutation_sequence=self.mutation_sequence,
            timestamp=self.clock(),
        )

    def install_checkpoint(self, cp: Checkpoint, signature_b64: str) -> bool:
        """Accept an owner-signed attestation of the current state."""
        if self.public_key is None:
            raise RuntimeError("Organism has not hatched.")
        try:
            self.public_key.verify(
                base64.urlsafe_b64decode(signature_b64),
                self.checkpoint_payload(cp).encode("utf-8"),
            )
        except Exception:
            return False

        expected = self.checkpoint_request()
        for f in (
            "organism_id", "sequence", "prev_checkpoint_hash", "birth_root",
            "constitution_root", "gates_root", "character_root", "consumed_root",
            "trace_head", "attested_trace_len", "mutation_sequence",
        ):
            if getattr(cp, f) != getattr(expected, f):
                return False

        # v0.8.5 (ChatGPT round 5, F2): nothing changes in memory unless the save succeeds.
        kept = (self.checkpoint, self.checkpoint_sig, len(self.trace), self._trace_head)
        self.checkpoint = cp
        self.checkpoint_sig = signature_b64
        self._append_trace({
            "event": "checkpoint",
            "sequence": cp.sequence,
            "birth_root": cp.birth_root,
            "constitution_root": cp.constitution_root,
            "gates_root": cp.gates_root,
            "character_root": cp.character_root,
            "timestamp": cp.timestamp,
        })
        gen_before = self._generation
        try:
            self._save()
        except BaseException:
            if self._generation == gen_before:     # v0.8.6 (ChatGPT r6 F2): roll back only if nothing landed
                self.checkpoint, self.checkpoint_sig, n, self._trace_head = kept   # [INSTALL-ROLLBACK]
                del self.trace[n:]
            raise
        return True

    def _verify_attestation(self) -> None:
        """State is only trusted as far as the owner signed it."""
        if self.checkpoint is None or self.checkpoint_sig is None:
            raise IntegrityError("No owner checkpoint — state is unattested")

        try:
            self.public_key.verify(
                base64.urlsafe_b64decode(self.checkpoint_sig),
                self.checkpoint_payload(self.checkpoint).encode("utf-8"),
            )
        except Exception:
            raise IntegrityError("Checkpoint signature invalid — state is not owner-attested")

        cp = self.checkpoint
        if cp.organism_id != self.organism_id:
            raise IntegrityError("Checkpoint is for a different organism")
        if cp.birth_root != self._birth_root():
            raise IntegrityError("Birth record does not match the attested checkpoint")
        if cp.constitution_root != self._constitution_root():
            raise IntegrityError("Constitution does not match the attested checkpoint")
        if cp.gates_root != self._gates_root():
            raise IntegrityError("Category sequences do not match the attested checkpoint")
        if cp.character_root != self._character_root():
            raise IntegrityError(
                "Character does not match the attested checkpoint — "
                "unattested mutation or forged character"
            )
        if cp.consumed_root != self._consumed_root():
            raise IntegrityError("Consumed ledger does not match the attested checkpoint")
        if cp.mutation_sequence != self.mutation_sequence:
            raise IntegrityError("Mutation sequence does not match the attested checkpoint")
        if cp.attested_trace_len > len(self.trace):
            raise IntegrityError("Trace is shorter than the attested checkpoint — truncation")
        if cp.attested_trace_len < 1:
            raise IntegrityError("Checkpoint does not attest the birth event")

        attested = self.trace[:cp.attested_trace_len]
        if _chain_head(attested) != cp.trace_head:
            raise IntegrityError("Attested trace prefix does not match checkpoint trace_head")

        for i, entry in enumerate(self.trace[cp.attested_trace_len:],
                                  start=cp.attested_trace_len):
            if entry.get("event") not in NON_AUTHORIZING_EVENTS:
                raise IntegrityError(
                    f"Unattested authorizing event at trace index {i}: "
                    f"{entry.get('event')} — owner checkpoint required"
                )

    # ------------------------------------------------------------------
    # Seal + persistence
    # ------------------------------------------------------------------

    def _compute_seal(self) -> str:
        """Integrity digest over every mutable region. Not an authenticity
        control on its own; authenticity comes from the owner checkpoint."""
        return _sha256(_canonical_json({
            "schema_version": SCHEMA_VERSION,
            "birth_root": self._birth_root(),
            "constitution_root": self._constitution_root(),
            "character_root": self._character_root(),
            "basin_root": _sha256(_canonical_json([asdict(p) for p in self.basin])),
            "pending_root": _sha256(_canonical_json(
                {pid: asdict(p) for pid, p in self.pending.items()}
            )),
            "consumed_root": self._consumed_root(),
            "gates_root": self._gates_root(),
            "mutation_sequence": self.mutation_sequence,
            "trace_head": self._trace_head,
        }))

    def _state_path(self) -> Path:
        return self.data_dir / "organism_state.json"

    def _organism_lock(self):
        """v0.8.6: the organism's own lock file (POSIX flock, reentrant within a thread)."""
        return _OwnerLock(self.data_dir / "organism.lock")      # [ORGANISM-LOCK]

    def _saved_generation(self) -> Optional[int]:
        path = self._state_path()
        if not path.exists():
            return None
        try:
            return _strict_loads(path.read_text(encoding="utf-8")).get("generation")
        except (ValueError, AttributeError) as why:
            raise StaleOrganism(f"the saved state is unreadable ({type(why).__name__}); refusing to write over it")

    def _require_current(self) -> None:
        """v0.8.6 (ChatGPT r6 F1): refuse to act on a stale object."""
        with self._organism_lock():
            saved = self._saved_generation()
            if saved != self._generation:
                raise StaleOrganism(f"stale organism object: the saved state is at generation {saved}, "
                                    f"this object last saw {self._generation}; reload it")

    def _save(self) -> None:
        if self.organism_id is None or self.birth is None:
            return
        new_gen = 0 if self._generation is None else self._generation + 1
        state = {
            "schema_version": SCHEMA_VERSION,
            "generation": new_gen,
            "organism_id": self.organism_id,
            "birth": asdict(self.birth),
            "constitution": self.constitution,
            "character": self.character,
            "basin": [asdict(p) for p in self.basin],
            "pending": {pid: asdict(p) for pid, p in self.pending.items()},
            "consumed": sorted(self.consumed),
            "trace": self.trace,
            "category_sequence": self.category_sequence,
            "mutation_sequence": self.mutation_sequence,
            "trace_head": self._trace_head,
            "checkpoint": asdict(self.checkpoint) if self.checkpoint else None,
            "checkpoint_sig": self.checkpoint_sig,
            "state_seal": self._compute_seal(),
        }
        text = _canonical_json(state)          # raises before anything is written
        with self._organism_lock():            # v0.8.6 (ChatGPT r6 F1): one writer, and only a current one
            saved = self._saved_generation()
            if saved != self._generation:                    # [SAVE-CAS]
                raise StaleOrganism(f"stale organism object: the saved state is at generation {saved}, "
                                    f"this object last saw {self._generation}; reload it")
            try:
                _durable_write(self._state_path(), text)
            except BaseException:
                # v0.8.6 (ChatGPT r6 F2): the replace may already have landed; record what did.
                try:
                    if self._saved_generation() == new_gen:
                        self._generation = new_gen               # [SAVE-LANDED]
                except StaleOrganism:
                    pass
                raise
            self._generation = new_gen

    def load(self) -> None:
        path = self._state_path()
        if not path.exists():
            raise FileNotFoundError("No saved organism state found.")
        try:
            data = _strict_loads(path.read_text(encoding="utf-8"))
        except ValueError as why:
            raise IntegrityError(f"State file refused: {why}")

        if data.get("schema_version") != SCHEMA_VERSION:
            raise IntegrityError(
                f"Schema version mismatch: file={data.get('schema_version')} "
                f"expected={SCHEMA_VERSION}"
            )

        self.organism_id = data["organism_id"]
        self.birth = BirthRecord(**data["birth"])
        self.public_key = Ed25519PublicKey.from_public_bytes(
            base64.urlsafe_b64decode(self.birth.public_key_b64)
        )
        self.constitution = data.get("constitution", {})
        self.character = data["character"]
        self.basin = [PreTrace(**p) for p in data["basin"]]
        self.pending = {pid: PendingProposal(**p) for pid, p in data.get("pending", {}).items()}
        self.consumed = set(data.get("consumed", []))
        self.trace = data["trace"]
        self.category_sequence = data.get("category_sequence", {})
        self.mutation_sequence = data.get("mutation_sequence", 0)
        self._trace_head = data.get("trace_head", "0" * 64)
        cp = data.get("checkpoint")
        self.checkpoint = Checkpoint(**cp) if cp else None
        self.checkpoint_sig = data.get("checkpoint_sig")
        g = data.get("generation")
        if isinstance(g, bool) or not isinstance(g, int) or g < 0:
            raise IntegrityError("Saved generation is not a non-negative integer")
        self._generation = g

        self.verify(expected_seal=data.get("state_seal"))

    def _verify_policy(self) -> None:
        """Structure of the attested policy and derivation rule."""
        c = self.constitution
        fields = c.get("allowed_character_fields")
        if (not isinstance(fields, list) or not fields
                or not all(isinstance(f, str) for f in fields) or len(set(fields)) != len(fields)):
            raise IntegrityError("Constitution allowed_character_fields must be a list of unique names")
        vr = c.get("value_range")
        if (not isinstance(vr, list) or len(vr) != 2
                or not all(_is_finite_number(x) for x in vr) or not float(vr[0]) < float(vr[1])):
            raise IntegrityError("Constitution value_range must be two finite numbers, low < high")
        ttl = c.get("reading_ttl_seconds")
        if not _is_finite_number(ttl) or float(ttl) <= 0.0:
            raise IntegrityError("Constitution reading_ttl_seconds must be a finite positive number")
        gc = c.get("genesis_character")
        if not isinstance(gc, dict) or set(gc) != set(fields):
            raise IntegrityError("Constitution genesis_character must cover exactly the allowed fields")
        for k, v in gc.items():
            if not _is_finite_number(v) or not (float(vr[0]) <= float(v) <= float(vr[1])):
                raise IntegrityError(f"Genesis character {k} is not a finite number in range")

        der = c.get("derivation")
        if not isinstance(der, dict):
            raise IntegrityError("Constitution carries no derivation rule")
        table = der.get("label_to_delta")
        if not isinstance(table, dict) or not table:
            raise IntegrityError("Derivation rule has no label_to_delta table")
        for k, v in table.items():
            if not isinstance(k, str) or not _is_finite_number(v):
                raise IntegrityError(f"Derivation entry {k!r} is not label -> finite number")
        w = der.get("min_lead_weight")
        if not _is_finite_number(w) or not (0.0 < float(w) <= 1.0):
            raise IntegrityError("Derivation min_lead_weight must be a number in (0, 1]")

    def verify(self, expected_seal: Optional[str] = None) -> bool:
        if self.birth is None:
            raise IntegrityError("No birth record")

        if not self.constitution:
            raise IntegrityError("Constitution missing from state — cannot verify birth binding")
        if _sha256(_canonical_json(self.constitution)) != self.birth.constitution_hash:
            raise IntegrityError(
                "Constitution does not match birth commitment — organism is not "
                "running under the constitution it was born with"
            )
        if self._derive_genesis(
            self.birth.organism_id, self.birth.public_key_b64,
            self.birth.created_at, self.birth.constitution_hash,
        ) != self.birth.genesis_hash:
            raise IntegrityError("Genesis hash does not re-derive from birth record")
        if self.birth.organism_id != self.organism_id:
            raise IntegrityError("organism_id does not match birth record")
        self._verify_policy()

        allowed = self._allowed_fields()
        if set(self.category_sequence) != allowed:
            raise IntegrityError("Category sequence set does not match allowed character fields")
        for category, n in self.category_sequence.items():
            if isinstance(n, bool) or not isinstance(n, int) or n < 0:
                raise IntegrityError(f"Category sequence for {category} is not a non-negative int")
        if sum(self.category_sequence.values()) != self.mutation_sequence:
            raise IntegrityError("Category sequences do not sum to the mutation sequence")

        if set(self.character) != allowed:
            raise IntegrityError("Character field set does not match allowed character fields")
        lo, hi = policy_range(self.constitution)
        for k, v in self.character.items():
            if not _is_finite_number(v):
                raise IntegrityError(f"Character field {k} is not a finite number")
            if not (lo <= float(v) <= hi):
                raise IntegrityError(f"Character field {k} out of range: {v}")

        self._verify_chain()
        self._verify_birth_trace()

        if expected_seal is not None and expected_seal != self._compute_seal():
            raise IntegrityError("State seal mismatch — corruption or rewrite of a sealed region")

        self._verify_attestation()
        return True

    # ------------------------------------------------------------------
    # Interpretation + basin
    # ------------------------------------------------------------------

    def interpret(self, event: str, transcript: str) -> Dict[str, float]:
        """R3: keyword stub. A model-backed interpreter should return
        parse_reading_json(model_output)."""
        reads = {"preference": 0.0, "confound": 0.0, "unmodeled_cause": 0.0}
        lower = transcript.lower()
        if "sorry" in lower or "door" in lower or "interrupt" in lower:
            reads.update(confound=0.72, preference=0.18, unmodeled_cause=0.10)
        elif "always" in lower or "prefer" in lower:
            reads.update(preference=0.68, confound=0.12, unmodeled_cause=0.20)
        else:
            reads.update(preference=0.35, confound=0.25, unmodeled_cause=0.40)
        total = sum(reads.values())
        return {k: v / total for k, v in reads.items()}

    def _dwell(self, category: str, reason: str) -> None:
        self._append_trace({
            "event": "dwelling",
            "category": category,
            "reason": reason,
            "timestamp": self.clock(),
        })
        self._save()

    def dwell_or_propose(self, category: str, event: str, transcript: str) -> dict:
        if category not in self._allowed_fields():
            raise ValueError(f"Unknown character category: {category}")

        try:
            dist = validate_distribution(self.interpret(event, transcript))
        except ValueError as why:
            # Unreadable: hold, do not guess (ChatGPT round 2 #1).
            self._dwell(category, f"unreadable: {why}")
            return {
                "status": "dwelling",
                "unreadable": True,
                "message": "The reading could not be read. Holding; nothing deposited.",
            }

        lead = max(dist, key=dist.get)
        self.basin.append(PreTrace(
            category=category, distribution=dist, evidence=[transcript],
            salience=dist[lead], created_at=self.clock(),
        ))

        try:
            self.derive(category, dist, float(self.character[category]))
        except ValueError as why:
            self._dwell(category, str(why))
            return {
                "status": "dwelling",
                "distribution": dist,
                "message": "Holding in basin. Owner authorization required for permanent change.",
            }

        proposal = self._issue_pending_proposal(
            category=category, distribution=dist, evidence=[transcript],
        )
        prompts = render_prompts(asdict(proposal), self.constitution)
        return {
            "status": "proposal",
            "proposal_id": proposal.proposal_id,
            "payload_to_sign": proposal.payload_to_sign,
            "first_commit": proposal.first_commit,
            "question": prompts["question"],                  # D2: answered as evidence
            "authorization_prompt": prompts["authorization"],  # D2: answered by signing
            "message": (
                "FIRST COMMITMENT in this category — owner should review with care."
                if proposal.first_commit else
                "Reading issued and pending. Requires valid owner signature to cross."
            ),
        }

    # ------------------------------------------------------------------
    # D2: the owner's answer is evidence
    # ------------------------------------------------------------------

    def record_owner_answer(self, proposal_id: str, answer: str, text: str = "") -> dict:
        """Record the owner's answer to a reading's question. Evidence only: it
        is deposited in the basin, never authorizes, never alters the reading.
        Owners answer through OwnerTool.answer, which also keeps its own record."""
        if proposal_id not in self.pending:
            raise ValueError("No pending reading with that id")
        if answer not in OWNER_ANSWERS:
            raise ValueError(f"Answer must be one of {OWNER_ANSWERS}")
        p = self.pending[proposal_id]
        now = self.clock()
        self._append_trace({
            "event": "owner_answer",
            "proposal_id": proposal_id,
            "category": p.category,
            "answer": answer,
            "text": text,
            "timestamp": now,
        })
        self.basin.append(PreTrace(category=p.category, distribution={}, evidence=[text or answer], salience=1.0, created_at=now, source="owner_answer", answer=answer, about=proposal_id))
        self._save()
        return {"status": "recorded", "authorizes": False,
                "message": "Recorded as evidence. An answer does not authorize a change."}

    # ------------------------------------------------------------------
    # Reading issuance (K1 + K2)
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_distribution(distribution: Dict[str, Any]) -> Dict[str, float]:
        return validate_distribution(distribution)

    def _reading_payload(self, p: PendingProposal) -> str:
        """Re-derived from the fields that will actually be read at apply time.
        Names no destination (K2)."""
        return _canonical_json({
            "schema_version": SCHEMA_VERSION,
            "kind": "reading_authorization",
            "organism_id": p.organism_id,
            "proposal_id": p.proposal_id,
            "category": p.category,
            "evidence_root": _sha256(_canonical_json(p.evidence)),
            "distribution_root": _sha256(_canonical_json(p.distribution)),
            "first_commit": p.first_commit,
            "prior_value": p.prior_value,
            "category_sequence": p.category_sequence,
            "constitution_root": p.constitution_root,
            "issued_trace_head": p.issued_trace_head,
            "issued_mutation_sequence": p.issued_mutation_sequence,
            "nonce": p.nonce,
            "timestamp": _fixed(p.timestamp),
            "expires_at": _fixed(p.expires_at),
        })

    def _issue_pending_proposal(
        self,
        category: str,
        distribution: Dict[str, float],
        evidence: List[str],
    ) -> PendingProposal:
        if category not in self._allowed_fields():
            raise ValueError(f"Disallowed mutation category: {category}")
        distribution = validate_distribution(distribution)
        prior_value = float(self.character[category])
        self.derive(category, distribution, prior_value)   # must support a crossing

        seq = self.category_sequence[category]
        first_commit = (seq == 0)          # derived; no caller override exists

        timestamp = self.clock()
        p = PendingProposal(
            proposal_id=str(uuid.uuid4()),
            organism_id=self.organism_id,
            category=category,
            distribution=distribution,
            distribution_root=_sha256(_canonical_json(distribution)),
            evidence=list(evidence),
            evidence_root=_sha256(_canonical_json(list(evidence))),
            first_commit=first_commit,
            prior_value=prior_value,
            category_sequence=seq,
            constitution_root=self._constitution_root(),
            issued_trace_head=self._trace_head,
            issued_mutation_sequence=self.mutation_sequence,
            nonce=secrets.token_hex(16),
            timestamp=timestamp,
            expires_at=timestamp + policy_ttl(self.constitution),
            payload_to_sign="",
            payload_hash="",
        )
        p.payload_to_sign = self._reading_payload(p)
        p.payload_hash = _sha256(p.payload_to_sign)
        self.pending[p.proposal_id] = p
        self._save()
        return p

    # ------------------------------------------------------------------
    # D1: re-read at apply time — may only hold
    # ------------------------------------------------------------------

    def _events_since(self, p: PendingProposal) -> List[Dict[str, Any]]:
        idx = next((i for i, e in enumerate(self.trace)
                    if e.get("entry_hash") == p.issued_trace_head), None)
        return list(self.trace) if idx is None else self.trace[idx + 1:]

    def _consult_reader(self, p: PendingProposal) -> Optional[str]:
        """None = no objection. A string = hold. Fail-closed to hold."""
        if self.reader is None:
            return None
        reading = copy.deepcopy(asdict(p))
        terrain = copy.deepcopy([asdict(q) for q in self.basin])
        events_since = copy.deepcopy(self._events_since(p))
        try:
            verdict = self.reader(reading, terrain, events_since)
        except Exception as why:
            return f"reader failed ({type(why).__name__}: {why})"
        if verdict is None:
            return None
        if isinstance(verdict, str) and verdict.strip():
            return verdict
        return f"reader returned {type(verdict).__name__}, not a reason or None"

    # ------------------------------------------------------------------
    # External authorization — verify only
    # ------------------------------------------------------------------

    def authorize_and_apply(
        self, proposal_id: str, signature_b64: str, annotation: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        On success returns {"status": "applied", "record", "consequence"}. The
        owner must then attest (OwnerTool.attest builds a fresh checkpoint
        request when it signs) before the state will load again.
        Returns None if the reading was rejected or held; the last trace
        event says which ("authorization_rejected" or "reading_held").
        """
        if self.public_key is None or self.organism_id is None:
            raise RuntimeError("Organism has not hatched.")

        if proposal_id not in self.pending:
            self._reject(proposal_id, "unknown or already-consumed proposal_id")
            return None

        p = self.pending[proposal_id]
        consume_key = f"{p.proposal_id}|{p.nonce}"

        if consume_key in self.consumed:
            self._reject(proposal_id, "replay of consumed proposal/nonce")
            return None
        if p.organism_id != self.organism_id:
            self._reject(proposal_id, "wrong organism_id")
            return None
        if p.category not in self._allowed_fields():
            self._reject(proposal_id, f"disallowed category {p.category}")
            return None
        now = self.clock()                 # v0.8.5: one clock reading, for expiry and for the record
        if now > p.expires_at:
            self._reject(proposal_id, "proposal expired")
            return None

        # K1: staleness is per category.
        current_seq = self.category_sequence[p.category]
        if p.category_sequence != current_seq:
            self._reject(proposal_id, "stale reading: this category has advanced since issuance")
            return None
        if float(p.prior_value) != float(self.character[p.category]):
            self._reject(proposal_id, "stale reading: category value differs from the value read")
            return None
        # [K1-ANCHOR] non-authorizing events and other categories' commits do not expire a reading.

        # Truthful first commitment: strict Boolean, derived from live state.
        expected_first_commit = (current_seq == 0)
        if not isinstance(p.first_commit, bool) or p.first_commit != expected_first_commit:
            self._reject(proposal_id, "first-commit mismatch: signed reading does not match live gate")
            return None

        # K2: the derivation rule and policy the owner signed under must still hold.
        if p.constitution_root != self._constitution_root():
            self._reject(proposal_id, "derivation rule changed since the reading was signed")
            return None

        # Evidence and distribution are re-hashed, so post-signature
        # substitution changes the payload and breaks the signature.
        recomputed = self._reading_payload(p)
        if recomputed != p.payload_to_sign:
            self._reject(proposal_id, "envelope inconsistency (evidence, distribution, or reading altered)")
            return None

        try:
            self.public_key.verify(
                base64.urlsafe_b64decode(signature_b64), recomputed.encode("utf-8")
            )
        except InvalidSignature:
            self._reject(proposal_id, "invalid signature")
            return None
        except Exception:
            self._reject(proposal_id, "signature verification error")
            return None

        # K2: the destination is derived here, from signed inputs only.
        try:
            lead, delta, destination = self.derive(p.category, p.distribution, p.prior_value)
        except (ValueError, KeyError) as why:
            self._reject(proposal_id, f"reading does not support a crossing: {why}")
            return None

        # D1: a fresh look at what arrived since the reading was taken. It may
        # only hold. The destination above is not recomputed, whatever it says.
        veto = self._consult_reader(p)
        if veto is not None:
            self._append_trace({
                "event": "reading_held",
                "proposal_id": proposal_id,
                "category": p.category,
                "reason": veto,
                "timestamp": self.clock(),
            })
            # [D1-ANCHOR] a hold never re-proposes and never re-derives.
            self._save()
            return None

        # v0.8.5: the record is built before anything changes, so it can be checked first.
        prior = dict(self.character)
        record = MutationRecord(
            proposal_id=p.proposal_id, category=p.category, lead=lead, delta=delta,
            prior_value=p.prior_value, change={p.category: float(destination)},
            distribution=p.distribution, evidence=p.evidence,
            first_commit=p.first_commit,
            category_sequence=current_seq + 1,
            mutation_sequence=self.mutation_sequence + 1,
            authorized_at=now, signature_b64=signature_b64,
            signed_payload=recomputed,
            prior_character_snapshot=prior, unverified_annotation=annotation,
        )
        entry = {
            "event": "authorized_mutation",
            "record": asdict(record),
            "timestamp": record.authorized_at,
        }
        # v0.8.5 (ChatGPT round 5, F4): apply refuses anything the owner's replay would
        # refuse in this crossing, before any state changes. Same function, same checks.
        apply_refusal = self._replay_refusal(entry)
        if apply_refusal is not None:                        # [APPLY=REPLAY]
            self._reject(proposal_id, f"replay would refuse this crossing: {apply_refusal}")
            return None

        self.character[p.category] = float(destination)
        self.category_sequence[p.category] = current_seq + 1
        self.consumed.add(consume_key)
        self.mutation_sequence += 1
        del self.pending[proposal_id]
        self._append_trace(entry)
        self.basin = [q for q in self.basin if q.category != p.category]
        self._save()
        rec = asdict(record)
        return {"status": "applied", "record": rec, "consequence": render_consequence(rec)}

    def _replay_refusal(self, entry: Dict[str, Any]) -> Optional[str]:
        """v0.8.5 (ChatGPT round 5, F4). Run the owner's replay on this one crossing,
        from the live state, as if it were already the next trace entry.
        None means the replay accepts it; otherwise the replay's reason."""
        probe = dict(entry)
        probe["prev_hash"] = self._trace_head
        try:
            probe["entry_hash"] = _sha256(_canonical_json(probe))
            replay_signed_history(
                self.constitution, self.trace + [probe], self.public_key, self.organism_id,
                resume={"character": self.character, "category_sequence": self.category_sequence,
                        "consumed": self.consumed, "mutation_sequence": self.mutation_sequence,
                        "from_index": len(self.trace)})
        except (AttestationRefused, ValueError) as why:
            return str(why)
        return None

    def _reject(self, proposal_id: str, reason: str) -> None:
        self._append_trace({
            "event": "authorization_rejected",
            "proposal_id": proposal_id,
            "reason": reason,
            "timestamp": self.clock(),
        })
        self._save()


# ===========================================================================
# OWNER SIDE — outside the organism entirely (R2: same process here)
# ===========================================================================

def owner_sign_external(private_key_pem: str, payload_to_sign: str) -> str:
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("ascii"), password=None
    )
    return base64.urlsafe_b64encode(
        private_key.sign(payload_to_sign.encode("utf-8"))
    ).decode("ascii")


def _verify_owner_signature(public_key: Ed25519PublicKey, signature_b64: str, payload: str) -> bool:
    try:
        public_key.verify(base64.urlsafe_b64decode(signature_b64), payload.encode("utf-8"))
        return True
    except Exception:
        return False


def replay_signed_history(constitution: Dict[str, Any], trace: List[Dict[str, Any]],
                          owner_public_key: Ed25519PublicKey, organism_id: str,
                          resume: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """D4. Rebuild character, category sequences, consumed ledger and mutation
    count from the genesis character in the attested constitution, applying only
    readings this owner signed. Raises AttestationRefused on anything else.
    v0.8.5: with `resume`, start from the given state at trace index from_index
    (the organism uses this to check its next crossing before applying it)."""
    try:
        _check_chain(trace)
    except ValueError as why:
        raise AttestationRefused(f"trace chain does not verify: {why}")
    if not trace or trace[0].get("event") != "birth":
        raise AttestationRefused("trace does not begin with the birth event")

    constitution_root = _sha256(_canonical_json(constitution))
    allowed = policy_fields(constitution)
    character = {k: float(v) for k, v in constitution["genesis_character"].items()}
    gates = {c: 0 for c in allowed}
    consumed: Set[str] = set()
    mseq = 0
    applied: List[Tuple[int, Dict[str, Any]]] = []
    first = 1
    if resume is not None:
        character = {k: float(v) for k, v in resume["character"].items()}
        gates = dict(resume["category_sequence"])
        consumed = set(resume["consumed"])
        mseq = int(resume["mutation_sequence"])
        first = int(resume["from_index"])

    for i, entry in enumerate(trace[first:], start=first):
        ev = entry.get("event")
        if ev in NON_AUTHORIZING_EVENTS:
            continue
        if ev != "authorized_mutation":
            raise AttestationRefused(f"trace index {i}: unknown authorizing event {ev!r}")
        try:
            rec = entry["record"]
            payload_text = rec["signed_payload"]
            if not _verify_owner_signature(owner_public_key, rec["signature_b64"], payload_text):
                raise AttestationRefused(
                    f"trace index {i}: reading signature does not verify under the owner's key")
            pl = _strict_loads(payload_text)
            cat = pl["category"]
            problems = []
            if pl.get("kind") != "reading_authorization":
                problems.append("not a reading authorization")
            if pl.get("organism_id") != organism_id:
                problems.append("signed for another organism")
            if pl.get("proposal_id") != rec["proposal_id"] or rec["category"] != cat:
                problems.append("record does not match the signed reading")
            if cat not in allowed:
                problems.append(f"category {cat!r} not allowed")
            if pl.get("constitution_root") != constitution_root:
                problems.append("signed under another constitution")
            if pl.get("evidence_root") != _sha256(_canonical_json(rec["evidence"])):
                problems.append("recorded evidence differs from the signed reading")
            if pl.get("distribution_root") != _sha256(_canonical_json(rec["distribution"])):
                problems.append("recorded distribution differs from the signed reading")
            if problems:
                raise AttestationRefused(f"trace index {i}: " + "; ".join(problems))
            if pl.get("category_sequence") != gates[cat]:
                raise AttestationRefused(f"trace index {i}: reading taken at {cat} sequence "
                                         f"{pl.get('category_sequence')}, replay is at {gates[cat]}")
            if not _is_finite_number(pl.get("prior_value")) or float(pl["prior_value"]) != character[cat]:
                raise AttestationRefused(f"trace index {i}: reading taken from {cat}="
                                         f"{pl.get('prior_value')}, replay holds {character[cat]}")
            if not isinstance(pl.get("first_commit"), bool) or pl["first_commit"] != (gates[cat] == 0):
                raise AttestationRefused(f"trace index {i}: first-commit flag inconsistent with replay")
            key = f"{pl['proposal_id']}|{pl['nonce']}"
            if key in consumed:
                raise AttestationRefused(f"trace index {i}: reading applied twice")
            before = dict(character)
            lead, delta, destination = derive_destination(constitution, rec["distribution"], character[cat])
            if rec["change"] != {cat: destination} or rec["lead"] != lead or float(rec["delta"]) != delta:
                raise AttestationRefused(f"trace index {i}: recorded change is not what the attested rule derives")
            # v0.8.3 (ChatGPT round 3, F2): every remaining field must match the
            # replay, so a consequence rendered from an attested record is true.
            extra = []
            if rec.get("prior_value") != before[cat]:
                extra.append("prior_value")
            if not isinstance(rec.get("first_commit"), bool) or rec["first_commit"] != pl["first_commit"]:
                extra.append("first_commit")
            snap = rec.get("prior_character_snapshot")
            if snap != before:
                diff = sorted(k for k in before if not isinstance(snap, dict) or snap.get(k) != before[k])
                extra.append("prior_character_snapshot (" + ", ".join(
                    f"{k}: recorded {snap.get(k) if isinstance(snap, dict) else snap!r}, replay {before[k]}"
                    for k in diff) + ")")
            if set(rec) != _RECORD_FIELDS:
                extra.append("field set")
            if extra:
                raise AttestationRefused(f"trace index {i}: record fields differ from the replay: {extra}")
            # v0.8.4 (ChatGPT round 4, F3; author A1): metadata provenance.
            meta = []
            at = rec.get("authorized_at")
            if not _is_finite_number(at):
                meta.append("authorized_at is not a finite number")
            elif not (float(pl["timestamp"]) - 1e-6 <= float(at) <= float(pl["expires_at"]) + 1e-6):
                meta.append("authorized_at outside the reading's own window")
            if entry.get("timestamp") != at:
                meta.append("event timestamp differs from authorized_at")
            ann = rec.get("unverified_annotation")
            if not isinstance(ann, str) or len(ann) > 2000:
                meta.append("unverified_annotation is not a short string")
            if meta:
                raise AttestationRefused(f"trace index {i}: record metadata invalid: {meta}")
            character[cat] = destination
            gates[cat] += 1
            consumed.add(key)
            mseq += 1
            if rec["category_sequence"] != gates[cat] or rec["mutation_sequence"] != mseq:
                raise AttestationRefused(f"trace index {i}: recorded sequences differ from replay")
            applied.append((i, rec))
        except (ValueError, KeyError, TypeError) as why:
            raise AttestationRefused(f"trace index {i}: malformed authorized mutation ({type(why).__name__}: {why})")

    return {"character": character, "category_sequence": gates,
            "consumed": consumed, "mutation_sequence": mseq, "applied": applied}


class OwnerWitness:
    """
    Linear checkpoint head held OUTSIDE the organism (C4/C5).
    v0.8.4: re-read from disk before every operation, under the owner lock, and
    a write-ahead intent ("pending") makes the checkpoint commit recoverable.
    R1 (revised): a local file under an advisory POSIX lock, standing in for a
    TPM counter / HSM / remote notary.
    """

    def __init__(self, ledger_path: Path | str, lock_path: Optional[Path | str] = None):
        self.path = Path(ledger_path)
        self.lock_path = Path(lock_path) if lock_path is not None else self.path.parent / "owner.lock"
        self.ledger: Dict[str, Dict[str, Any]] = {}      # organism_id -> current head
        self.pending: Dict[str, Dict[str, Any]] = {}     # organism_id -> commit in progress
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            data = _strict_loads(self.path.read_text(encoding="utf-8"))
            self.ledger, self.pending = data["heads"], data["pending"]
        else:
            self.ledger, self.pending = {}, {}

    def _refresh(self) -> None:
        self._load()  # re-read the witness before every operation

    def _persist(self) -> None:
        _durable_write(self.path, _canonical_json({"heads": self.ledger, "pending": self.pending}))

    @staticmethod
    def _checkpoint_hash(cp: Checkpoint) -> str:
        return _sha256(HumbleSeed.checkpoint_payload(cp))

    @staticmethod
    def _check_enrollment(cp: Checkpoint) -> None:
        if cp.sequence != 0:
            raise RollbackDetected(
                f"Invalid enrollment: first checkpoint sequence is {cp.sequence}, expected 0"
            )
        if cp.prev_checkpoint_hash != "0" * 64:
            raise RollbackDetected("Invalid enrollment: genesis checkpoint has a nonzero parent")

    @_owner_locked
    def check_successor(self, cp: Checkpoint) -> None:
        self._refresh()
        if cp.organism_id in self.pending:
            raise RollbackDetected("A checkpoint commit is pending for this organism; recover it first")
        known = self.ledger.get(cp.organism_id)
        if known is None:
            self._check_enrollment(cp)
            return
        if cp.birth_root != known.get("birth_root"):
            raise RollbackDetected("Identity fork: checkpoint birth root does not match witness")
        if cp.sequence != known["sequence"] + 1:
            raise RollbackDetected(
                f"Non-successor checkpoint: organism presents sequence {cp.sequence}, "
                f"expected {known['sequence'] + 1}"
            )
        if cp.prev_checkpoint_hash != known["checkpoint_hash"]:
            raise RollbackDetected("Advancing fork: checkpoint parent does not match witness head")

    @_owner_locked
    def check_current(self, cp: Checkpoint) -> None:
        self._refresh()
        known = self.ledger.get(cp.organism_id)
        if known is None:
            raise RollbackDetected("Unknown organism: explicit sequence-zero enrollment is required")
        if cp.birth_root != known.get("birth_root"):
            raise RollbackDetected("Identity fork: checkpoint birth root does not match witness")
        if cp.sequence < known["sequence"]:
            raise RollbackDetected(
                f"Rollback: organism presents sequence {cp.sequence}, witness holds {known['sequence']}"
            )
        if cp.sequence > known["sequence"]:
            raise RollbackDetected(
                f"Unwitnessed advance: organism presents sequence {cp.sequence}, "
                f"witness holds {known['sequence']}"
            )
        if self._checkpoint_hash(cp) != known["checkpoint_hash"]:
            raise RollbackDetected(f"Fork: two different states both claim sequence {cp.sequence}")

    def _advance(self, cp: Checkpoint) -> None:
        self.ledger[cp.organism_id] = {
            "sequence": cp.sequence,
            "checkpoint_hash": self._checkpoint_hash(cp),
            "birth_root": cp.birth_root,
        }

    @_owner_locked
    def record(self, cp: Checkpoint) -> None:
        """Advance the head in one step (no organism install in between)."""
        self._refresh()
        known = self.ledger.get(cp.organism_id)
        cp_hash = self._checkpoint_hash(cp)
        if known is not None and cp.sequence == known["sequence"]:
            if cp_hash == known["checkpoint_hash"] and cp.birth_root == known.get("birth_root"):
                return
            raise RollbackDetected(f"Fork: refusing to overwrite recorded sequence {cp.sequence}")
        self.check_successor(cp)
        self._advance(cp)
        self._persist()

    @_owner_locked
    def begin(self, cp: Checkpoint, signature_b64: str) -> None:
        """Write-ahead intent: durable before the organism installs the checkpoint."""
        self._refresh()
        self.check_successor(cp)
        self.pending[cp.organism_id] = {"checkpoint": asdict(cp), "signature_b64": signature_b64,
                                        "checkpoint_hash": self._checkpoint_hash(cp)}
        self._persist()

    @_owner_locked
    def commit(self, cp: Checkpoint) -> None:
        """Advance the head to the pending checkpoint and clear the intent."""
        self._refresh()
        p = self.pending.get(cp.organism_id)
        if p is None or p["checkpoint_hash"] != self._checkpoint_hash(cp):
            raise RollbackDetected("No matching pending checkpoint commit")
        self._advance(cp)
        del self.pending[cp.organism_id]
        self._persist()

    @_owner_locked
    def abandon(self, organism_id: str) -> None:
        self._refresh()
        if self.pending.pop(organism_id, None) is not None:
            self._persist()

    @_owner_locked
    def pending_for(self, organism_id: str) -> Optional[Dict[str, Any]]:
        self._refresh()
        p = self.pending.get(organism_id)
        return copy.deepcopy(p) if p is not None else None


class OwnerLedger:
    """The owner's own record of its acts (ruling 1): every reading signed (by
    exact payload hash, with the owner's clock) and every answer given, in one
    ordered sequence. v0.8.4: re-read from disk before every operation, under
    the owner lock, so no session acts on a stale copy or writes one back.
    R21: a local file standing in for durable owner storage."""

    def __init__(self, path: Path | str, lock_path: Optional[Path | str] = None):
        self.path = Path(path)
        self.lock_path = Path(lock_path) if lock_path is not None else self.path.parent / "owner.lock"
        self.data: Dict[str, Any] = {"seq": 0, "organisms": {}}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            self.data = _strict_loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"seq": 0, "organisms": {}}

    def _refresh(self) -> None:
        self._load()  # re-read the ledger before every operation

    def _persist(self) -> None:
        _durable_write(self.path, _canonical_json(self.data))

    def _org(self, organism_id: str) -> Dict[str, Any]:
        return self.data["organisms"].setdefault(organism_id, {"signed": {}, "answers": []})

    def _next(self) -> int:
        self.data["seq"] += 1
        return self.data["seq"]

    @_owner_locked
    def record_signature(self, organism_id: str, proposal_id: str, category: str,
                         payload_sha256: str, at: float) -> None:
        self._refresh()
        signed = self._org(organism_id)["signed"]
        if payload_sha256 not in signed:          # lifetime runs from the FIRST signing
            signed[payload_sha256] = {"proposal_id": proposal_id, "category": category,
                                      "signed_at": float(at), "seq": self._next()}
            self._persist()

    @_owner_locked
    def record_answer(self, organism_id: str, proposal_id: str, category: str,
                      answer: str, at: float) -> None:
        self._refresh()
        self._org(organism_id)["answers"].append({"proposal_id": proposal_id, "category": category,
                                                  "answer": answer, "at": float(at),
                                                  "seq": self._next()})
        self._persist()

    @_owner_locked
    def signed(self, organism_id: str, payload_sha256: str) -> Optional[Dict[str, Any]]:
        self._refresh()
        return self.data["organisms"].get(organism_id, {}).get("signed", {}).get(payload_sha256)

    @_owner_locked
    def answers_to(self, organism_id: str, proposal_id: str) -> List[str]:
        self._refresh()
        return [a["answer"] for a in self.data["organisms"].get(organism_id, {}).get("answers", [])
                if a["proposal_id"] == proposal_id]

    @_owner_locked
    def answers_in_category_after(self, organism_id: str, category: str, seq: int) -> List[str]:
        self._refresh()
        return [a["answer"] for a in self.data["organisms"].get(organism_id, {}).get("answers", [])
                if a["category"] == category and a["seq"] > seq]


class OwnerTool:
    """Sign readings, record answers, attest consequences, keep the witness and
    the ledger. Every operation runs under one exclusive owner lock (v0.8.4)."""

    def __init__(self, private_key_pem: str, witness: OwnerWitness,
                 ledger: Optional[OwnerLedger] = None):
        self._pem = private_key_pem
        self.witness = witness
        self.lock_path = witness.lock_path
        self.ledger = ledger if ledger is not None else OwnerLedger(
            witness.path.parent / "owner_ledger.json", lock_path=self.lock_path)
        self.clock: Callable[[], float] = time.time
        key = serialization.load_pem_private_key(private_key_pem.encode("ascii"), password=None)
        self._public_key = key.public_key()
        self._public_b64 = base64.urlsafe_b64encode(self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw,
        )).decode("ascii")

    @_owner_locked
    def sign_proposal(self, payload_to_sign: str) -> str:
        pl = _strict_loads(payload_to_sign)
        self.ledger.record_signature(pl["organism_id"], pl["proposal_id"], pl["category"], _sha256(payload_to_sign), self.clock())
        return owner_sign_external(self._pem, payload_to_sign)

    @_owner_locked
    def answer(self, seed: HumbleSeed, proposal_id: str, answer: str, text: str = "") -> dict:
        """The owner answers a reading's question. Recorded in the owner's ledger
        (authoritative) and passed to the organism as evidence."""
        if answer not in OWNER_ANSWERS:
            raise ValueError(f"Answer must be one of {OWNER_ANSWERS}")
        if proposal_id not in seed.pending:
            raise ValueError("No pending reading with that id")
        category = _strict_loads(seed.pending[proposal_id].payload_to_sign)["category"]
        self.ledger.record_answer(seed.organism_id, proposal_id, category, answer, self.clock())
        return seed.record_owner_answer(proposal_id, answer, text)

    def _check_owner_acts(self, seed: HumbleSeed, i: int, rec: Dict[str, Any],
                          now: float, ttl: float, prev: Optional[Dict[str, Any]] = None) -> None:
        """Rulings 1-3 for one crossing applied since the last attestation. `prev` is
        the previous crossing in the same category, from the replay (None: the first)."""
        oid, pid, cat = seed.organism_id, rec["proposal_id"], rec["category"]
        entry = self.ledger.signed(oid, _sha256(rec["signed_payload"]))
        if entry is None or entry["proposal_id"] != pid:
            raise AttestationRefused(f"trace index {i}: reading was not signed through this owner tool")
        if now > entry["signed_at"] + ttl:
            raise AttestationRefused(f"trace index {i}: reading is past its lifetime by the owner's clock")
        expired_before = any(
            e.get("event") == "authorization_rejected" and e.get("proposal_id") == pid
            and "expired" in str(e.get("reason", "")) for e in seed.trace[:i])
        if expired_before:
            raise AttestationRefused(
                f"trace index {i}: the organism recorded this reading as expired before applying it")
        # v0.8.5 (ChatGPT round 5, F1): the owner's category window starts where the owner
        # can verify it: its own signature of the previous crossing in this category, or
        # the start of its record for the first. Answers before that signature were checked
        # when the previous crossing was attested; answers after it are checked here.
        if prev is None:
            window_start = 0
            window = "since its record began"
        else:
            prev_signed = self.ledger.signed(oid, _sha256(prev["signed_payload"]))
            if prev_signed is None:
                raise AttestationRefused(
                    f"trace index {i}: the previous {cat} crossing was not signed through this owner tool")
            window_start = prev_signed["seq"]                # [OWNER-WINDOW]
            window = f"since it signed the previous {cat} crossing"
        to_reading = self.ledger.answers_to(oid, pid)
        held = answer_position(to_reading, self.ledger.answers_in_category_after(oid, cat, window_start))
        if held is not None:
            which = ("its latest answer to this reading is 'no'" if to_reading and to_reading[-1] == "no"
                     else f"its latest answer in {cat} {window} is 'no'")    # v0.8.6 (author A2)
            raise AttestationRefused(f"trace index {i}: owner's position: {which}")
        issued_head = _strict_loads(rec["signed_payload"])["issued_trace_head"]
        start = next((j for j, e in enumerate(seed.trace) if e.get("entry_hash") == issued_head), -1)
        window = seed.trace[start + 1:i]
        recorded = answer_position(*_answers_in_window({"proposal_id": pid, "category": cat}, window))
        if recorded is not None:
            raise AttestationRefused(
                f"trace index {i}: the organism's own record holds this reading ({recorded})")

    def verify_consequence(self, seed: HumbleSeed, cp: Checkpoint) -> None:
        """D4: refuse unless the presented state is exactly what replaying this
        owner's signed readings from the attested genesis produces."""
        if seed.birth is None:
            raise AttestationRefused("organism has not hatched")
        if seed.birth.public_key_b64 != self._public_b64:
            raise AttestationRefused("organism is not keyed to this owner")
        if _sha256(_canonical_json(seed.constitution)) != seed.birth.constitution_hash:
            raise AttestationRefused("constitution does not match the birth commitment")
        if cp.birth_root != _sha256(_canonical_json(asdict(seed.birth))):
            raise AttestationRefused("checkpoint birth root does not match the birth record")
        if seed.checkpoint is not None:
            n = seed.checkpoint.attested_trace_len
            if _chain_head(seed.trace[:n]) != seed.checkpoint.trace_head:
                raise AttestationRefused("attested history was rewritten")
        st = replay_signed_history(seed.constitution, seed.trace, self._public_key, seed.organism_id)
        # Rulings 1-3: crossings applied since the last attestation are checked
        # against the owner's own records and clock.
        since = seed.checkpoint.attested_trace_len if seed.checkpoint is not None else 0
        now, ttl = self.clock(), policy_ttl(seed.constitution)
        previous: Dict[str, Dict[str, Any]] = {}
        for i, rec in st["applied"]:
            if i >= since:
                self._check_owner_acts(seed, i, rec, now, ttl, previous.get(rec["category"]))
            previous[rec["category"]] = rec
        mismatched = []
        if cp.character_root != _sha256(_canonical_json(st["character"])):
            diff = {k: (seed.character.get(k), st["character"][k]) for k in st["character"]
                    if seed.character.get(k) != st["character"][k]}
            mismatched.append(f"character (presented, replayed): {diff}")
        if cp.gates_root != _sha256(_canonical_json(st["category_sequence"])):
            mismatched.append("category sequences")
        if cp.consumed_root != _sha256(_canonical_json(sorted(st["consumed"]))):
            mismatched.append("consumed ledger")
        if cp.mutation_sequence != st["mutation_sequence"]:
            mismatched.append("mutation sequence")
        if cp.trace_head != _chain_head(seed.trace) or cp.attested_trace_len != len(seed.trace):
            mismatched.append("trace head")
        if mismatched:
            raise AttestationRefused(
                "presented state is not the consequence of signed readings: " + "; ".join(mismatched))

    def _saved_checkpoint(self, seed: HumbleSeed) -> Tuple[Optional[Checkpoint], Optional[str]]:
        """v0.8.5 (ChatGPT round 5, F2/F3): the checkpoint and signature in the
        organism's saved state, re-read now under the owner lock, not the object's."""
        try:
            data = _strict_loads(seed._state_path().read_text(encoding="utf-8"))
            cp = data.get("checkpoint")
            return (Checkpoint(**cp) if cp else None), data.get("checkpoint_sig")
        except (OSError, ValueError, TypeError, AttributeError) as why:
            raise RollbackDetected("A pending checkpoint commit cannot be resolved: the organism's "
                                   f"saved state is unreadable ({type(why).__name__})")

    def _saved_state_refusal(self, seed: HumbleSeed) -> Optional[str]:
        """v0.8.6 (author A1): None if the organism's saved state loads and verifies on its own."""
        probe = HumbleSeed(seed.data_dir)
        try:
            probe.load()
        except (IntegrityError, ValueError, KeyError, TypeError, FileNotFoundError) as why:
            return f"{type(why).__name__}: {why}"
        return None

    def _recover(self, seed: HumbleSeed) -> Optional[str]:
        """Complete or abandon a checkpoint commit that was interrupted between
        the witness intent and the witness advance (ChatGPT round 4, F4).
        v0.8.5: decided from the organism's saved state, never from the object
        handed in, which may be stale or ahead of its own disk."""
        oid = seed.organism_id
        p = self.witness.pending_for(oid)
        if p is None:
            return None
        pending_cp = Checkpoint(**p["checkpoint"])
        saved_cp, saved_sig = self._saved_checkpoint(seed)       # [RECOVER-FROM-DISK]
        installed = (saved_cp is not None and saved_sig == p["signature_b64"]
                     and HumbleSeed.checkpoint_payload(saved_cp)
                     == HumbleSeed.checkpoint_payload(pending_cp))
        if installed:                       # v0.8.6 (author A1): the saved state must also verify
            why = self._saved_state_refusal(seed)                 # [RECOVER-VERIFIES]
            if why is not None:
                raise RollbackDetected("A pending checkpoint commit cannot be completed: the saved state "
                                       f"claims it but does not verify ({why})")
        if installed:
            self.witness.commit(pending_cp)
            return "completed"
        head = self.witness.ledger.get(oid)
        at_head = ((head is None and saved_cp is None)
                   or (head is not None and saved_cp is not None
                       and OwnerWitness._checkpoint_hash(saved_cp) == head["checkpoint_hash"]))
        if at_head:
            self.witness.abandon(oid)
            return "abandoned"
        raise RollbackDetected("A pending checkpoint commit matches neither the organism's saved state "
                               "nor the witness head")

    @_owner_locked
    def attest(self, seed: HumbleSeed) -> bool:
        # v0.8.6 (ChatGPT r6 F1): the organism lock is held from recovery to the witness
        # commit, so no organism write can land between the checks and the commit.
        with seed._organism_lock():
            return self._attest_under_organism_lock(seed)

    def _attest_under_organism_lock(self, seed: HumbleSeed) -> bool:
        self._recover(seed)
        seed._require_current()                 # [ATTEST-CURRENT]
        cp = seed.checkpoint_request()          # built now, at signing time
        self.witness.check_successor(cp)
        self.verify_consequence(seed, cp)       # [D4] replay before signing
        sig = owner_sign_external(self._pem, HumbleSeed.checkpoint_payload(cp))
        self.witness.begin(cp, sig)             # [COMMIT-1] durable intent before the organism installs
        if not seed.install_checkpoint(cp, sig):
            self.witness.abandon(seed.organism_id)
            return False
        self.witness.commit(cp)                 # [COMMIT-2] the witness advances
        return True

    @_owner_locked
    def audit(self, seed: HumbleSeed) -> bool:
        self._recover(seed)
        seed.verify()
        if seed.checkpoint is None:
            raise IntegrityError("No checkpoint to audit")
        self.witness.check_current(seed.checkpoint)
        return True


# ---------------------------------------------------------------------------
# Attack helpers used by the harness and by the lineage's R10 probe
# ---------------------------------------------------------------------------

def _reseal_attack(seed: HumbleSeed, mutate, rechain: bool = False) -> str:
    """Apply a raw edit, optionally rebuild the hash chain, recompute the seal:
    defeat every local integrity check. Whatever objects after this is the
    owner attestation and nothing else."""
    st = _strict_loads(seed._state_path().read_text())
    mutate(st)

    ghost = HumbleSeed(data_dir=seed.data_dir)
    ghost.organism_id = st["organism_id"]
    ghost.birth = BirthRecord(**st["birth"])
    ghost.constitution = st["constitution"]
    ghost.character = st["character"]
    ghost.basin = [PreTrace(**b) for b in st["basin"]]
    ghost.pending = {k: PendingProposal(**v) for k, v in st["pending"].items()}
    ghost.consumed = set(st["consumed"])
    ghost.category_sequence = st["category_sequence"]
    ghost.mutation_sequence = st["mutation_sequence"]

    if rechain:
        bodies = [{k: v for k, v in e.items() if k not in ("prev_hash", "entry_hash")}
                  for e in st["trace"]]
        ghost.trace = []
        ghost._trace_head = "0" * 64
        for b in bodies:
            ghost._append_trace(b)
        st["trace"] = ghost.trace
        st["trace_head"] = ghost._trace_head
    else:
        ghost.trace = st["trace"]
        ghost._trace_head = st["trace_head"]

    st["state_seal"] = ghost._compute_seal()
    seed._state_path().write_text(_canonical_json(st), encoding="utf-8")

    fresh = HumbleSeed(data_dir=seed.data_dir)
    try:
        fresh.load()
        return "ACCEPTED — FAIL"
    except IntegrityError as ex:
        return f"rejected: {ex}"


if __name__ == "__main__":
    print(__doc__.split("FINDINGS CLOSED")[0])
    print("Run the harness: python3 -I falsify_v0_8_6.py")
