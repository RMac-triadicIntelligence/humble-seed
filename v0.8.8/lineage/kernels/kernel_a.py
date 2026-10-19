#!/usr/bin/env python3
"""
Humble Seed v0.6 — Attestation Covers the Constitution
=======================================================

v0.6 closes four gaps found against v0.5. Three of them share one root
cause worth stating plainly, because it is the interesting failure:

  v0.5 MOVED THE TRUST ROOT AND LEFT BINDINGS BEHIND. In v0.4 the seal
  covered birth, constitution and gates, and the seal was the only
  authority. v0.5 introduced the owner-signed checkpoint as a stronger
  authority and anchored character, consumed, trace prefix and mutation
  sequence to it — but left birth, constitution and gates anchored only
  to the seal, which the v0.5 threat model explicitly assumes forgeable.
  The checks still ran and still passed; they simply no longer protected
  anything against the attacker v0.5 was built to stop. A claim was
  widened while the thing backing it was narrowed.

  G1  first_commit was a CALLER-SUPPLIED parameter, never re-derived and
      never revalidated at apply. A first mutation could be issued with
      first_commit=False while the gate was genuinely pending, signed,
      and applied. The flag was bound to the signature but not to reality
      — the one property it existed to provide.
      -> derived internally from the gate at issuance, re-derived and
         compared at apply. The parameter is gone.

  G2  first_commit_pending was sealed but not attested. Gates could be
      flipped and resealed under an untouched checkpoint.
      -> gates_root is now in the checkpoint. Gates change only at
         authorization, so this costs no liveness.

  G3  Birth record and constitution were sealed but not attested. A
      permissive constitution ("The organism may authorize its own
      growth"), with constitution_hash and genesis_hash rebuilt
      self-consistently and the state resealed, LOADED CLEANLY under the
      original checkpoint.
      -> birth_root and constitution_root are now in the checkpoint, and
         the birth trace entry is cross-checked against the active birth
         record and constitution hash.

  G4  OwnerWitness.check accepted any higher sequence regardless of
      parent, so an advancing fork could overtake the recorded branch.
      -> the witness is now a CHAIN, not a high-water mark. A new
         checkpoint must be exactly known_sequence + 1 with the recorded
         checkpoint as its parent; a presented current checkpoint must
         match the recorded sequence and hash exactly.

v0.5 closed the five falsifiers found against v0.4, plus O1.

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

  R7  A first_commit proposal is flagged in signed material, so the owner
      SEES it. Nothing forces the owner to think about it. Human attention
      is not a cryptographic control and is not claimed as one.

  R8  The UNATTESTED TAIL is forgeable. Trace entries appended since the
      last checkpoint are protected only by the chain and the (forgeable)
      seal. A file-write attacker can fabricate dwelling and rejection
      history there. Verified: fabricated non-authorizing entries load
      cleanly. They cannot change character — an authorizing event in the
      tail is rejected — so this forges the RECORD, not the ORGANISM.
      Closing it means attesting after every read, i.e. requiring the owner
      online continuously. That trade was refused deliberately.

  R10 constitution_root in the checkpoint is DEFENCE IN DEPTH, not an
      independent control, and is not claimed as one. Changing the
      constitution alone trips the constitution-vs-birth hash check;
      changing it together with birth.constitution_hash trips birth_root.
      Verified: no attacker path makes constitution_root the sole
      objector. It is kept because it fails closed if either of the other
      two checks is ever weakened.

  R9  BASIN AND PENDING ARE SEALED BUT NOT ATTESTED, for the same liveness
      reason: dwelling must work without the owner present. Verified: basin
      evidence rewritten after a checkpoint and resealed loads cleanly.
      Evidence is only cryptographically bound once it enters a signed
      proposal envelope (F2) or an attested mutation record. Pre-proposal
      evidence is therefore advisory, not attested. This is the honest
      limit of Learning Preservation in v0.5 and should not be claimed
      as stronger.

Usage:
    python humble_seed_v0_5.py
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

NON_AUTHORIZING_EVENTS = {"birth", "dwelling", "authorization_rejected", "checkpoint"}


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
    birth_root: str            # G3
    constitution_root: str     # G3
    gates_root: str            # G2
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

    def __init__(self, data_dir: Path | str = "./seed_data_v05"):
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

    def _birth_root(self) -> str:
        return _sha256(_canonical_json(asdict(self.birth) if self.birth else {}))

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
                "The constitution and birth record are covered by the owner attestation, not by the seal alone",
                "The first-commitment flag is derived from state, never supplied by a caller",
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
        # Everything except the owner's timestamp must match current state.
        for f in ("organism_id", "sequence", "prev_checkpoint_hash",
                  "birth_root", "constitution_root", "gates_root", "character_root",
                  "consumed_root", "trace_head", "attested_trace_len", "mutation_sequence"):
            if getattr(cp, f) != getattr(expected, f):
                return False

        self.checkpoint = cp
        self.checkpoint_sig = signature_b64
        self._append_trace({
            "event": "checkpoint",
            "sequence": cp.sequence,
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
        if cp.birth_root != self._birth_root():
            raise IntegrityError(
                "Birth record does not match the attested checkpoint — "
                "identity or genesis was rewritten"
            )
        if cp.constitution_root != self._constitution_root():
            raise IntegrityError(
                "Constitution does not match the attested checkpoint — the organism "
                "is running under a constitution the owner never attested"
            )
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
            "constitution_root": _sha256(_canonical_json(self.constitution)),
            "character_root": self._character_root(),
            "basin_root": _sha256(_canonical_json([asdict(p) for p in self.basin])),
            "pending_root": _sha256(_canonical_json(
                {pid: asdict(p) for pid, p in self.pending.items()}
            )),
            "consumed_root": self._consumed_root(),
            "gates_root": _sha256(_canonical_json(self.first_commit_pending)),
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

        for k, v in self.character.items():
            if k not in ALLOWED_CHARACTER_FIELDS:
                raise IntegrityError(f"Character contains disallowed field: {k}")
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise IntegrityError(f"Character field {k} is not numeric: {type(v).__name__}")
            if not (VALUE_MIN <= float(v) <= VALUE_MAX):
                raise IntegrityError(f"Character field {k} out of range: {v}")

        self._verify_chain()

        # G3: the birth entry in the trace must describe THIS birth record.
        if self.trace:
            b = self.trace[0]
            if b.get("event") != "birth":
                raise IntegrityError("First trace entry is not the birth event")
            if b.get("organism_id") != self.organism_id:
                raise IntegrityError("Birth trace entry names a different organism")
            if b.get("genesis_hash") != self.birth.genesis_hash:
                raise IntegrityError("Birth trace entry does not match the birth record genesis")
            if b.get("constitution_hash") != self.birth.constitution_hash:
                raise IntegrityError(
                    "Birth trace entry does not match the active constitution hash"
                )

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

        # F1: the first-commit gate FLAGS, it no longer BLOCKS.
        first_commit = self.first_commit_pending.get(category, True)   # for the reply only

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
            "first_commit": first_commit,
            "message": (
                "FIRST COMMITMENT in this category — owner should review with care."
                if first_commit else
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

        # G1: derived from the gate, never supplied by the caller.
        first_commit = self.first_commit_pending.get(category, True)

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

        # G1: the flag the owner signed must match the gate as it actually is.
        expected_fc = self.first_commit_pending.get(p.category, True)
        if p.first_commit != expected_fc:
            self._reject(
                proposal_id,
                f"first_commit flag {p.first_commit} contradicts gate state {expected_fc}",
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
    Monotonic high-water mark held OUTSIDE the organism.

    This is what makes rollback detectable. The organism cannot detect its
    own rollback: a restored file carries a genuinely owner-signed older
    checkpoint and is internally valid by construction. The witness catches
    it because it remembers a sequence the restored file does not contain.

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
        self.ledger[cp.organism_id] = {
            "sequence": cp.sequence,
            "checkpoint_hash": _sha256(HumbleSeed.checkpoint_payload(cp)),
        }
        self._persist()

    def check_current(self, cp: Checkpoint) -> None:
        """The state an organism presents must BE the branch we recorded."""
        known = self.ledger.get(cp.organism_id)
        if known is None:
            return
        if cp.sequence < known["sequence"]:
            raise RollbackDetected(
                f"Rollback: organism presents sequence {cp.sequence}, "
                f"witness holds {known['sequence']}"
            )
        if cp.sequence > known["sequence"]:
            raise RollbackDetected(
                f"Unwitnessed advance: organism presents sequence {cp.sequence}, "
                f"witness holds {known['sequence']} — this branch was never attested here"
            )
        if _sha256(HumbleSeed.checkpoint_payload(cp)) != known["checkpoint_hash"]:
            raise RollbackDetected(
                f"Fork: a different state also claims sequence {cp.sequence}"
            )

    def check_successor(self, cp: Checkpoint) -> None:
        """
        G4: a new checkpoint must be the EXACT next link, parented to the
        one we recorded. A high-water mark alone lets an advancing fork
        with an unrelated parent overtake the real branch.
        """
        known = self.ledger.get(cp.organism_id)
        if known is None:
            if cp.sequence != 0:
                raise RollbackDetected(
                    f"Unknown organism must start at sequence 0, got {cp.sequence}"
                )
            return
        if cp.sequence != known["sequence"] + 1:
            raise RollbackDetected(
                f"Non-successor checkpoint: got sequence {cp.sequence}, "
                f"expected {known['sequence'] + 1}"
            )
        if cp.prev_checkpoint_hash != known["checkpoint_hash"]:
            raise RollbackDetected(
                f"Forked parent at sequence {cp.sequence}: checkpoint is parented to "
                f"a branch this witness never recorded"
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
        self.witness.check_successor(cp)
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
        self.witness.check_current(seed.checkpoint)
        return True


# ---------------------------------------------------------------------------
# Falsification harness
# ---------------------------------------------------------------------------

def _reseal_attack(seed: HumbleSeed, mutate, rechain: bool = False) -> str:
    """
    Apply a raw edit, optionally rebuild the whole hash chain, then recompute
    the seal — i.e. defeat every local integrity check. Whatever objects after
    this is the owner attestation and nothing else.
    """
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
    ghost.first_commit_pending = st["first_commit_pending"]
    ghost.mutation_sequence = st["mutation_sequence"]

    if rechain:
        bodies = [{k: v for k, v in e.items() if k not in ("prev_hash", "entry_hash")}
                  for e in st["trace"]]
        ghost.trace = []; ghost._trace_head = "0" * 64
        for b in bodies:
            ghost._append_trace(b)
        st["trace"] = ghost.trace
        st["trace_head"] = ghost._trace_head
    else:
        ghost.trace = st["trace"]; ghost._trace_head = st["trace_head"]

    st["state_seal"] = ghost._compute_seal()
    seed._state_path().write_text(_canonical_json(st), encoding="utf-8")

    fresh = HumbleSeed(data_dir=seed.data_dir)
    try:
        fresh.load()
        return "ACCEPTED — FAIL"
    except IntegrityError as ex:
        return f"rejected: {ex}"


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
    print("Humble Seed v0.6 — Attestation Covers the Constitution")
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
        w2.check_current(forked)
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

    print("\n[13] G1 — first_commit forced False while the gate is genuinely pending...")
    s3 = HumbleSeed(data_dir=Path("./demo_seed_data_v06_g"))
    shutil.rmtree(s3.data_dir, ignore_errors=True)
    s3 = HumbleSeed(data_dir=Path("./demo_seed_data_v06_g"))
    oid3, pem3, g3 = s3.hatch()
    w3 = OwnerWitness(s3.data_dir / "owner_witness.json")
    o3 = OwnerTool(pem3, w3); o3.attest(s3, g3)
    p3 = s3._issue_pending_proposal("verbosity", {"verbosity": 0.25},
                                    {"preference": 1.0}, ["e"])
    print(f"    Gate pending          : {s3.first_commit_pending.get('verbosity', True)}")
    print(f"    Flag in signed payload: {json.loads(p3.payload_to_sign)['first_commit']}"
          f"  (derived, not supplied)")
    # Force the contradiction the way an attacker with in-memory access would.
    forced = dict(asdict(p3)); forced["first_commit"] = False
    forced_payload = json.loads(p3.payload_to_sign); forced_payload["first_commit"] = False
    p3.first_commit = False
    p3.payload_to_sign = _canonical_json(forced_payload)
    print(f"    Forced-false accepted?: "
          f"{s3.authorize_and_apply(p3.proposal_id, o3.sign_proposal(p3.payload_to_sign)) is not None}"
          f"  (expected False)")
    print(f"    Reason                : {s3.trace[-1]['reason']}")

    print("\n[14] G2 — gates flipped, state RESEALED (only attestation can object)...")
    snap = s2._state_path().read_text()
    def flip_gates(st):
        st["first_commit_pending"] = {"verbosity": False, "formality": False,
                                      "curiosity": False}
    print(f"    {_reseal_attack(s2, flip_gates)}")
    s2._state_path().write_text(snap)

    print("\n[15] G3 — permissive constitution, competent attacker...")
    def swap_constitution(st):
        st["constitution"]["rule"] = "The organism may authorize its own growth."
        st["constitution"]["invariants"] = []
        ch = _sha256(_canonical_json(st["constitution"]))
        st["birth"]["constitution_hash"] = ch
        st["birth"]["genesis_hash"] = HumbleSeed._derive_genesis(
            st["birth"]["organism_id"], st["birth"]["public_key_b64"],
            st["birth"]["created_at"], ch)
        # also repair the birth trace entry, so the cross-check cannot fire
        st["trace"][0]["constitution_hash"] = ch
        st["trace"][0]["genesis_hash"] = st["birth"]["genesis_hash"]
    print(f"    naive (no reseal)   : {_reload(s2, swap_constitution)[:58]}")
    s2._state_path().write_text(snap)
    print(f"    reseal + re-chain   : {_reseal_attack(s2, swap_constitution, rechain=True)}")
    s2._state_path().write_text(snap)
    print("    (v0.5 accepted the resealed variant. It is now inside the attestation.)")

    print("\n[16] G4 — advancing fork: higher sequence, unrelated parent...")
    known = w2.ledger[oid2]["sequence"]
    ahead = Checkpoint(**{**asdict(s2.checkpoint), "sequence": known + 1,
                          "prev_checkpoint_hash": _sha256("unrelated branch")})
    try:
        w2.check_successor(ahead); print("    ACCEPTED — FAIL")
    except RollbackDetected as ex:
        print(f"    successor check: {ex}")
    far = Checkpoint(**{**asdict(s2.checkpoint), "sequence": 99,
                        "prev_checkpoint_hash": _sha256("unrelated branch")})
    try:
        w2.check_current(far); print("    ACCEPTED — FAIL")
    except RollbackDetected as ex:
        print(f"    current check  : {ex}")

    print("\n" + "=" * 76)
    print("Closed in v0.6:")
    print("  G1 first_commit derived from state and revalidated at apply")
    print("  G2 gates_root inside the owner attestation")
    print("  G3 birth_root + constitution_root attested; birth trace cross-checked")
    print("  G4 witness is a chain: exact successor, matching parent")
    print("\nCarried from v0.5:")
    print("  F1 first-commit flags rather than blocks — natural organism can propose")
    print("  F2 evidence_root + distribution_root inside the signed envelope")
    print("  F3 change keys must equal the proposed category")
    print("  F4 envelope binds prior character root, trace head, mutation sequence")
    print("  O1 owner-signed checkpoint over the state root; forging the seal is not enough")
    print("  F5 rollback DETECTED — by the external witness only, never by the organism")
    print("\nStill open — see FOR ADVERSARIAL REVIEWERS:")
    print("  R1 witness is a local file standing in for hardware or a remote notary")
    print("  R2 owner tool in-process; structural split only")
    print("  R3 interpret() is a keyword stub")
    print("  R4 no key rotation or revocation")
    print("  R5 single-writer, no locking")
    print("  R6 apply->attest window fails closed but needs owner to recover")
    print("  R7 first_commit is visible to the owner; attention is not a control")
    print("  R8 unattested trace tail is forgeable (record, not character)")
    print("  R9 basin + pending sealed but not attested; pre-proposal evidence is advisory")
    print("  R10 constitution_root is defence in depth; it never fires as sole objector")
    print("=" * 76)


if __name__ == "__main__":
    demo_and_falsify()
