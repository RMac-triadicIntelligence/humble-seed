#!/usr/bin/env python3
"""
Humble Seed v0.4 — Full-Coverage Seal, Genesis Re-derivation, Constitution Binding
==================================================================================

Changes from v0.3 (each closes a defect found by adversarial probe):

  D1  pending_root hashed only proposal *keys*. A pending proposal's change
      and evidence could be rewritten in the state file with no seal change.
      -> seal now covers the full canonical pending map.

  D2  basin was not sealed at all. Pre-authorization evidence (the Learning
      Preservation store) could be silently wiped.
      -> seal now covers the full canonical basin.

  D3  birth.constitution_hash and birth.created_at were unsealed, and
      genesis_hash was never re-derived on load. The constitution binding
      was decorative at rest, and the constitution text was never persisted
      at all, so nothing could be checked against it.
      -> constitution object is now persisted; load() re-derives
         constitution_hash from it, re-derives genesis_hash from the birth
         fields, and seals the whole birth record.

  D4  owner_sign was a static method on the organism class, asserting an
      isolation property nothing enforced.
      -> moved out of the class entirely into a separate OWNER TOOL section.
         HumbleSeed now has no signing capability anywhere in its namespace.

  D5  State writes were non-atomic; a partial write corrupts a sealed store.
      -> tmp file + os.replace.

  D6  Harness weaknesses: [7] deliberately corrupted entry_hash (trivial
      case) and [6] never reached the consumed-ledger branch.
      -> both now exercise the real path.


FOR ADVERSARIAL REVIEWERS  (Grok / GPT / anyone)
------------------------------------------------
Known-open, deliberately not claimed as closed:

  O1  The state seal is an UNKEYED hash of public material. An attacker who
      can write organism_state.json and recompute _compute_seal() can forge
      any sealed field. This detects corruption and naive edits, NOT a
      motivated tamperer. Closing it requires an HMAC under a key the
      organism does not hold, or an owner signature over the state root.
      Everything below O1 is conditional on O1.

  O2  owner_sign_external() still runs in the same process as the organism
      in this prototype. Physical separation (separate process, hardware
      token) is the real fix; the split here is structural, not enforced.

  O3  interpret() is a keyword-matching stub, not an inference model. The
      confidence numbers it emits are decorative. Do not attack it as if it
      were the real thing; do attack what the rest of the system does with
      whatever numbers it produces.

  O4  No key rotation, no revocation, no expiry on pending proposals.

  O5  Single-writer assumption. No file locking; concurrent instances on the
      same data_dir will clobber each other.

Attacks worth trying that are NOT on that list are the interesting ones.

Usage:
    python humble_seed_v0_4.py
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


SCHEMA_VERSION = "0.4"

# The only fields the organism may ever mutate, and their legal range.
ALLOWED_CHARACTER_FIELDS = {"verbosity", "formality", "curiosity"}
VALUE_MIN, VALUE_MAX = 0.0, 1.0

# Interpretation labels are NOT values. This is the only sanctioned bridge
# from a read to a proposed numeric change.
LABEL_TO_DELTA = {
    "preference": -0.25,   # honour the stated preference, move toward it
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canonical_json(obj: Any) -> str:
    """Deterministic serialization used for all hashes and signed payloads."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _fixed(t: float) -> str:
    """Stable textual form for timestamps used inside hashed/signed material."""
    return f"{t:.6f}"


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
    proposal_id: Optional[str] = None


@dataclass
class PendingProposal:
    proposal_id: str
    organism_id: str
    category: str
    change: Dict[str, Any]
    change_hash: str
    distribution: Dict[str, float]
    evidence: List[str]
    nonce: str
    timestamp: float
    payload_to_sign: str
    payload_hash: str


@dataclass
class MutationRecord:
    proposal_id: str
    category: str
    change: Dict[str, Any]
    distribution: Dict[str, float]
    evidence: List[str]
    authorized_at: float
    signature_b64: str
    prior_character_snapshot: Dict[str, Any]
    note: str = ""


class IntegrityError(RuntimeError):
    """Raised when persisted state fails any structural check."""


# ---------------------------------------------------------------------------
# The organism
#
# NOTE: this class contains NO code path that can produce a signature.
# Search it for "sign" — the only hits are verification and stored material.
# ---------------------------------------------------------------------------

