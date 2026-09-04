"""Integration checks for observable primary-v0.6 behavior and declared limits."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import humble_seed_v0_6 as core


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="humble-contract-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.seed, self.owner, self.pem = self.newborn("seed")

    def newborn(self, name):
        seed = core.HumbleSeed(self.root / name)
        _, pem, genesis = seed.hatch()
        witness = core.OwnerWitness(self.root / f"{name}-witness.json")
        owner = core.OwnerTool(pem, witness)
        self.assertTrue(owner.attest(seed, genesis))
        return seed, owner, pem

    def propose(self, seed=None):
        seed = seed or self.seed
        result = seed.dwell_or_propose("verbosity", "length", "I always prefer shorter answers")
        self.assertEqual(result["status"], "proposal")
        return seed.pending[result["proposal_id"]]

    def apply(self, proposal=None):
        proposal = proposal or self.propose()
        checkpoint = self.seed.authorize_and_apply(
            proposal.proposal_id, self.owner.sign_proposal(proposal.payload_to_sign)
        )
        self.assertIsNotNone(checkpoint)
        return checkpoint

    def reload(self):
        seed = core.HumbleSeed(self.seed.data_dir)
        seed.load()
        return seed

    def test_genesis_requires_owner_attestation(self):
        raw = core.HumbleSeed(self.root / "unattested")
        raw.hatch()
        with self.assertRaises(core.IntegrityError):
            core.HumbleSeed(raw.data_dir).load()

    def test_ambiguous_input_dwells_and_preserves_character(self):
        before = dict(self.seed.character)
        result = self.seed.dwell_or_propose("verbosity", "length", "Sorry, the door interrupted us")
        self.assertEqual(result["status"], "dwelling")
        reloaded = self.reload()
        self.assertEqual(reloaded.character, before)
        self.assertEqual(len(reloaded.basin), 1)
        self.assertTrue(self.owner.audit(reloaded))

    def test_first_commit_authorization_round_trip(self):
        proposal = self.propose()
        self.assertTrue(proposal.first_commit)
        self.assertEqual(self.seed.character["verbosity"], 0.5)
        self.assertTrue(self.owner.attest(self.seed, self.apply(proposal)))
        reloaded = self.reload()
        self.assertEqual(reloaded.character["verbosity"], 0.25)
        self.assertFalse(reloaded.first_commit_pending["verbosity"])
        self.assertEqual(reloaded.mutation_sequence, 1)
        self.assertTrue(self.owner.audit(reloaded))
        self.assertFalse(self.propose(reloaded).first_commit)

    def test_invalid_signature_preserves_character(self):
        proposal = self.propose()
        before = dict(self.seed.character)
        self.assertIsNone(self.seed.authorize_and_apply(proposal.proposal_id, "invalid"))
        self.assertEqual(self.reload().character, before)

    def test_signed_evidence_and_distribution_cannot_be_substituted(self):
        for field in ("evidence", "distribution"):
            with self.subTest(field=field):
                seed, owner, _ = self.newborn(field)
                proposal = self.propose(seed)
                signature = owner.sign_proposal(proposal.payload_to_sign)
                before = dict(seed.character)
                if field == "evidence":
                    proposal.evidence = ["substituted evidence"]
                else:
                    proposal.distribution = {"preference": 1.0}
                self.assertIsNone(seed.authorize_and_apply(proposal.proposal_id, signature))
                self.assertEqual(seed.character, before)
                self.assertIn("envelope", seed.trace[-1]["reason"])

    def test_expired_proposal_is_rejected(self):
        proposal = self.propose()
        signature = self.owner.sign_proposal(proposal.payload_to_sign)
        with patch.object(core.time, "time", return_value=proposal.expires_at + 1):
            self.assertIsNone(self.seed.authorize_and_apply(proposal.proposal_id, signature))
        self.assertEqual(self.seed.character["verbosity"], 0.5)
        self.assertIn("expired", self.seed.trace[-1]["reason"])

    def test_applied_state_cannot_reload_until_attested(self):
        checkpoint = self.apply()
        with self.assertRaises(core.IntegrityError):
            self.reload()
        self.assertTrue(self.owner.attest(self.seed, checkpoint))
        self.assertTrue(self.owner.audit(self.reload()))

    def test_consumed_signature_cannot_apply_twice(self):
        proposal = self.propose()
        signature = self.owner.sign_proposal(proposal.payload_to_sign)
        self.assertTrue(self.owner.attest(self.seed, self.apply(proposal)))
        before = dict(self.seed.character)
        self.assertIsNone(self.seed.authorize_and_apply(proposal.proposal_id, signature))
        self.assertEqual(self.seed.character, before)
        self.assertEqual(self.seed.mutation_sequence, 1)

    def test_other_pending_proposal_becomes_stale(self):
        first = self.propose()
        second = self.propose()
        signature = self.owner.sign_proposal(second.payload_to_sign)
        self.assertTrue(self.owner.attest(self.seed, self.apply(first)))
        self.assertIsNone(self.seed.authorize_and_apply(second.proposal_id, signature))
        self.assertIn("stale", self.seed.trace[-1]["reason"])

    def test_recomputed_seal_cannot_attest_changed_character(self):
        attacker = self.reload()
        attacker.character["verbosity"] = 0.99
        attacker._save()
        with self.assertRaises(core.IntegrityError):
            self.reload()

    def test_state_rollback_is_detected_by_external_witness(self):
        snapshot = self.seed._state_path().read_bytes()
        self.assertTrue(self.owner.attest(self.seed, self.apply()))
        self.seed._state_path().write_bytes(snapshot)
        internally_valid_old_state = self.reload()
        with self.assertRaises(core.RollbackDetected):
            self.owner.audit(internally_valid_old_state)

    def test_rolling_back_both_files_remains_a_documented_limit(self):
        state = self.seed._state_path().read_bytes()
        ledger = self.owner.witness.path.read_bytes()
        self.assertTrue(self.owner.attest(self.seed, self.apply()))
        self.seed._state_path().write_bytes(state)
        self.owner.witness.path.write_bytes(ledger)
        rolled_back_owner = core.OwnerTool(self.pem, core.OwnerWitness(self.owner.witness.path))
        self.assertTrue(rolled_back_owner.audit(self.reload()))

    def test_unattested_history_and_basin_remain_advisory(self):
        self.seed.dwell_or_propose("curiosity", "event", "something odd happened")
        attacker = self.reload()
        before = dict(attacker.character)
        attacker.basin[0].evidence = ["fabricated pre-proposal evidence"]
        attacker._append_trace({"event": "dwelling", "reason": "fabricated history"})
        attacker._save()
        accepted = self.reload()
        self.assertEqual(accepted.character, before)
        self.assertEqual(accepted.basin[0].evidence, ["fabricated pre-proposal evidence"])
        self.assertTrue(self.owner.audit(accepted))

    def test_invalid_mutation_values_are_rejected(self):
        for value in (True, "brief", float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.seed._issue_pending_proposal(
                    "verbosity", {"verbosity": value}, {"preference": 1.0}, ["e"]
                )

    def test_category_must_match_the_change(self):
        with self.assertRaises(ValueError):
            self.seed._issue_pending_proposal(
                "verbosity", {"formality": 0.2}, {"preference": 1.0}, ["e"]
            )

    def test_another_owners_signature_is_rejected(self):
        _, other_owner, _ = self.newborn("other")
        proposal = self.propose()
        signature = other_owner.sign_proposal(proposal.payload_to_sign)
        self.assertIsNone(self.seed.authorize_and_apply(proposal.proposal_id, signature))
        self.assertEqual(self.seed.character["verbosity"], 0.5)


if __name__ == "__main__":
    unittest.main()
