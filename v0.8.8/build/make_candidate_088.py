#!/usr/bin/env python3
"""Derives humble_seed_v0_8_8_candidate.py from v0.8.7 by exact-once replacements."""
import sys
from pathlib import Path

src_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
src = src_path.read_text(encoding="utf-8")


def once(old, new):
    global src
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"anchor occurs {n} times:\n{old[:300]}")
    src = src.replace(old, new)


start = src.index('"""')
end_marker = 'Run the falsification harness:  python3 -I falsify_v0_8_7.py\n"""'
end = src.index(end_marker) + len(end_marker)
DOC = '''"""
Humble Seed v0.8.8 CANDIDATE — Final Revision of the v0.8 Line
==============================================================

STATUS: candidate, not canonical; the final revision before publication.
Parent: humble_seed_v0_8_7_candidate.py (sha256 0292c032...).

Round 8 (ChatGPT's claims battery) found three things:
  - A failed witness commit followed by ordinary use left an organism that
    attest, audit and restore all refused.
  - A same-thread re-entry (a signal handler) between a save's check and its
    write could lose a saved update, or let restore overwrite a sign-off.
  - An interrupt during the generation re-read escaped the unusable mark.
It also showed two docstring claims that the frozen tests themselves
contradicted. The author's sealed findings: restore forgot the owner's
answers; a callback could deadlock the two locks; a symlinked path
deadlocked one thread. Everything not listed is carried from v0.8.7.

CHANGES

  E1  RESTORE RESOLVES A PENDING COMMIT FROM THE ATTESTED PREFIX. Sometimes the
      saved checkpoint is the pending one but the saved state does not verify
      (a later unattested change). Restore then completes the commit if the
      attested prefix verifies, and rebuilds at that checkpoint. The prefix
      verifies when:
        - the owner's signature on the checkpoint verifies;
        - the prefix chain ends at the checkpoint's trace head;
        - a replay of the prefix reproduces every root the checkpoint commits to.
      attest and audit keep the strict rule (v0.8.6 C).

  E2  NO RE-ENTRY INTO A SAVE. A save marks its organism, in its own thread,
      from its checks to its write. A save that re-enters another save of the
      same organism in the same thread (a signal handler, a callback) is
      refused with ReentryRefused, and writes nothing. The refused
      operation's object may already have changed its memory; it is then
      ahead of its disk (R31). If the handler lets the refusal propagate, the
      outer save is interrupted like any other exception.

  E3  AN INTERRUPT DURING THE GENERATION RE-READ still marks the object
      unusable, and the interrupt propagates.

  E4  RESTORE KEEPS THE OWNER'S ANSWERS.
      - Owner answers in the discarded tail are carried into the restored trace,
        before the "restored" event. They are non-authorizing.
      - restore reports, as "owner_no_outstanding", each category in which the
        owner's latest answer within its own window is 'no'. The next crossing
        there will be refused at sign-off unless the owner answers again.

  E5  LOCK ORDER IS ENFORCED: owner, then organism. An owner operation started
      by a thread that holds an organism lock but not the owner lock is refused
      with LockOrderRefused, instead of deadlocking.

  E6  LOCKS ARE KEYED BY THE REAL PATH, so a symlinked path names the same
      lock.

  E7  DOCSTRING CORRECTIONS (below).

CORRECTED CLAIMS (v0.8.7 text that its own frozen tests T81 and T76 contradicted)
  - Restore moves the witness only when it first completes a pending commit.
    Otherwise the witness does not move.
  - An object that is stale at the start of an operation is refused before it
    changes anything. An object made stale during its own operation (a write
    through a callback, T76) has already changed its memory when its save is
    refused; it must reload.
  - An unusable object refuses every state-changing operation, and attest.
    audit and read-only methods still work on it; audit resolves a pending
    commit from the saved state, not from the object.

FINDINGS CLOSED
  ChatGPT r8 F1  Failed commit + later crossing: nothing could recover -> E1.
  ChatGPT r8 F2  Same-thread re-entry lost a saved update -> E2.
  ChatGPT r8 F3  Restore overwrote a sign-off made inside it -> E2.
  ChatGPT r8 F4  Interrupt during the re-read escaped the unusable mark -> E3.
  ChatGPT r8     R2, Q3/R33 overclaimed -> E7.
  Author  A1     Restore forgot the owner's answers -> E4.
  Author  A2     Callback lock-order deadlock (found independently by ChatGPT) -> E5.
  Author  A3     Symlinked path self-deadlock -> E6.

LIMITS. R1-R32, R34 and R36 as in v0.8.7, except:
  R33 (revised) A stale object must reload, and its unsaved changes are lost.
      An object stale when an operation starts is refused before it changes
      anything, and an answer given through it is recorded nowhere. An object
      made stale during its own operation is covered by R35.
  R35 (revised) Operations are serialized per organism, by real path, across
      threads and processes. Reading an object's attributes, or calling its
      private methods, outside these operations is not. A save cannot be
      re-entered in the same thread. Other same-thread nesting is allowed: a
      callback or handler that runs an operation inside another, outside a
      save. Its write makes the outer object stale mid-operation. The outer
      object has then changed its memory, and its save is refused as stale
      (T76). An owner answer whose organism save is refused this way stays in
      the owner's ledger.
  R37 Restore's prefix route completes a pending commit only for a checkpoint
      the owner signed whose prefix replays exactly. Whatever follows the
      prefix in the saved file is then discarded by the restore, except the
      owner's answers.
  R38 The lock-order refusal covers owner operations started from inside an
      organism operation. Waits outside these two locks are not covered.
  R39 A restore that is interrupted by a nested owner operation (refused by E2)
      can leave that operation's pending intent behind. The next attest, audit
      or restore abandons it, because the saved checkpoint is the witness head.

Run the falsification harness:  python3 -I falsify_v0_8_8.py
"""'''
src = src[:start] + DOC + src[end:]