class HumbleSeed:

    def __init__(self, data_dir: Path | str = "./seed_data_v04"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.organism_id: Optional[str] = None
        self.public_key: Optional[Ed25519PublicKey] = None
        self.birth: Optional[BirthRecord] = None
        self.constitution: Dict[str, Any] = {}
        self.character: Dict[str, Any] = {}
        self.basin: List[PreTrace] = []
        self.pending: Dict[str, PendingProposal] = {}
        self.consumed: Set[str] = set()
        self.trace: List[Dict[str, Any]] = []
        self.first_commit_pending: Dict[str, bool] = {}
        self._trace_head: str = "0" * 64

    # ------------------------------------------------------------------
    # Birth
    # ------------------------------------------------------------------

    def hatch(self) -> Tuple[str, str]:
        if self.organism_id is not None:
            raise RuntimeError("This seed has already hatched.")

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_raw = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        public_b64 = base64.urlsafe_b64encode(public_raw).decode("ascii")

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
                "Signature bound to exact mutation that will be applied",
                "Replay of authorizations forbidden",
                "Mutation values are numbers in range, never interpretation labels",
                "Constitution under which the organism was born is verifiable at rest",
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
        self.basin = []
        self.pending = {}
        self.consumed = set()
        self.first_commit_pending = {}
        self._trace_head = "0" * 64

        self._append_trace({
            "event": "birth",
            "organism_id": organism_id,
            "genesis_hash": genesis_hash,
            "constitution_hash": constitution_hash,
            "timestamp": created_at,
        })

        del private_key
        self._save()
        return organism_id, private_pem.decode("ascii")

    @staticmethod
    def _derive_genesis(
        organism_id: str, public_b64: str, created_at: float, constitution_hash: str
    ) -> str:
        """Deterministic — must be reproducible on every load. (D3)"""
        return _sha256("|".join([
            organism_id, public_b64, _fixed(created_at), constitution_hash
        ]))

    # ------------------------------------------------------------------
    # Hash-chained trace
    # ------------------------------------------------------------------

    def _append_trace(self, entry: Dict[str, Any]) -> None:
        entry = dict(entry)
        entry["prev_hash"] = self._trace_head
        entry_hash = _sha256(_canonical_json(entry))
        entry["entry_hash"] = entry_hash
        self.trace.append(entry)
        self._trace_head = entry_hash

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
    # Integrity seal — now covers every mutable region of state
    # ------------------------------------------------------------------

    def _compute_seal(self) -> str:
        """
        Coverage: birth record (whole), constitution, character, basin,
        pending (whole, not just keys), consumed, gates, trace head.

        HONEST LIMIT (O1): unkeyed hash of public material. Detects
        corruption and naive edits. An attacker who recomputes this seal
        forges freely. Replace with HMAC under an external key, or an
        owner signature over this digest, for anti-tamper.
        """
        material = {
            "schema_version": SCHEMA_VERSION,
            "birth_root": _sha256(_canonical_json(asdict(self.birth) if self.birth else {})),
            "constitution_root": _sha256(_canonical_json(self.constitution)),
            "character_root": _sha256(_canonical_json(self.character)),
            "basin_root": _sha256(_canonical_json([asdict(p) for p in self.basin])),   # D2
            "pending_root": _sha256(_canonical_json(                                   # D1
                {pid: asdict(p) for pid, p in self.pending.items()}
            )),
            "consumed_root": _sha256(_canonical_json(sorted(self.consumed))),
            "gates_root": _sha256(_canonical_json(self.first_commit_pending)),
            "trace_head": self._trace_head,
        }
        return _sha256(_canonical_json(material))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _state_path(self) -> Path:
        return self.data_dir / "organism_state.json"

    def _save(self) -> None:
        if self.organism_id is None or self.birth is None:
            return
        state = {
            "schema_version": SCHEMA_VERSION,
            "organism_id": self.organism_id,
            "birth": asdict(self.birth),
            "constitution": self.constitution,          # D3: persist the text, not just its hash
            "character": self.character,
            "basin": [asdict(p) for p in self.basin],
            "pending": {pid: asdict(p) for pid, p in self.pending.items()},
            "consumed": sorted(self.consumed),
            "trace": self.trace,
            "first_commit_pending": self.first_commit_pending,
            "trace_head": self._trace_head,
            "state_seal": self._compute_seal(),
        }
        # D5: atomic write — never leave a half-written sealed store
        tmp = self._state_path().with_suffix(".json.tmp")
        tmp.write_text(_canonical_json(state), encoding="utf-8")
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
        public_raw = base64.urlsafe_b64decode(self.birth.public_key_b64)
        self.public_key = Ed25519PublicKey.from_public_bytes(public_raw)
        self.constitution = data.get("constitution", {})
        self.character = data["character"]
        self.basin = [PreTrace(**p) for p in data["basin"]]
        self.pending = {pid: PendingProposal(**p) for pid, p in data.get("pending", {}).items()}
        self.consumed = set(data.get("consumed", []))
        self.trace = data["trace"]
        self.first_commit_pending = data.get("first_commit_pending", {})
        self._trace_head = data.get("trace_head", "0" * 64)

        self.verify(expected_seal=data.get("state_seal"))

    def verify(self, expected_seal: Optional[str] = None) -> bool:
        """
        Full structural check. Callable independently of load() so a
        reviewer can audit a store without trusting the loader.
        """
        if self.birth is None:
            raise IntegrityError("No birth record")

        # D3a: the persisted constitution must hash to the birth commitment
        if not self.constitution:
            raise IntegrityError("Constitution missing from state — cannot verify birth binding")
        recomputed_constitution = _sha256(_canonical_json(self.constitution))
        if recomputed_constitution != self.birth.constitution_hash:
            raise IntegrityError(
                "Constitution does not match birth commitment — organism is not "
                "running under the constitution it was born with"
            )

        # D3b: genesis must be re-derivable from the birth fields
        recomputed_genesis = self._derive_genesis(
            self.birth.organism_id,
            self.birth.public_key_b64,
            self.birth.created_at,
            self.birth.constitution_hash,
        )
        if recomputed_genesis != self.birth.genesis_hash:
            raise IntegrityError("Genesis hash does not re-derive from birth record")

        if self.birth.organism_id != self.organism_id:
            raise IntegrityError("organism_id does not match birth record")

        # Character must still satisfy the schema the constitution declares
        for k, v in self.character.items():
            if k not in ALLOWED_CHARACTER_FIELDS:
                raise IntegrityError(f"Character contains disallowed field: {k}")
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise IntegrityError(f"Character field {k} is not numeric: {type(v).__name__}")
            if not (VALUE_MIN <= float(v) <= VALUE_MAX):
                raise IntegrityError(f"Character field {k} out of range: {v}")

        self._verify_chain()

        if expected_seal is not None and expected_seal != self._compute_seal():
            raise IntegrityError(
                "State seal mismatch — corruption or rewrite of a sealed region "
                "(birth, constitution, character, basin, pending, consumed, gates, trace head)"
            )
        return True

    # ------------------------------------------------------------------
    # Fenced interpretation + basin
    # ------------------------------------------------------------------

    def interpret(self, event: str, transcript: str) -> Dict[str, float]:
        """O3: keyword stub. Confidence numbers here are decorative."""
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
            category=category,
            distribution=dist,
            evidence=[transcript],
            salience=lead_weight,
            created_at=time.time(),
        ))

        needs_first = self.first_commit_pending.get(category, True)

        if lead not in LABEL_TO_DELTA or lead_weight < 0.60 or needs_first:
            self._save()
            return {
                "status": "dwelling",
                "reason": (
                    "no sanctioned mapping for lead read" if lead not in LABEL_TO_DELTA
                    else "low confidence or first-commit gate"
                ),
                "distribution": dist,
                "message": "Holding in basin. Owner authorization required for permanent change.",
            }

        # Labels never become values. Only a sanctioned delta does.
        current = float(self.character[category])
        proposed = min(VALUE_MAX, max(VALUE_MIN, current + LABEL_TO_DELTA[lead]))

        proposal = self._issue_pending_proposal(
            category=category,
            change={category: proposed},
            distribution=dist,
            evidence=[transcript],
        )
        self._save()
        return {
            "status": "proposal",
            "proposal_id": proposal.proposal_id,
            "payload_to_sign": proposal.payload_to_sign,
            "message": "Proposal issued and pending. Requires valid owner signature to apply.",
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
    ) -> PendingProposal:
        if category not in ALLOWED_CHARACTER_FIELDS:
            raise ValueError(f"Disallowed mutation category: {category}")
        if not change:
            raise ValueError("Empty mutation")
        for k, v in change.items():
            if k not in ALLOWED_CHARACTER_FIELDS:
                raise ValueError(f"Disallowed mutation field: {k}")
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(
                    f"Mutation value for {k} must be a number, got {type(v).__name__}"
                )
            if not (VALUE_MIN <= float(v) <= VALUE_MAX):
                raise ValueError(
                    f"Mutation value for {k} out of range [{VALUE_MIN}, {VALUE_MAX}]: {v}"
                )
        # Normalise to float so signed material and applied material cannot
        # differ by int-vs-float representation.
        change = {k: float(v) for k, v in change.items()}

        proposal_id = str(uuid.uuid4())
        nonce = secrets.token_hex(16)
        timestamp = time.time()
        change_hash = _sha256(_canonical_json(change))

        payload_obj = {
            "schema_version": SCHEMA_VERSION,
            "organism_id": self.organism_id,
            "proposal_id": proposal_id,
            "category": category,
            "change": change,
            "change_hash": change_hash,
            "nonce": nonce,
            "timestamp": _fixed(timestamp),
        }
        payload_to_sign = _canonical_json(payload_obj)

        pending = PendingProposal(
            proposal_id=proposal_id,
            organism_id=self.organism_id,
            category=category,
            change=change,
            change_hash=change_hash,
            distribution=distribution,
            evidence=evidence,
            nonce=nonce,
            timestamp=timestamp,
            payload_to_sign=payload_to_sign,
            payload_hash=_sha256(payload_to_sign),
        )
        self.pending[proposal_id] = pending
        return pending

    def _recompute_payload(self, pending: PendingProposal) -> str:
        return _canonical_json({
            "schema_version": SCHEMA_VERSION,
            "organism_id": pending.organism_id,
            "proposal_id": pending.proposal_id,
            "category": pending.category,
            "change": pending.change,
            "change_hash": pending.change_hash,
            "nonce": pending.nonce,
            "timestamp": _fixed(pending.timestamp),
        })

    # ------------------------------------------------------------------
    # External authorization (verify only — no signing anywhere in here)
    # ------------------------------------------------------------------

    def authorize_and_apply(
        self,
        proposal_id: str,
        signature_b64: str,
        owner_note: str = "",
    ) -> bool:
        if self.public_key is None or self.organism_id is None:
            raise RuntimeError("Organism has not hatched.")

        if proposal_id not in self.pending:
            self._log_auth_failure(proposal_id, "unknown or already-consumed proposal_id")
            return False

        pending = self.pending[proposal_id]
        consume_key = f"{pending.proposal_id}|{pending.nonce}"

        if consume_key in self.consumed:
            self._log_auth_failure(proposal_id, "replay of consumed proposal/nonce")
            return False

        if pending.organism_id != self.organism_id:
            self._log_auth_failure(proposal_id, "wrong organism_id")
            return False

        # Re-validate the schema at apply time, not only at issue time.
        try:
            for k, v in pending.change.items():
                if k not in ALLOWED_CHARACTER_FIELDS:
                    raise ValueError(f"disallowed field {k}")
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise ValueError(f"non-numeric value for {k}")
                if not (VALUE_MIN <= float(v) <= VALUE_MAX):
                    raise ValueError(f"out-of-range value for {k}")
            if pending.change_hash != _sha256(_canonical_json(pending.change)):
                raise ValueError("change_hash does not match change")
        except ValueError as e:
            self._log_auth_failure(proposal_id, f"schema violation at apply time: {e}")
            return False

        recomputed_payload = self._recompute_payload(pending)
        if recomputed_payload != pending.payload_to_sign:
            self._log_auth_failure(proposal_id, "internal payload inconsistency")
            return False

        try:
            sig = base64.urlsafe_b64decode(signature_b64)
            self.public_key.verify(sig, recomputed_payload.encode("utf-8"))
        except InvalidSignature:
            self._log_auth_failure(proposal_id, "invalid signature")
            return False
        except Exception:
            self._log_auth_failure(proposal_id, "signature verification error")
            return False

        prior = dict(self.character)
        category = pending.category
        change = pending.change

        for k, v in change.items():
            self.character[k] = float(v)

        self.first_commit_pending[category] = False
        self.consumed.add(consume_key)
        del self.pending[proposal_id]

        record = MutationRecord(
            proposal_id=pending.proposal_id,
            category=category,
            change=change,
            distribution=pending.distribution,
            evidence=pending.evidence,
            authorized_at=time.time(),
            signature_b64=signature_b64,
            prior_character_snapshot=prior,
            note=owner_note,
        )
        self._append_trace({
            "event": "authorized_mutation",
            "record": asdict(record),
            "timestamp": record.authorized_at,
        })

        self.basin = [p for p in self.basin if p.category != category]
        self._save()
        return True

    def _log_auth_failure(self, proposal_id: str, reason: str) -> None:
        self._append_trace({
            "event": "authorization_rejected",
            "proposal_id": proposal_id,
            "reason": reason,
            "timestamp": time.time(),
        })
        self._save()


