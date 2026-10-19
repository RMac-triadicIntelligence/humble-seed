#!/usr/bin/env python3
"""
Humble Seed v0.8 CANDIDATE — Liveness and Signing the Reading
==============================================================

STATUS: candidate, not canonical. K2 implements a proposal ("sign the reading,
not the result") that awaits the author's ruling. Parent: the v0.7 file headed
"Canonical Converged Constitutional Core" (sha256 08a75604...3707), which
carries C1-C5, including the fail-closed unknown-organism audit (C5) that the
published repository's v0.7 lacks.

Two changes. Everything else is carried from the parent unchanged.

  K1  LIVENESS. In v0.7 a signed proposal was rejected if the trace head,
      the whole character root, or the global mutation sequence had moved
      since issuance. Any ordinary exchange appends a non-authorizing
      "dwelling" entry, so one message between proposal and signature made
      the proposal stale; a commit in another category did the same.
      -> Staleness is now per category. The envelope binds the category's
         prior value and its attested category sequence. Non-authorizing
         events and other categories' commits no longer expire a reading.
         Same-category ordering (F4) is still enforced: once a category
         advances, every older reading in that category is stale.
      The trace head and global sequence at issuance are still signed, as
      provenance ("read at"), but they are not rejection conditions.

  K2  SIGN THE READING, NOT THE RESULT. v0.7 signed the exact change, so the
      owner's signature named a destination (against the Sept 2026 rule that
      grace carries no destination). In v0.7 the change was already a pure
      function of signed inputs (prior value + delta for the lead read), so
      the change field restated what the signature already determined.
      -> The envelope binds the reading: evidence root, distribution root,
         prior value, category sequence, and the constitution root. It names
         no destination. The destination is derived at apply time from those
         signed inputs and the derivation rule, which now lives in the
         ATTESTED constitution instead of a module constant. Nothing can be
         swapped after signing, and the signer never chooses where it lands.
      The applied change is recorded in the MutationRecord, as before.

  Gates: first_commit_pending (bool map) is replaced by category_sequence
  (int map, attested through gates_root). first_commit is derived as
  category_sequence[category] == 0, so the flag and the sequence cannot
  disagree.

OPEN DESIGN QUESTIONS (the author's to rule on; not resolved here)
  D1  A signed reading of earlier evidence still applies after newer evidence
      arrives in the same category (newer evidence alone does not advance the
      category). Under the Oct 15 rule that every reading is a fresh look at
      the whole present terrain, the author may want apply-time re-reading.
  D2  The owner sees a derived destination as a PREVIEW (returned, never
      stored, never signed). Attention is not a control (R7).
  D3  Whether the destination should be visible to the signer at all.

FOR ADVERSARIAL REVIEWERS — carried limits R1-R9 from the parent, plus:
  R11 prior_value is redundant with category_sequence on every path we found
      (only authorized commits change a category's value, and each advances
      its sequence). Its removal is a declared SURVIVING mutant in the
      harness. Kept as defence in depth, like R10.

Run the falsification harness:  python falsify_v0_8.py
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import secrets
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


SCHEMA_VERSION = "0.8-candidate"

ALLOWED_CHARACTER_FIELDS = {"verbosity", "formality", "curiosity"}
VALUE_MIN, VALUE_MAX = 0.0, 1.0
PROPOSAL_TTL_SECONDS = 3600.0

# Genesis input ONLY. After hatch the organism reads its derivation rule from
# the attested constitution, never from this constant (K2).
GENESIS_DERIVATION = {
    "rule": ("destination = clamp(prior_value + label_to_delta[lead], value_range); "
             "a crossing is possible only if lead weight >= min_lead_weight"),
    "label_to_delta": {"preference": -0.25},
    "min_lead_weight": 0.60,
}

NON_AUTHORIZING_EVENTS = {"dwelling", "authorization_rejected", "checkpoint"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


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


class IntegrityError(RuntimeError):
    """Persisted state failed a structural or attestation check."""


class RollbackDetected(RuntimeError):
    """External witness observed a sequence regression or fork."""


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
    constitution_root: str        # K2: pins the derivation rule
    issued_trace_head: str        # provenance only; never a rejection condition
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
    prior_character_snapshot: Dict[str, float]
    note: str = ""


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

class HumbleSeed:

    def __init__(self, data_dir: Path | str = "./seed_data_v08c"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

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
    # K2: the derivation rule comes from the attested constitution
    # ------------------------------------------------------------------

    def _derivation(self) -> Dict[str, Any]:
        return self.constitution["derivation"]

    def derive(self, category: str, distribution: Dict[str, float],
               prior_value: float) -> Tuple[str, float, float]:
        """Return (lead, delta, destination). Raises ValueError if the reading
        does not support a crossing under the attested rule."""
        der = self._derivation()
        lead = max(distribution, key=distribution.get)
        weight = float(distribution[lead])
        table = der["label_to_delta"]
        if lead not in table:
            raise ValueError(f"lead read {lead!r} has no sanctioned mapping")
        if weight < float(der["min_lead_weight"]):
            raise ValueError(f"lead weight {weight:.3f} below {der['min_lead_weight']}")
        delta = float(table[lead])
        destination = min(VALUE_MAX, max(VALUE_MIN, float(prior_value) + delta))
        return lead, delta, destination

    # ------------------------------------------------------------------
    # Birth
    # ------------------------------------------------------------------

    def hatch(self) -> Tuple[str, str, Checkpoint]:
        """Returns (organism_id, owner_private_pem, genesis checkpoint request).

        The organism is NOT loadable until the owner installs a signed
        checkpoint. Fail-closed from the first instant.
        """
        if self.organism_id is not None:
            raise RuntimeError("This seed has already hatched.")

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
        created_at = time.time()

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
            "allowed_character_fields": sorted(ALLOWED_CHARACTER_FIELDS),
            "value_range": [VALUE_MIN, VALUE_MAX],
            "derivation": copy.deepcopy(GENESIS_DERIVATION),
        }
        constitution_hash = _sha256(_canonical_json(constitution))
        genesis_hash = self._derive_genesis(
            organism_id, public_b64, created_at, constitution_hash
        )

        self.organism_id = organism_id
        self.public_key = public_key
        self.constitution = constitution
        self.birth = BirthRecord(
            organism_id=organism_id,
            public_key_b64=public_b64,
            genesis_hash=genesis_hash,
            created_at=created_at,
            constitution_hash=constitution_hash,
        )
        self.character = {"verbosity": 0.5, "formality": 0.5, "curiosity": 0.6}
        self.category_sequence = {c: 0 for c in sorted(ALLOWED_CHARACTER_FIELDS)}
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
        prev = "0" * 64
        for i, entry in enumerate(self.trace):
            if entry.get("prev_hash") != prev:
                raise IntegrityError(f"Hash chain broken at index {i}: prev_hash mismatch")
            body = {k: v for k, v in entry.items() if k != "entry_hash"}
            if entry.get("entry_hash") != _sha256(_canonical_json(body)):
                raise IntegrityError(f"Hash chain broken at index {i}: entry_hash mismatch")
            prev = entry["entry_hash"]
        if prev != self._trace_head:
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
            timestamp=time.time(),
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
        self._save()
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

    def _save(self) -> None:
        if self.organism_id is None or self.birth is None:
            return
        state = {
            "schema_version": SCHEMA_VERSION,
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
        tmp = self._state_path().with_suffix(".json.tmp")
        tmp.write_text(_canonical_json(state), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._state_path())

    def load(self) -> None:
        path = self._state_path()
        if not path.exists():
            raise FileNotFoundError("No saved organism state found.")
        data = json.loads(path.read_text(encoding="utf-8"))

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

        self.verify(expected_seal=data.get("state_seal"))

    def _verify_derivation(self) -> None:
        der = self.constitution.get("derivation")
        if not isinstance(der, dict):
            raise IntegrityError("Constitution carries no derivation rule")
        table = der.get("label_to_delta")
        if not isinstance(table, dict) or not table:
            raise IntegrityError("Derivation rule has no label_to_delta table")
        for k, v in table.items():
            if not isinstance(k, str) or not _is_number(v):
                raise IntegrityError(f"Derivation entry {k!r} is not label -> number")
        w = der.get("min_lead_weight")
        if not _is_number(w) or not (0.0 < float(w) <= 1.0):
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
        self._verify_derivation()

        if set(self.category_sequence) != ALLOWED_CHARACTER_FIELDS:
            raise IntegrityError("Category sequence set does not match allowed character fields")
        for category, n in self.category_sequence.items():
            if isinstance(n, bool) or not isinstance(n, int) or n < 0:
                raise IntegrityError(f"Category sequence for {category} is not a non-negative int")
        if sum(self.category_sequence.values()) != self.mutation_sequence:
            raise IntegrityError("Category sequences do not sum to the mutation sequence")

        if set(self.character) != ALLOWED_CHARACTER_FIELDS:
            raise IntegrityError("Character field set does not match allowed character fields")
        for k, v in self.character.items():
            if not _is_number(v):
                raise IntegrityError(f"Character field {k} is not numeric: {type(v).__name__}")
            if not (VALUE_MIN <= float(v) <= VALUE_MAX):
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
        """R3: keyword stub."""
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

    def dwell_or_propose(self, category: str, event: str, transcript: str) -> dict:
        if category not in ALLOWED_CHARACTER_FIELDS:
            raise ValueError(f"Unknown character category: {category}")

        dist = self.interpret(event, transcript)
        lead = max(dist, key=dist.get)
        lead_weight = dist[lead]

        self.basin.append(PreTrace(
            category=category, distribution=dist, evidence=[transcript],
            salience=lead_weight, created_at=time.time(),
        ))

        try:
            self.derive(category, dist, float(self.character[category]))
        except ValueError as why:
            self._append_trace({
                "event": "dwelling",
                "category": category,
                "reason": str(why),
                "timestamp": time.time(),
            })
            self._save()
            return {
                "status": "dwelling",
                "distribution": dist,
                "message": "Holding in basin. Owner authorization required for permanent change.",
            }

        proposal = self._issue_pending_proposal(
            category=category, distribution=dist, evidence=[transcript],
        )
        _, _, preview = self.derive(category, dist, proposal.prior_value)
        return {
            "status": "proposal",
            "proposal_id": proposal.proposal_id,
            "payload_to_sign": proposal.payload_to_sign,
            "first_commit": proposal.first_commit,
            # D2: informational only. Never stored, never signed.
            "preview_destination": {category: preview},
            "message": (
                "FIRST COMMITMENT in this category — owner should review with care."
                if proposal.first_commit else
                "Reading issued and pending. Requires valid owner signature to cross."
            ),
        }

    # ------------------------------------------------------------------
    # Reading issuance (K1 + K2)
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_distribution(distribution: Dict[str, Any]) -> Dict[str, float]:
        if not isinstance(distribution, dict) or not distribution:
            raise ValueError("Distribution must be a non-empty mapping")
        out = {}
        for k, v in distribution.items():
            if not isinstance(k, str) or not _is_number(v) or float(v) < 0.0:
                raise ValueError(f"Distribution entry {k!r} must map a label to a non-negative number")
            out[k] = float(v)
        if abs(sum(out.values()) - 1.0) > 1e-6:
            raise ValueError("Distribution must sum to 1")
        return out

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
        ttl: float = PROPOSAL_TTL_SECONDS,
    ) -> PendingProposal:
        if category not in ALLOWED_CHARACTER_FIELDS:
            raise ValueError(f"Disallowed mutation category: {category}")
        distribution = self._validate_distribution(distribution)
        prior_value = float(self.character[category])
        self.derive(category, distribution, prior_value)   # must support a crossing

        seq = self.category_sequence[category]
        first_commit = (seq == 0)          # derived; no caller override exists

        timestamp = time.time()
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
            expires_at=timestamp + ttl,
            payload_to_sign="",
            payload_hash="",
        )
        p.payload_to_sign = self._reading_payload(p)
        p.payload_hash = _sha256(p.payload_to_sign)
        self.pending[p.proposal_id] = p
        self._save()
        return p

    # ------------------------------------------------------------------
    # External authorization — verify only
    # ------------------------------------------------------------------

    def authorize_and_apply(
        self, proposal_id: str, signature_b64: str, owner_note: str = "",
    ) -> Optional[Checkpoint]:
        """
        Returns a Checkpoint REQUEST on success (the owner must sign it and
        call install_checkpoint before the state will load again), or None
        on rejection. Fail-closed: an applied-but-unattested state is
        deliberately not loadable.
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
        if p.category not in ALLOWED_CHARACTER_FIELDS:
            self._reject(proposal_id, f"disallowed category {p.category}")
            return None
        if time.time() > p.expires_at:
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

        # K2: the derivation rule the owner signed under must still be the rule.
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
        if not (VALUE_MIN <= destination <= VALUE_MAX):
            self._reject(proposal_id, "derived destination out of range")
            return None

        prior = dict(self.character)
        self.character[p.category] = float(destination)
        self.category_sequence[p.category] = current_seq + 1
        self.consumed.add(consume_key)
        self.mutation_sequence += 1
        del self.pending[proposal_id]

        record = MutationRecord(
            proposal_id=p.proposal_id, category=p.category, lead=lead, delta=delta,
            prior_value=p.prior_value, change={p.category: float(destination)},
            distribution=p.distribution, evidence=p.evidence,
            first_commit=p.first_commit,
            category_sequence=self.category_sequence[p.category],
            mutation_sequence=self.mutation_sequence,
            authorized_at=time.time(), signature_b64=signature_b64,
            prior_character_snapshot=prior, note=owner_note,
        )
        self._append_trace({
            "event": "authorized_mutation",
            "record": asdict(record),
            "timestamp": record.authorized_at,
        })
        self.basin = [q for q in self.basin if q.category != p.category]
        self._save()
        return self.checkpoint_request()

    def _reject(self, proposal_id: str, reason: str) -> None:
        self._append_trace({
            "event": "authorization_rejected",
            "proposal_id": proposal_id,
            "reason": reason,
            "timestamp": time.time(),
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


class OwnerWitness:
    """
    Linear checkpoint head held OUTSIDE the organism (unchanged from parent C4/C5).
    R1: a local JSON file standing in for a TPM counter / HSM / remote notary.
    """

    def __init__(self, ledger_path: Path | str):
        self.path = Path(ledger_path)
        self.ledger: Dict[str, Dict[str, Any]] = {}
        if self.path.exists():
            self.ledger = json.loads(self.path.read_text(encoding="utf-8"))

    def _persist(self) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(_canonical_json(self.ledger), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

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

    def check_successor(self, cp: Checkpoint) -> None:
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

    def check_current(self, cp: Checkpoint) -> None:
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

    def record(self, cp: Checkpoint) -> None:
        known = self.ledger.get(cp.organism_id)
        cp_hash = self._checkpoint_hash(cp)
        if known is not None and cp.sequence == known["sequence"]:
            if cp_hash == known["checkpoint_hash"] and cp.birth_root == known.get("birth_root"):
                return
            raise RollbackDetected(f"Fork: refusing to overwrite recorded sequence {cp.sequence}")
        self.check_successor(cp)
        self.ledger[cp.organism_id] = {
            "sequence": cp.sequence,
            "checkpoint_hash": cp_hash,
            "birth_root": cp.birth_root,
        }
        self._persist()


class OwnerTool:
    """Convenience wrapper: sign readings, attest state, keep the witness."""

    def __init__(self, private_key_pem: str, witness: OwnerWitness):
        self._pem = private_key_pem
        self.witness = witness

    def sign_proposal(self, payload_to_sign: str) -> str:
        return owner_sign_external(self._pem, payload_to_sign)

    def attest(self, seed: HumbleSeed, cp: Checkpoint) -> bool:
        self.witness.check_successor(cp)
        sig = owner_sign_external(self._pem, HumbleSeed.checkpoint_payload(cp))
        if not seed.install_checkpoint(cp, sig):
            return False
        self.witness.record(cp)
        return True

    def audit(self, seed: HumbleSeed) -> bool:
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
    st = json.loads(seed._state_path().read_text())
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
    print(__doc__.split("OPEN DESIGN")[0])
    print("Run the harness: python falsify_v0_8.py")