once('SCHEMA_VERSION = "0.8.7-candidate"\n', 'SCHEMA_VERSION = "0.8.8-candidate"\n')

# E5, E6: lock order and real-path keys
once('''    _registry: Dict[str, Dict[str, Any]] = {}
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
''', '''    _registry: Dict[str, Dict[str, Any]] = {}
    _guard = threading.Lock()

    def __init__(self, path: Path | str, kind: str = "owner"):
        self.path = os.path.realpath(str(path))          # [LOCK-KEY] v0.8.8 (author A3): one lock per real path
        self.kind = kind                                 # "owner" or "organism"

    def __enter__(self):
        with _OwnerLock._guard:
            entry = _OwnerLock._registry.setdefault(
                self.path, {"rlock": threading.RLock(), "fd": None, "depth": 0, "thread": None})
        # v0.8.8 (author A2; ChatGPT r8): the order is owner, then organism. A thread holding an
        # organism lock may re-enter an owner lock it already holds, never take one fresh.
        if (self.kind == "owner" and getattr(_THREAD, "organism_held", 0) > 0    # [LOCK-ORDER]
                and not (entry["depth"] > 0 and entry["thread"] == threading.get_ident())):
            raise LockOrderRefused("an owner operation was started while this thread holds an organism "
                                   "lock; the order is owner, then organism")
        entry["rlock"].acquire()
        if entry["depth"] == 0:
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
            entry["fd"] = fd
            entry["thread"] = threading.get_ident()
        entry["depth"] += 1
        if self.kind == "organism":
            _THREAD.organism_held = getattr(_THREAD, "organism_held", 0) + 1
        return self

    def __exit__(self, *exc) -> bool:
        entry = _OwnerLock._registry[self.path]
        if self.kind == "organism":
            _THREAD.organism_held -= 1
        entry["depth"] -= 1
        if entry["depth"] == 0:
            fcntl.flock(entry["fd"], fcntl.LOCK_UN)
            os.close(entry["fd"])
            entry["fd"] = None
            entry["thread"] = None
        entry["rlock"].release()
        return False
''')
once('''class _OwnerLock:
''', '''_THREAD = threading.local()     # v0.8.8: per thread, organism locks held and saves in progress


class _OwnerLock:
''')
once('''class IntegrityError(RuntimeError):
    """Persisted state failed a structural or attestation check."""
''', '''class IntegrityError(RuntimeError):
    """Persisted state failed a structural or attestation check."""


class ReentryRefused(RuntimeError):
    """v0.8.8: a save re-entered another save of the same organism in the same thread."""


class LockOrderRefused(RuntimeError):
    """v0.8.8: an owner operation was started while holding an organism lock."""
''')
once('''        return _OwnerLock(self.data_dir / "organism.lock")      # [ORGANISM-LOCK]
''', '''        return _OwnerLock(self.data_dir / "organism.lock", kind="organism")      # [ORGANISM-LOCK]
''')

