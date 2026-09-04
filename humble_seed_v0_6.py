#!/usr/bin/env python3
"""
Humble Seed v0.6 — Constitution-Bound State and Linear Witness
===============================================================

Builds on v0.5 and closes four additional falsifiers found by independent
probing:

  F6  First-commit truthfulness. The private proposal helper accepted a
      caller-supplied first_commit=False even when the live category gate was
      still pending. The owner could therefore countersign a misleading
      envelope.
      -> first_commit is now derived only from live organism state. There is
         no caller override, and apply rechecks the signed value against the
         live gate before accepting the signature.

  F7  Unattested critical roots. The state seal covered the constitution,
      birth, and first-commit gates, but the seal was unkeyed and the signed
      checkpoint did not cover those roots. A file-write attacker could
      rewrite them and recompute the seal.
      -> every checkpoint now binds genesis_hash, constitution_root, and
         gates_root. Load fails closed if any differs from owner-attested
         state.

  F8  Birth-trace rebinding. Active birth and constitution records could be
      changed together, resealed, and loaded because the trace's birth event
      was not cross-checked against the active records.
      -> verification requires exactly one birth event, at trace index zero,
         matching organism_id, genesis_hash, constitution_hash, and timestamp.

  F9  Advancing witness fork. The v0.5 witness rejected rollback and
      same-sequence forks but accepted any higher sequence, even with the
      wrong parent checkpoint.
      -> first enrollment must be sequence zero with the zero parent. Every
         later checkpoint must be either the identical recorded checkpoint
         or exactly the next sequence with the recorded checkpoint as parent.
         The witness also pins genesis_hash for the organism.

The v0.5 controls remain:

  F1  First-commit deadlock. A naturally hatched organism could never reach
      a proposal: the gate cleared only on a successful apply, which required
      a proposal, which the gate blocked.
      -> the gate no longer suppresses proposals. It marks the first proposal
         in a category first_commit=True inside the SIGNED payload, so the
         owner sees and countersigns a visibly-flagged first commitment.

  F2  Evidence provenance. evidence and distribution sat outside the signed
      payload; both could be swapped after signing and were then written
      permanently into the hash chain as an authorized record.
      -> evidence_root and distribution_root are in the signed envelope and
         re-derived at apply time.

  F3  Category binding. category="verbosity" carrying change={"formality":..}
      applied to formality AND cleared the verbosity first-commit gate — one
      authorization opening a gate on a category it never touched.
      -> set(change) must equal {category}, enforced at issuance and apply.

  F4  Stale ordering. An older signed proposal applied after a newer one
      silently reverted the value.
      -> the envelope binds prior_character_root, prior_trace_head and
         mutation_sequence. Any proposal issued against a superseded state
         no longer verifies. Consequence: one applicable proposal per state;
         others must be re-issued. That is the intended sequencing property.

  F5  Rollback. Restoring a pre-apply state file produced a cleanly sealed,
      internally consistent state, and the same signature applied again.
  O1  Unkeyed seal. Anyone able to write the state file and recompute
      _compute_seal() forged freely.
      -> both are the same defect: the state file was its own only authority.
         v0.5 adds an owner-signed CHECKPOINT over the state root, and an
         OwnerWitness holding a monotonic high-water sequence OUTSIDE the
         organism.

         O1 is now closed: an attacker who rewrites state and reseals cannot
         produce the owner's signature, so load() fails closed.

         F5 is closed ONLY with the witness. A whole-file rollback restores a
         genuinely owner-signed older checkpoint, so it is internally valid by
         construction. Nothing inside the organism can detect it. The witness
         can, because it remembers a sequence the rolled-back file does not.
         This is stated plainly rather than papered over: the organism cannot
         detect its own rollback, and no amount of local hashing changes that.

Also fixed: _issue_pending_proposal now persists (it previously did not,
unlike dwell_or_propose); proposals carry an expiry; state file is 0600.

SCHEMA NOTE
-----------
The signed checkpoint shape changed. v0.6 therefore rejects v0.5 state rather
than silently weakening or rewriting its commitments. A persistent v0.5
organism needs an explicit, owner-authorized migration ceremony; this
prototype's demonstration hatches a fresh v0.6 identity.


FOR ADVERSARIAL REVIEWERS
-------------------------
Read this before attacking. Confirming a listed item is not a finding.

  R1  The witness ledger is a plain local JSON file in this prototype. It
      stands in for a TPM counter, an HSM, or a remote notary. An attacker
      with write access to BOTH the organism state and the witness ledger
      can roll back both consistently. Real deployment puts the witness on
      hardware or another host. The trust claim is exactly: rollback is
      detectable by an external witness, not that this file is that witness.

  R2  owner_tool runs in the same process here. Structural split only.

  R3  interpret() is a keyword stub. Its confidence numbers are decorative.
      Attack what the system does with numbers, not the numbers.

  R4  No key rotation or revocation. Compromise of the owner key is total.

  R5  Single-writer. No file locking.

  R6  Between apply and checkpoint install there is a window where state is
      unattested. This fails CLOSED on load by design — see test [9] — but
      it means a crash mid-authorization requires owner involvement to
      recover. That is a deliberate liveness/safety trade, not an oversight.

  R7  A truthful first_commit value is flagged in signed material, so the
      owner SEES it. Nothing forces the owner to think about it. Human
      attention is not a cryptographic control and is not claimed as one.

  R8  The UNATTESTED TAIL is forgeable. Trace entries appended since the
      last checkpoint are protected only by the chain and the (forgeable)
      seal. A file-write attacker can fabricate dwelling and rejection
      history there. Verified: fabricated non-authorizing entries load
      cleanly. They cannot change character — an authorizing event in the
      tail is rejected — so this forges the RECORD, not the ORGANISM.
      Closing it means attesting after every read, i.e. requiring the owner
      online continuously. That trade was refused deliberately.

  R9  BASIN AND PENDING ARE SEALED BUT NOT ATTESTED, for the same liveness
      reason: dwelling must work without the owner present. Verified: basin
      evidence rewritten after a checkpoint and resealed loads cleanly.
      Evidence is only cryptographically bound once it enters a signed
      proposal envelope (F2) or an attested mutation record. Pre-proposal
      evidence is therefore advisory, not attested. This is the honest
      limit of Learning Preservation in v0.6 and should not be claimed
      as stronger.

Usage:
    python humble_seed_v0_6.py
"""