# ---------------------------------------------------------------------------
# OWNER TOOL — deliberately outside HumbleSeed (D4)
#
# The organism class has no reference to this function and no signing
# primitive in its namespace. In a real deployment this lives in a separate
# process or a hardware token; here it is merely a separate module region,
# which is a structural split, not an enforced one (O2).
# ---------------------------------------------------------------------------

def owner_sign_external(private_key_pem: str, payload_to_sign: str) -> str:
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("ascii"), password=None
    )
    return base64.urlsafe_b64encode(
        private_key.sign(payload_to_sign.encode("utf-8"))
    ).decode("ascii")


# ---------------------------------------------------------------------------
# Falsification harness
# ---------------------------------------------------------------------------

def _rewrite_state(seed: HumbleSeed, mutate) -> str:
    """Apply a raw edit to the state file and report what a fresh load does."""
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

    print("=" * 74)
    print("Humble Seed v0.4 — Full-Coverage Seal / Genesis / Constitution Binding")
    print("=" * 74)

    data_dir = Path("./demo_seed_data_v04")
    shutil.rmtree(data_dir, ignore_errors=True)
    seed = HumbleSeed(data_dir=data_dir)

    print("\n[1] Hatching...")
    organism_id, private_pem = seed.hatch()
    print(f"    Organism ID       : {organism_id}")
    print(f"    Genesis           : {seed.birth.genesis_hash[:16]}...")
    print(f"    Constitution hash : {seed.birth.constitution_hash[:16]}...")
    key_path = data_dir / "OWNER_PRIVATE_KEY.pem"
    key_path.write_text(private_pem)
    key_path.chmod(0o600)

    print("\n[2] Public path (first-commit gate opened)...")
    seed.first_commit_pending["verbosity"] = False
    result = seed.dwell_or_propose("verbosity", "response_length",
                                   "I always prefer shorter answers")
    print(f"    Status : {result['status']}")
    pid = result["proposal_id"]
    payload = result["payload_to_sign"]
    change = seed.pending[pid].change
    print(f"    Change : {change}")
    assert all(isinstance(v, float) for v in change.values()), "label leaked into value"

    print("\n[3] Invalid signature (must fail)...")
    bad = base64.urlsafe_b64encode(b"I_am_the_organism").decode()
    print(f"    Accepted? {seed.authorize_and_apply(pid, bad)}  (expected False)")

    print("\n[4] External owner authorization...")
    sig = owner_sign_external(private_pem, payload)
    ok = seed.authorize_and_apply(pid, sig, owner_note="Prefer concise answers")
    print(f"    Applied?  {ok}")
    print(f"    Character: {seed.character}")

    print("\n[5] Type-invalid mutation (must be rejected at issuance)...")
    try:
        seed._issue_pending_proposal("verbosity", {"verbosity": "preference"},
                                     {"preference": 1.0}, ["x"])
        print("    ACCEPTED — FAIL")
    except ValueError as e:
        print(f"    Rejected: {e}")

    print("\n[6] TRUE consumed-ledger replay (pending entry re-inserted)...")
    p2 = seed._issue_pending_proposal("formality", {"formality": 0.3},
                                      {"preference": 1.0}, ["be less formal"])
    sig2 = owner_sign_external(private_pem, p2.payload_to_sign)
    seed.authorize_and_apply(p2.proposal_id, sig2)
    seed.pending[p2.proposal_id] = p2          # resurrect it, as an attacker would
    ok_replay = seed.authorize_and_apply(p2.proposal_id, sig2)
    reason = [e["reason"] for e in seed.trace if e.get("event") == "authorization_rejected"][-1]
    print(f"    Replay accepted? {ok_replay}  (expected False)")
    print(f"    Branch reached : {reason}")
    assert reason == "replay of consumed proposal/nonce", "consumed ledger still unreachable"
    del seed.pending[p2.proposal_id]
    seed._save()

    print("\n[7] Trace body rewritten, entry_hash LEFT INTACT (the real attack)...")
    def forge_trace(st):
        for e in st["trace"]:
            if e.get("event") == "authorized_mutation":
                e["record"]["note"] = "FORGED BY ATTACKER"
                e["record"]["evidence"] = ["fabricated evidence"]
    print(f"    {_rewrite_state(seed, forge_trace)}")
    seed._save()

    print("\n[8] Pending proposal body rewritten, same proposal_id (D1)...")
    p3 = seed._issue_pending_proposal("curiosity", {"curiosity": 0.4},
                                      {"preference": 1.0}, ["real evidence"])
    seed._save()
    def forge_pending(st):
        st["pending"][p3.proposal_id]["change"] = {"curiosity": 0.99}
        st["pending"][p3.proposal_id]["evidence"] = ["WIPED"]
    print(f"    {_rewrite_state(seed, forge_pending)}")
    seed._save()

    print("\n[9] Basin evidence wiped (D2)...")
    seed.dwell_or_propose("curiosity", "ambiguous", "something odd happened")
    seed._save()
    def forge_basin(st):
        for b in st["basin"]:
            b["evidence"] = ["EVIDENCE DESTROYED"]
    print(f"    {_rewrite_state(seed, forge_basin)}")
    seed._save()

    print("\n[10] Constitution swapped for a permissive one (D3)...")
    def forge_constitution(st):
        st["constitution"]["rule"] = "The organism may authorize its own growth."
        st["constitution"]["invariants"] = []
    print(f"    {_rewrite_state(seed, forge_constitution)}")
    seed._save()

    print("\n[11] Birth record edited to detach genesis (D3)...")
    def forge_birth(st):
        st["birth"]["constitution_hash"] = "0" * 64
        st["birth"]["created_at"] = 1.0
    print(f"    {_rewrite_state(seed, forge_birth)}")
    seed._save()

    print("\n[12] Restart + independent verify()...")
    fresh = HumbleSeed(data_dir=data_dir)
    fresh.load()
    print(f"    Identity matches  : {fresh.organism_id == organism_id}")
    print(f"    Character         : {fresh.character}")
    print(f"    Trace length      : {len(fresh.trace)}")
    print(f"    Consumed entries  : {len(fresh.consumed)}")
    print(f"    verify() passes   : {fresh.verify()}")

    print("\n" + "=" * 74)
    print("Closed in v0.4:")
    print("  D1 seal covers full pending contents, not just proposal ids")
    print("  D2 seal covers the basin (pre-authorization evidence)")
    print("  D3 constitution persisted + rehashed; genesis re-derived; birth sealed")
    print("  D4 signing moved out of the organism class entirely")
    print("  D5 atomic state writes")
    print("  D6 harness exercises the real replay and real chain attacks")
    print("\nStill open — see FOR ADVERSARIAL REVIEWERS in the module docstring:")
    print("  O1 seal is unkeyed; a file-write attacker who recomputes it forges freely")
    print("  O2 owner tool runs in-process; the split is structural, not enforced")
    print("  O3 interpret() is a keyword stub")
    print("  O4 no key rotation, revocation, or proposal expiry")
    print("  O5 single-writer assumption, no file locking")
    print("=" * 74)


if __name__ == "__main__":
    demo_and_falsify()