# E2, E3: no re-entry into a save; an interrupt during the re-read still marks the object unusable
lock_line = "        with self._organism_lock():            # [SAVE-LOCK] v0.8.7 (ChatGPT r7 F1): check, snapshot and write under one lock\n"
i = src.index(lock_line)
j = src.index("\n    def load(self) -> None:", i)
body = src[i + len(lock_line):j]
lines = body.split("\n")
assert all(l.startswith("            ") or not l.strip() for l in lines), "save body indentation"
dedented = "\n".join(l[4:] if l.strip() else l for l in lines)
src = src[:i] + lock_line + """            with _save_mark(self.data_dir):    # v0.8.8 (ChatGPT r8 F2, F3): a save is never re-entered
                self._save_locked()

    def _save_locked(self) -> None:
        \"\"\"The save itself. The caller holds the organism lock and the save mark.\"\"\"
""" + dedented + src[j:]
once('''            try:
                landed = self._saved_generation() == new_gen
            except Exception:
                landed = None
            if landed is None:
                self._generation = _UNUSABLE                 # [SAVE-INDETERMINATE]
            elif landed:
                self._generation = new_gen                   # [SAVE-LANDED]
            raise
''', '''            try:
                landed = self._saved_generation() == new_gen
            except BaseException as why:                     # v0.8.8 (ChatGPT r8 F4): an interrupt too
                self._generation = _UNUSABLE                 # [SAVE-INDETERMINATE]
                if not isinstance(why, Exception):
                    raise                                    # the interrupt still propagates
            else:
                if landed:
                    self._generation = new_gen               # [SAVE-LANDED]
            raise
''')
once('''def _owner_locked(method):
''', '''@contextlib.contextmanager
def _save_mark(data_dir: Path):
    """v0.8.8 (ChatGPT r8 F2, F3): a save marks its organism, in its own thread, from its
    checks to its write. A save that re-enters it is refused before it checks or writes."""
    key = os.path.realpath(str(data_dir))
    saving = getattr(_THREAD, "saving", None)
    if saving is None:
        saving = _THREAD.saving = set()
    if key in saving:                                    # [SAVE-REENTRY]
        raise ReentryRefused("a save re-entered another save of this organism in the same thread "
                             "(a signal handler or callback); refused, nothing written")
    saving.add(key)
    try:
        yield
    finally:
        saving.discard(key)


def _owner_locked(method):
''')

# E4: restore carries the owner's answers
once('''            digest = _sha256(raw)
            keep = self.data_dir / f"pre_restore_gen{g}_{digest[:12]}.json"
            r._append_trace({
                "event": "restored",
                "checkpoint_sequence": cp.sequence,
                "discarded_entries": len(trace) - n if isinstance(trace, list) else None,
''', '''            carried = [e for e in trace[n:] if isinstance(e, dict) and e.get("event") == "owner_answer"]
            for e in carried:                                                                   # [RESTORE-ANSWERS] v0.8.8 (author A1)
                r._append_trace({k: v for k, v in e.items() if k not in ("prev_hash", "entry_hash")})
            digest = _sha256(raw)
            keep = self.data_dir / f"pre_restore_gen{g}_{digest[:12]}.json"
            r._append_trace({
                "event": "restored",
                "checkpoint_sequence": cp.sequence,
                "discarded_entries": len(trace) - n if isinstance(trace, list) else None,
                "carried_owner_answers": len(carried),
''')