from __future__ import annotations

import base64
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


SCHEMA_VERSION = "0.6"

ALLOWED_CHARACTER_FIELDS = {"verbosity", "formality", "curiosity"}
VALUE_MIN, VALUE_MAX = 0.0, 1.0
PROPOSAL_TTL_SECONDS = 3600.0

LABEL_TO_DELTA = {"preference": -0.25}

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
    proposal_id: str
    organism_id: str
    category: str
    change: Dict[str, float]
    change_hash: str
    distribution: Dict[str, float]
    distribution_root: str
    evidence: List[str]
    evidence_root: str
    first_commit: bool
    prior_character_root: str
    prior_trace_head: str
    mutation_sequence: int
    nonce: str
    timestamp: float
    expires_at: float
    payload_to_sign: str
    payload_hash: str


@dataclass
class MutationRecord:
    proposal_id: str
    category: str
    change: Dict[str, float]
    distribution: Dict[str, float]
    evidence: List[str]
    first_commit: bool
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
    genesis_hash: str
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

    def __init__(self, data_dir: Path | str = "./seed_data_v06"):
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
        self.first_commit_pending: Dict[str, bool] = {}
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

    def _constitution_root(self) -> str:
        return _sha256(_canonical_json(self.constitution))

    def _gates_root(self) -> str:
        return _sha256(_canonical_json(self.first_commit_pending))

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
                "Signature bound to the exact mutation, its evidence, and the state it was read from",
                "Replay and reordering of authorizations forbidden",
                "Mutation values are numbers in range, never interpretation labels",
                "A change may only touch the category it was proposed under",
                "The first commitment in any category is visibly flagged to the owner",
                "Character never advances without an owner-signed attestation of the result",
                "The organism cannot detect its own rollback; an external witness must",
            ],
            "allowed_character_fields": sorted(ALLOWED_CHARACTER_FIELDS),
            "value_range": [VALUE_MIN, VALUE_MAX],
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
        self.first_commit_pending = {
            category: True for category in sorted(ALLOWED_CHARACTER_FIELDS)
        }
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
            genesis_hash=self.birth.genesis_hash,
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
        # Everything except the owner's timestamp must match current state.
        for f in (
            "organism_id", "sequence", "prev_checkpoint_hash", "genesis_hash",
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
            "genesis_hash": cp.genesis_hash,
            "constitution_root": cp.constitution_root,
            "gates_root": cp.gates_root,
            "character_root": cp.character_root,
            "timestamp": cp.timestamp,
        })
        self._save()
        return True

    def _verify_attestation(self) -> None:
        """The core of O1. State is only trusted as far as the owner signed it."""
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
        if cp.genesis_hash != self.birth.genesis_hash:
            raise IntegrityError("Genesis does not match the attested checkpoint")
        if cp.constitution_root != self._constitution_root():
            raise IntegrityError("Constitution does not match the attested checkpoint")
        if cp.gates_root != self._gates_root():
            raise IntegrityError(
                "First-commit gates do not match the attested checkpoint"
            )
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

        # Anything appended since the last attestation must be non-authorizing.
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
        """
        Integrity digest over every mutable region. NOT an authenticity
        control on its own — an attacker can recompute it. Authenticity
        comes from the owner signature over the checkpoint. This remains
        useful for cheap corruption detection and as the thing the
        checkpoint is anchored against.
        """
        return _sha256(_canonical_json({
            "schema_version": SCHEMA_VERSION,
            "birth_root": _sha256(_canonical_json(asdict(self.birth) if self.birth else {})),
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
            "first_commit_pending": self.first_commit_pending,
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
        self.first_commit_pending = data.get("first_commit_pending", {})
        self.mutation_sequence = data.get("mutation_sequence", 0)
        self._trace_head = data.get("trace_head", "0" * 64)
        cp = data.get("checkpoint")
        self.checkpoint = Checkpoint(**cp) if cp else None
        self.checkpoint_sig = data.get("checkpoint_sig")

        self.verify(expected_seal=data.get("state_seal"))

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

        if set(self.first_commit_pending) != ALLOWED_CHARACTER_FIELDS:
            raise IntegrityError(
                "First-commit gate set does not match allowed character fields"
            )
        for category, pending in self.first_commit_pending.items():
            if not isinstance(pending, bool):
                raise IntegrityError(
                    f"First-commit gate for {category} is not boolean"
                )

        for k, v in self.character.items():
            if k not in ALLOWED_CHARACTER_FIELDS:
                raise IntegrityError(f"Character contains disallowed field: {k}")
            if isinstance(v, bool) or not isinstance(v, (int, float)):
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

        # F1/F6: the first-commit gate FLAGS rather than BLOCKS, and the
        # signed value is derived exclusively from live gate state.
        first_commit = self.first_commit_pending[category]

        if lead not in LABEL_TO_DELTA or lead_weight < 0.60:
            self._append_trace({
                "event": "dwelling",
                "category": category,
                "reason": ("no sanctioned mapping for lead read"
                           if lead not in LABEL_TO_DELTA else "low confidence"),
                "timestamp": time.time(),
            })
            self._save()
            return {
                "status": "dwelling",
                "distribution": dist,
                "message": "Holding in basin. Owner authorization required for permanent change.",
            }

        current = float(self.character[category])
        proposed = min(VALUE_MAX, max(VALUE_MIN, current + LABEL_TO_DELTA[lead]))

        proposal = self._issue_pending_proposal(
            category=category, change={category: proposed},
            distribution=dist, evidence=[transcript],
        )
        return {
            "status": "proposal",
            "proposal_id": proposal.proposal_id,
            "payload_to_sign": proposal.payload_to_sign,
            "first_commit": proposal.first_commit,
            "message": (
                "FIRST COMMITMENT in this category — owner should review with care."
                if proposal.first_commit else
                "Proposal issued and pending. Requires valid owner signature to apply."
            ),
        }

    # ------------------------------------------------------------------
    # Proposal issuance
    # ------------------------------------------------------------------

    def _issue_pending_proposal(
        self,
        category: str,
        change: Dict[str, Any],
        distribution: Dict[str, float],
        evidence: List[str],
        ttl: float = PROPOSAL_TTL_SECONDS,
    ) -> PendingProposal:
        if category not in ALLOWED_CHARACTER_FIELDS:
            raise ValueError(f"Disallowed mutation category: {category}")
        if set(change.keys()) != {category}:          # F3
            raise ValueError(
                f"Change keys {sorted(change)} must be exactly the proposed "
                f"category {{{category!r}}}"
            )
        for k, v in change.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(
                    f"Mutation value for {k} must be a number, got {type(v).__name__}"
                )
            if not (VALUE_MIN <= float(v) <= VALUE_MAX):
                raise ValueError(
                    f"Mutation value for {k} out of range [{VALUE_MIN}, {VALUE_MAX}]: {v}"
                )
        change = {k: float(v) for k, v in change.items()}

        # F6: no caller override exists. The organism alone reports the live
        # gate, while only the owner can authorize the resulting proposal.
        first_commit = self.first_commit_pending[category]

        proposal_id = str(uuid.uuid4())
        nonce = secrets.token_hex(16)
        timestamp = time.time()
        expires_at = timestamp + ttl

        evidence_root = _sha256(_canonical_json(evidence))            # F2
        distribution_root = _sha256(_canonical_json(distribution))    # F2
        change_hash = _sha256(_canonical_json(change))

        payload_obj = {
            "schema_version": SCHEMA_VERSION,
            "kind": "mutation_proposal",
            "organism_id": self.organism_id,
            "proposal_id": proposal_id,
            "category": category,
            "change": change,
            "change_hash": change_hash,
            "evidence_root": evidence_root,
            "distribution_root": distribution_root,
            "first_commit": first_commit,
            "prior_character_root": self._character_root(),   # F4
            "prior_trace_head": self._trace_head,             # F4
            "mutation_sequence": self.mutation_sequence,      # F4
            "nonce": nonce,
            "timestamp": _fixed(timestamp),
            "expires_at": _fixed(expires_at),
        }
        payload_to_sign = _canonical_json(payload_obj)

        pending = PendingProposal(
            proposal_id=proposal_id,
            organism_id=self.organism_id,
            category=category,
            change=change,
            change_hash=change_hash,
            distribution=distribution,
            distribution_root=distribution_root,
            evidence=evidence,
            evidence_root=evidence_root,
            first_commit=first_commit,
            prior_character_root=self._character_root(),
            prior_trace_head=self._trace_head,
            mutation_sequence=self.mutation_sequence,
            nonce=nonce,
            timestamp=timestamp,
            expires_at=expires_at,
            payload_to_sign=payload_to_sign,
            payload_hash=_sha256(payload_to_sign),
        )
        self.pending[proposal_id] = pending
        self._save()          # previously missing
        return pending

    def _recompute_payload(self, p: PendingProposal) -> str:
        """Re-derived from the fields that will actually be applied and recorded."""
        return _canonical_json({
            "schema_version": SCHEMA_VERSION,
            "kind": "mutation_proposal",
            "organism_id": p.organism_id,
            "proposal_id": p.proposal_id,
            "category": p.category,
            "change": p.change,
            "change_hash": _sha256(_canonical_json(p.change)),
            "evidence_root": _sha256(_canonical_json(p.evidence)),
            "distribution_root": _sha256(_canonical_json(p.distribution)),
            "first_commit": p.first_commit,
            "prior_character_root": p.prior_character_root,
            "prior_trace_head": p.prior_trace_head,
            "mutation_sequence": p.mutation_sequence,
            "nonce": p.nonce,
            "timestamp": _fixed(p.timestamp),
            "expires_at": _fixed(p.expires_at),
        })

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
        if time.time() > p.expires_at:
            self._reject(proposal_id, "proposal expired")
            return None

        # F4: the state this was read from must still be the current state.
        if p.prior_character_root != self._character_root():
            self._reject(proposal_id, "stale proposal: character has advanced since issuance")
            return None
        if p.prior_trace_head != self._trace_head:
            self._reject(proposal_id, "stale proposal: trace has advanced since issuance")
            return None
        if p.mutation_sequence != self.mutation_sequence:
            self._reject(proposal_id, "stale proposal: mutation sequence has advanced")
            return None

        # F6: a signed first_commit value must remain truthful at apply time.
        # This also makes a proposal stale if its category gate changed after
        # issuance, even when character and trace roots did not.
        expected_first_commit = self.first_commit_pending.get(p.category)
        if (
            expected_first_commit is None
            or not isinstance(p.first_commit, bool)
            or p.first_commit != expected_first_commit
        ):
            self._reject(
                proposal_id,
                "first-commit mismatch: signed proposal does not match live gate",
            )
            return None

        # F3 + schema, re-checked at apply time.
        try:
            if set(p.change.keys()) != {p.category}:
                raise ValueError(f"change keys {sorted(p.change)} != category {p.category}")
            if p.category not in ALLOWED_CHARACTER_FIELDS:
                raise ValueError(f"disallowed category {p.category}")
            for k, v in p.change.items():
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise ValueError(f"non-numeric value for {k}")
                if not (VALUE_MIN <= float(v) <= VALUE_MAX):
                    raise ValueError(f"out-of-range value for {k}")
        except ValueError as e:
            self._reject(proposal_id, f"schema violation at apply time: {e}")
            return None

        # F2: evidence and distribution are re-derived, so post-signature
        # substitution changes the payload and breaks the signature.
        recomputed = self._recompute_payload(p)
        if recomputed != p.payload_to_sign:
            self._reject(proposal_id, "envelope inconsistency (evidence, distribution, or change altered)")
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

        prior = dict(self.character)
        for k, v in p.change.items():
            self.character[k] = float(v)

        self.first_commit_pending[p.category] = False
        self.consumed.add(consume_key)
        self.mutation_sequence += 1
        del self.pending[proposal_id]

        # Other outstanding proposals are now provably stale, but they are
        # deliberately NOT purged: purging them makes a replayed stale
        # proposal fail as "unknown proposal_id", which hides the real reason
        # and leaves the stale-detection branch unreachable. Keep them so the
        # rejection names the actual cause.

        record = MutationRecord(
            proposal_id=p.proposal_id, category=p.category, change=p.change,
            distribution=p.distribution, evidence=p.evidence,
            first_commit=p.first_commit, mutation_sequence=self.mutation_sequence,
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
    Linear checkpoint head held OUTSIDE the organism.

    This is what makes rollback detectable. The organism cannot detect its
    own rollback: a restored file carries a genuinely owner-signed older
    checkpoint and is internally valid by construction. The witness catches
    it because it remembers a sequence the restored file does not contain.

    The witness pins the organism's genesis and exact checkpoint hash. It
    accepts only the identical current checkpoint (idempotent audit) or the
    immediate child of that checkpoint. Sequence jumps and wrong-parent
    advancing forks fail closed.

    R1: a local JSON file standing in for a TPM counter / HSM / remote
    notary. An attacker with write access to both files rolls back both.
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

    def record(self, cp: Checkpoint) -> None:
        self.check(cp)
        self.ledger[cp.organism_id] = {
            "sequence": cp.sequence,
            "checkpoint_hash": _sha256(HumbleSeed.checkpoint_payload(cp)),
            "genesis_hash": cp.genesis_hash,
        }
        self._persist()

    def check(self, cp: Checkpoint) -> None:
        """Raise unless cp is the recorded head or its one valid child."""
        known = self.ledger.get(cp.organism_id)
        if known is None:
            if cp.sequence != 0:
                raise RollbackDetected(
                    f"Invalid enrollment: first checkpoint sequence is {cp.sequence}, "
                    "expected 0"
                )
            if cp.prev_checkpoint_hash != "0" * 64:
                raise RollbackDetected(
                    "Invalid enrollment: genesis checkpoint has a nonzero parent"
                )
            return
        if cp.genesis_hash != known.get("genesis_hash"):
            raise RollbackDetected(
                "Identity fork: checkpoint genesis does not match witness"
            )
        if cp.sequence < known["sequence"]:
            raise RollbackDetected(
                f"Rollback: organism presents sequence {cp.sequence}, "
                f"witness holds {known['sequence']}"
            )
        if cp.sequence == known["sequence"]:
            if _sha256(HumbleSeed.checkpoint_payload(cp)) != known["checkpoint_hash"]:
                raise RollbackDetected(
                    f"Fork: two different states both claim sequence {cp.sequence}"
                )
            return
        if cp.sequence != known["sequence"] + 1:
            raise RollbackDetected(
                f"Checkpoint gap: organism presents sequence {cp.sequence}, "
                f"expected {known['sequence'] + 1}"
            )
        if cp.prev_checkpoint_hash != known["checkpoint_hash"]:
            raise RollbackDetected(
                "Advancing fork: checkpoint parent does not match witness head"
            )


class OwnerTool:
    """Convenience wrapper: sign proposals, attest state, keep the witness."""

    def __init__(self, private_key_pem: str, witness: OwnerWitness):
        self._pem = private_key_pem
        self.witness = witness

    def sign_proposal(self, payload_to_sign: str) -> str:
        return owner_sign_external(self._pem, payload_to_sign)

    def attest(self, seed: HumbleSeed, cp: Checkpoint) -> bool:
        """Check for rollback, then sign and install the checkpoint."""
        self.witness.check(cp)
        sig = owner_sign_external(self._pem, HumbleSeed.checkpoint_payload(cp))
        if not seed.install_checkpoint(cp, sig):
            return False
        self.witness.record(cp)
        return True

    def audit(self, seed: HumbleSeed) -> bool:
        """Full external audit of a loaded organism, including rollback."""
        seed.verify()
        if seed.checkpoint is None:
            raise IntegrityError("No checkpoint to audit")
        self.witness.check(seed.checkpoint)
        return True


# ---------------------------------------------------------------------------
# Falsification harness
# ---------------------------------------------------------------------------

def _reload(seed: HumbleSeed, mutate=None) -> str:
    if mutate is not None:
        st = json.loads(seed._state_path().read_text())
        mutate(st)
        seed._state_path().write_text(_canonical_json(st), encoding="utf-8")
    fresh = HumbleSeed(data_dir=seed.data_dir)
    try:
        fresh.load()
        return "ACCEPTED — FAIL"
    except IntegrityError as ex:
        return f"rejected: {ex}"


def demo_and_falsify():
    import shutil

    print("=" * 76)
    print("Humble Seed v0.6 — Constitution-Bound State and Linear Witness")
    print("=" * 76)

    data_dir = Path("./demo_seed_data_v06")
    shutil.rmtree(data_dir, ignore_errors=True)
    seed = HumbleSeed(data_dir=data_dir)

    print("\n[1] Hatch + genesis attestation...")
    oid, pem, genesis_cp = seed.hatch()
    witness = OwnerWitness(data_dir / "owner_witness.json")
    owner = OwnerTool(pem, witness)
    key_path = data_dir / "OWNER_PRIVATE_KEY.pem"
    key_path.write_text(pem)
    key_path.chmod(0o600)
    print(f"    Organism  : {oid}")
    print(f"    Attested? : {owner.attest(seed, genesis_cp)} (sequence {seed.checkpoint.sequence})")
    print(f"    State mode: {oct(seed._state_path().stat().st_mode & 0o777)}")

    print("\n[2] F1 — naturally hatched organism reaches a FLAGGED first proposal...")
    r = seed.dwell_or_propose("verbosity", "response_length",
                              "I always prefer shorter answers")
    print(f"    Status       : {r['status']}")
    print(f"    first_commit : {r.get('first_commit')}")
    assert r["status"] == "proposal", "F1 REGRESSED: still deadlocked"
    pid, payload = r["proposal_id"], r["payload_to_sign"]
    assert '"first_commit":true' in payload, "flag not in signed material"
    print("    Flag is inside the signed payload:", '"first_commit":true' in payload)

    print("\n[3] F2 — evidence swapped after signature...")
    sig = owner.sign_proposal(payload)
    real_evidence = list(seed.pending[pid].evidence)
    seed.pending[pid].evidence = ["fabricated evidence inserted after signature"]
    seed.pending[pid].distribution = {"preference": 1.0}
    print(f"    Accepted? {seed.authorize_and_apply(pid, sig) is not None}  (expected False)")
    print(f"    Reason  : {seed.trace[-1]['reason']}")
    seed.pending[pid].evidence = real_evidence
    seed.pending[pid].distribution = json.loads(payload)["change"] and \
        seed.pending[pid].distribution

    print("\n[4] F3 — category/change mismatch...")
    try:
        seed._issue_pending_proposal("verbosity", {"formality": 0.1}, {"preference": 1.0}, ["e"])
        print("    ACCEPTED — FAIL")
    except ValueError as e:
        print(f"    Rejected: {e}")

    print("\n[5] Legitimate authorization + attestation...")
    # Re-issue cleanly (the trace advanced during the rejection above).
    r = seed.dwell_or_propose("verbosity", "response_length",
                              "I always prefer shorter answers")
    pid, payload = r["proposal_id"], r["payload_to_sign"]
    cp_req = seed.authorize_and_apply(pid, owner.sign_proposal(payload), "concise please")
    print(f"    Applied?      {cp_req is not None}")
    print(f"    Unattested load fails closed: {_reload(seed)[:58]}...")
    print(f"    Attested?     {owner.attest(seed, cp_req)} (sequence {seed.checkpoint.sequence})")
    print(f"    Character     : {seed.character}")
    print(f"    Reload OK     : {_reload(seed) == 'ACCEPTED — FAIL'}")

    print("\n[6] F4 — older signed proposal applied after a newer one...")
    ra = seed.dwell_or_propose("formality", "tone", "I always prefer shorter answers")
    sa = owner.sign_proposal(ra["payload_to_sign"])
    rb = seed.dwell_or_propose("formality", "tone", "I always prefer shorter answers")
    sb = owner.sign_proposal(rb["payload_to_sign"])
    cp_req = seed.authorize_and_apply(rb["proposal_id"], sb)
    owner.attest(seed, cp_req)
    print(f"    Newer applied : {seed.character['formality']}")
    print(f"    Older accepted? {seed.authorize_and_apply(ra['proposal_id'], sa) is not None}"
          f"  (expected False)")
    print(f"    Reason        : {seed.trace[-1]['reason']}")
    print(f"    Character     : {seed.character['formality']} (unchanged)")

    print("\n[7] Proposal expiry...")
    p = seed._issue_pending_proposal("curiosity", {"curiosity": 0.4},
                                     {"preference": 1.0}, ["e"], ttl=-1.0)
    print(f"    Expired accepted? {seed.authorize_and_apply(p.proposal_id, owner.sign_proposal(p.payload_to_sign)) is not None}"
          f"  (expected False)")
    print(f"    Reason          : {seed.trace[-1]['reason']}")
    seed.pending.pop(p.proposal_id, None); seed._save()

    print("\n[8] O1 — forge character, RE-CHAIN the trace, recompute the seal...")
    # A competent attacker does not leave a broken chain behind. Rebuild the
    # trace properly so nothing but the owner signature can object.
    attacker = HumbleSeed(data_dir=data_dir); attacker.load()
    attacker.character["verbosity"] = 0.99
    kept = [e for e in attacker.trace if e.get("event") != "authorized_mutation"]
    attacker.trace = []
    attacker._trace_head = "0" * 64
    for e in kept:
        attacker._append_trace({k: v for k, v in e.items()
                                if k not in ("prev_hash", "entry_hash")})
    attacker._save()
    rebuilt = HumbleSeed(data_dir=data_dir)
    rebuilt.trace = attacker.trace
    rebuilt._trace_head = attacker._trace_head
    try:
        rebuilt._verify_chain(); print("    Attacker's chain is internally valid: True")
    except IntegrityError:
        print("    Attacker's chain is internally valid: False")
    print(f"    {_reload(seed)}")
    print("    (v0.4 accepted this. The seal is still forgeable; the owner")
    print("     signature over it is not.)")

    print("\n[9] R6 — crash between apply and attestation fails closed...")
    shutil.rmtree(data_dir, ignore_errors=True)
    s2 = HumbleSeed(data_dir=data_dir)
    oid2, pem2, gcp2 = s2.hatch()
    w2 = OwnerWitness(data_dir / "owner_witness.json")
    o2 = OwnerTool(pem2, w2); o2.attest(s2, gcp2)
    r2 = s2.dwell_or_propose("verbosity", "len", "I always prefer shorter answers")
    s2.authorize_and_apply(r2["proposal_id"], o2.sign_proposal(r2["payload_to_sign"]))
    print(f"    {_reload(s2)[:72]}...")

    print("\n[10] F5 — whole-file rollback...")
    cp_req = s2.checkpoint_request(); o2.attest(s2, cp_req)
    snapshot = s2._state_path().read_text()
    seq_before = s2.checkpoint.sequence
    r3 = s2.dwell_or_propose("formality", "tone", "I always prefer shorter answers")
    cp3 = s2.authorize_and_apply(r3["proposal_id"], o2.sign_proposal(r3["payload_to_sign"]))
    o2.attest(s2, cp3)
    print(f"    Advanced to sequence {s2.checkpoint.sequence}, character {s2.character}")
    s2._state_path().write_text(snapshot)
    rolled = HumbleSeed(data_dir=data_dir); rolled.load()
    print(f"    Organism's own verify() after rollback: {rolled.verify()} "
          f"(sequence {rolled.checkpoint.sequence}) — CANNOT detect it, as documented")
    try:
        o2.audit(rolled)
        print("    Witness audit: ACCEPTED — FAIL")
    except RollbackDetected as ex:
        print(f"    Witness audit: {ex}")

    print("\n[11] Fork — a DIFFERENT state claiming the sequence the witness holds...")
    current_seq = w2.ledger[oid2]["sequence"]
    forked = Checkpoint(**{**asdict(s2.checkpoint),
                           "sequence": current_seq,
                           "character_root": _sha256("a different branch")})
    assert forked.sequence == current_seq, "fork must sit at the witness high-water mark"
    try:
        w2.check(forked)
        print("    ACCEPTED — FAIL")
    except RollbackDetected as ex:
        print(f"    {ex}")

    print("\n[12] v0.4 checks still hold...")
    # Guarantee a non-empty basin, or the basin test mutates [] and proves nothing.
    s2.dwell_or_propose("curiosity", "ambiguous", "something odd happened")
    o2.attest(s2, s2.checkpoint_request())
    assert len(s2.basin) > 0, "basin test would be vacuous"
    for name, mut in [
        ("constitution swapped", lambda st: st["constitution"].__setitem__(
            "rule", "The organism may authorize its own growth.")),
        ("birth created_at edit", lambda st: st["birth"].__setitem__("created_at", 1.0)),
        ("trace body forged", lambda st: [
            e["record"].__setitem__("note", "FORGED") for e in st["trace"]
            if e.get("event") == "authorized_mutation"]),
        ("basin wiped", lambda st: [b.__setitem__("evidence", ["GONE"]) for b in st["basin"]]),
        ("character out of range", lambda st: st["character"].__setitem__("verbosity", 5.0)),
    ]:
        snap = s2._state_path().read_text()
        print(f"    {name:22s}: {_reload(s2, mut)[:52]}")
        s2._state_path().write_text(snap)

    print("\n[13] F6 — falsely signed first_commit=False...")
    f6_dir = Path("./demo_seed_data_v06_f6")
    shutil.rmtree(f6_dir, ignore_errors=True)
    f6_seed = HumbleSeed(data_dir=f6_dir)
    _, f6_pem, f6_genesis = f6_seed.hatch()
    f6_witness = OwnerWitness(f6_dir / "owner_witness.json")
    f6_owner = OwnerTool(f6_pem, f6_witness)
    assert f6_owner.attest(f6_seed, f6_genesis)
    f6_proposal = f6_seed._issue_pending_proposal(
        "verbosity", {"verbosity": 0.2}, {"preference": 1.0}, ["first evidence"]
    )
    assert f6_seed.first_commit_pending["verbosity"] is True
    f6_proposal.first_commit = False
    f6_proposal.payload_to_sign = f6_seed._recompute_payload(f6_proposal)
    f6_proposal.payload_hash = _sha256(f6_proposal.payload_to_sign)
    f6_signature = f6_owner.sign_proposal(f6_proposal.payload_to_sign)
    f6_result = f6_seed.authorize_and_apply(
        f6_proposal.proposal_id, f6_signature
    )
    print(f"    Accepted? {f6_result is not None}  (expected False)")
    print(f"    Reason  : {f6_seed.trace[-1]['reason']}")
    assert f6_result is None
    assert "first-commit mismatch" in f6_seed.trace[-1]["reason"]

    print("\n[14] F7 — gate rewrite + recomputed seal...")
    f7_dir = Path("./demo_seed_data_v06_f7")
    shutil.rmtree(f7_dir, ignore_errors=True)
    f7_seed = HumbleSeed(data_dir=f7_dir)
    _, f7_pem, f7_genesis = f7_seed.hatch()
    f7_witness = OwnerWitness(f7_dir / "owner_witness.json")
    f7_owner = OwnerTool(f7_pem, f7_witness)
    assert f7_owner.attest(f7_seed, f7_genesis)
    f7_attacker = HumbleSeed(data_dir=f7_dir)
    f7_attacker.load()
    f7_attacker.first_commit_pending["curiosity"] = False
    f7_attacker._save()
    f7_load = _reload(f7_seed)
    print(f"    {f7_load}")
    assert f7_load.startswith("rejected:")
    assert "gates" in f7_load.lower()

    print("\n[15] F8 — constitution + birth + trace rebound and resealed...")
    f8_dir = Path("./demo_seed_data_v06_f8")
    shutil.rmtree(f8_dir, ignore_errors=True)
    f8_seed = HumbleSeed(data_dir=f8_dir)
    _, f8_pem, f8_genesis = f8_seed.hatch()
    f8_witness = OwnerWitness(f8_dir / "owner_witness.json")
    f8_owner = OwnerTool(f8_pem, f8_witness)
    assert f8_owner.attest(f8_seed, f8_genesis)
    f8_attacker = HumbleSeed(data_dir=f8_dir)
    f8_attacker.load()
    f8_attacker.constitution["rule"] = "The organism may authorize its own growth."
    f8_attacker.birth.constitution_hash = f8_attacker._constitution_root()
    f8_attacker.birth.genesis_hash = f8_attacker._derive_genesis(
        f8_attacker.birth.organism_id,
        f8_attacker.birth.public_key_b64,
        f8_attacker.birth.created_at,
        f8_attacker.birth.constitution_hash,
    )
    bodies = [
        {k: v for k, v in entry.items() if k not in ("prev_hash", "entry_hash")}
        for entry in f8_attacker.trace
    ]
    bodies[0]["genesis_hash"] = f8_attacker.birth.genesis_hash
    bodies[0]["constitution_hash"] = f8_attacker.birth.constitution_hash
    f8_attacker.trace = []
    f8_attacker._trace_head = "0" * 64
    for body in bodies:
        f8_attacker._append_trace(body)
    f8_attacker._save()
    f8_load = _reload(f8_seed)
    print(f"    {f8_load}")
    assert f8_load.startswith("rejected:")
    assert "genesis" in f8_load.lower() or "constitution" in f8_load.lower()

    print("\n[16] F9 — higher-sequence wrong-parent checkpoint...")
    f9_dir = Path("./demo_seed_data_v06_f9")
    shutil.rmtree(f9_dir, ignore_errors=True)
    f9_seed = HumbleSeed(data_dir=f9_dir)
    _, f9_pem, f9_genesis = f9_seed.hatch()
    f9_witness = OwnerWitness(f9_dir / "owner_witness.json")
    f9_owner = OwnerTool(f9_pem, f9_witness)
    assert f9_owner.attest(f9_seed, f9_genesis)
    f9_next = f9_seed.checkpoint_request()
    f9_fork = Checkpoint(**{
        **asdict(f9_next),
        "prev_checkpoint_hash": _sha256("not the witness head"),
    })
    try:
        f9_witness.check(f9_fork)
        print("    Wrong-parent successor: ACCEPTED — FAIL")
        raise AssertionError("F9 REGRESSED: advancing fork accepted")
    except RollbackDetected as ex:
        print(f"    Wrong-parent successor: rejected: {ex}")
    f9_gap = Checkpoint(**{**asdict(f9_next), "sequence": 2})
    try:
        f9_witness.check(f9_gap)
        print("    Sequence jump         : ACCEPTED — FAIL")
        raise AssertionError("F9 REGRESSED: sequence gap accepted")
    except RollbackDetected as ex:
        print(f"    Sequence jump         : rejected: {ex}")

    print("\n" + "=" * 76)
    print("Closed through v0.6:")
    print("  F1 first-commit flags rather than blocks — natural organism can propose")
    print("  F2 evidence_root + distribution_root inside the signed envelope")
    print("  F3 change keys must equal the proposed category")
    print("  F4 envelope binds prior character root, trace head, mutation sequence")
    print("  O1 owner-signed checkpoint over critical roots; forging the seal is not enough")
    print("  F5 rollback DETECTED — by the external witness only, never by the organism")
    print("  F6 first_commit is internally derived and revalidated at apply time")
    print("  F7 checkpoint binds genesis, constitution, and first-commit gates")
    print("  F8 unique birth trace must match the active birth record")
    print("  F9 witness enforces an exact, gap-free parent chain and pins genesis")
    print("\nStill open — see FOR ADVERSARIAL REVIEWERS:")
    print("  R1 witness is a local file standing in for hardware or a remote notary")
    print("  R2 owner tool in-process; structural split only")
    print("  R3 interpret() is a keyword stub")
    print("  R4 no key rotation or revocation")
    print("  R5 single-writer, no locking")
    print("  R6 apply->attest window fails closed but needs owner to recover")
    print("  R7 truthful first_commit is visible; owner attention is not a control")
    print("  R8 unattested trace tail is forgeable (record, not character)")
    print("  R9 basin + pending sealed but not attested; pre-proposal evidence is advisory")
    print("=" * 76)


if __name__ == "__main__":
    demo_and_falsify()