# E1: restore completes a pending commit from the attested prefix
once('''    def _recover(self, seed: HumbleSeed, oid: Optional[str] = None) -> Optional[str]:
''', '''    def _saved_prefix_refusal(self, seed: HumbleSeed, cp: Checkpoint, sig: str) -> Optional[str]:
        """v0.8.8 (ChatGPT r8 F1): None if the saved file's attested prefix for cp verifies: this
        owner's signature on cp, the prefix chain ending at cp.trace_head, and a replay of the
        prefix reproducing every root cp commits to. Nothing after the prefix is consulted."""
        try:
            data = _strict_loads(seed._state_path().read_text(encoding="utf-8"))
            birth = BirthRecord(**data["birth"])
            constitution = data["constitution"]
            trace = data["trace"]
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as why:
            return f"the saved state cannot be read ({type(why).__name__})"
        if birth.public_key_b64 != self._public_b64:
            return "the organism is not keyed to this owner"
        if not _verify_owner_signature(self._public_key, sig, HumbleSeed.checkpoint_payload(cp)):
            return "the checkpoint signature does not verify"
        n = cp.attested_trace_len
        prefix = list(trace[:n]) if isinstance(trace, list) else []
        try:
            head = _check_chain(prefix)
        except (ValueError, AttributeError, TypeError) as why:
            return f"the attested prefix does not chain ({why})"
        if n < 1 or len(prefix) != n or head != cp.trace_head:
            return "the attested prefix does not match the checkpoint"
        try:
            st = replay_signed_history(constitution, prefix, self._public_key, data.get("organism_id"))
        except (AttestationRefused, KeyError, TypeError, ValueError) as why:
            return f"the attested prefix does not replay ({why})"
        roots = {"birth_root": _sha256(_canonical_json(asdict(birth))),
                 "constitution_root": _sha256(_canonical_json(constitution)),
                 "character_root": _sha256(_canonical_json(st["character"])),
                 "gates_root": _sha256(_canonical_json(st["category_sequence"])),
                 "consumed_root": _sha256(_canonical_json(sorted(st["consumed"])))}
        off = [k for k, v in roots.items() if getattr(cp, k) != v]
        if st["mutation_sequence"] != cp.mutation_sequence or cp.organism_id != data.get("organism_id"):
            off.append("mutation_sequence/organism_id")
        return None if not off else "the replayed prefix does not match the checkpoint: " + ", ".join(off)

    def _recover(self, seed: HumbleSeed, oid: Optional[str] = None, allow_prefix: bool = False) -> Optional[str]:
''')
once('''            why = self._saved_state_refusal(seed)                 # [RECOVER-VERIFIES]
            if why is not None:
                raise RollbackDetected("A pending checkpoint commit cannot be completed: the saved state "
                                       f"claims it but does not verify ({why})")
''', '''            why = self._saved_state_refusal(seed)                 # [RECOVER-VERIFIES]
            if why is not None:
                prefix_why = self._saved_prefix_refusal(seed, pending_cp, p["signature_b64"]) if allow_prefix else why  # [RECOVER-PREFIX]
                if prefix_why is not None:
                    raise RollbackDetected("A pending checkpoint commit cannot be completed: the saved state "
                                           f"claims it but does not verify ({why})")
''')
once('''            self._recover(seed, oid)                     # [RESTORE-RECOVERS]
            head = self.witness.head_for(oid)
            if head is None:
                raise RollbackDetected("restore refused: the witness holds no checkpoint for this organism")
            return seed._restore_attested(head["checkpoint_hash"], self._public_b64)
''', '''            self._recover(seed, oid, allow_prefix=True)  # [RESTORE-RECOVERS] v0.8.8: the prefix route (E1)
            head = self.witness.head_for(oid)
            if head is None:
                raise RollbackDetected("restore refused: the witness holds no checkpoint for this organism")
            result = seed._restore_attested(head["checkpoint_hash"], self._public_b64)
            result["owner_no_outstanding"] = self._outstanding_no(seed)         # [RESTORE-REPORT] v0.8.8 (author A1)
            return result

    def _outstanding_no(self, seed: HumbleSeed) -> List[str]:
        """v0.8.8: categories whose next crossing the owner's own window would hold: its latest
        answer in the category, since it signed the last attested crossing there, is 'no'."""
        st = replay_signed_history(seed.constitution, seed.trace, self._public_key, seed.organism_id)
        last: Dict[str, Dict[str, Any]] = {}
        for _, rec in st["applied"]:
            last[rec["category"]] = rec
        out = []
        for cat in sorted(policy_fields(seed.constitution)):
            start = 0
            if cat in last:
                signed = self.ledger.signed(seed.organism_id, _sha256(last[cat]["signed_payload"]))
                start = signed["seq"] if signed else 0
            answers = self.ledger.answers_in_category_after(seed.organism_id, cat, start)
            if answers and answers[-1] == "no":
                out.append(cat)
        return out
''')
once('''        """v0.8.7 (R20; Rusty's ruling 2026-10-19). Bring the organism back to its last
        attested state: the witness head. A pending commit is resolved first; then the
        organism rebuilds that state from the attested prefix of its saved trace,
        discarding everything after it. The witness does not move. Works from an
        object that has not loaded (an unattested state does not load)."""''',
     '''        """v0.8.7 (R20; Rusty's ruling 2026-10-19). Bring the organism back to its last
        attested state: the witness head. A pending commit is resolved first (v0.8.8: from
        the attested prefix if the whole saved state does not verify), which moves the
        witness; then the organism rebuilds that state from the attested prefix of its
        saved trace, discarding everything after it except the owner's answers. Works
        from an object that has not loaded (an unattested state does not load)."""''')

once('''    print("Run the harness: python3 -I falsify_v0_8_7.py")''', '''    print("Run the harness: python3 -I falsify_v0_8_8.py")''')

out_path.write_text(src, encoding="utf-8")
print("written", out_path, len(src.splitlines()), "lines")
