from __future__ import annotations

import unittest

from internet_voting_system.service import VotingService
from internet_voting_system.sqlite_repository import SqliteRepository


class SqliteBackedServiceTest(unittest.TestCase):
    """Run the full voting flow on top of the SQLite repository.

    Using ``:memory:`` keeps tests hermetic while still exercising every SQL
    statement. If these tests pass we have confidence the schema + SQL
    transactions match the in-memory semantics.
    """

    def setUp(self) -> None:
        self.repository = SqliteRepository(":memory:")
        self.service = VotingService(repository=self.repository)
        self.election_id = "demo-2026"

    def _cast_vote(self, certificate: str, candidate: str) -> dict:
        auth = self.service.authenticate_voter(self.election_id, certificate, "1980-01-01")
        token = self.service.issue_token(self.election_id, auth["voter_hash"])
        prepared = self.service.prepare_vote(self.election_id, candidate)
        return self.service.submit_ballot(
            self.election_id,
            token["blind_token"],
            prepared["encrypted_vote"],
            prepared["zk_proof"],
        )

    def test_full_flow_persists_and_tallies(self) -> None:
        receipt = self._cast_vote("CERT-SQLITE-001", "cand-a")
        self.assertEqual(receipt["election_id"], self.election_id)

        tally = self.service.tally(self.election_id)
        self.assertEqual(tally["accepted_ballots"], 1)
        self.assertEqual(tally["counts"]["cand-a"], 1)

    def test_revote_replaces_earlier_ballot(self) -> None:
        auth = self.service.authenticate_voter(self.election_id, "CERT-SQLITE-002", "1980-01-01")
        token = self.service.issue_token(self.election_id, auth["voter_hash"])

        first = self.service.prepare_vote(self.election_id, "cand-a")
        self.service.submit_ballot(self.election_id, token["blind_token"], first["encrypted_vote"], first["zk_proof"])
        second = self.service.prepare_vote(self.election_id, "cand-c")
        self.service.submit_ballot(self.election_id, token["blind_token"], second["encrypted_vote"], second["zk_proof"])

        tally = self.service.tally(self.election_id)
        self.assertEqual(tally["accepted_ballots"], 1)
        self.assertEqual(tally["counts"]["cand-c"], 1)
        self.assertEqual(tally["counts"]["cand-a"], 0)

    def test_receipt_verification_round_trip(self) -> None:
        receipt = self._cast_vote("CERT-SQLITE-003", "cand-b")
        verified = self.service.verify_receipt(self.election_id, receipt["receipt_hash"])
        self.assertTrue(verified["found"])
        self.assertTrue(verified["integrity_ok"])
        self.assertEqual(verified["ballot"]["ballot_id"], receipt["ballot_id"])

    def test_receipt_verification_returns_not_found_for_unknown_hash(self) -> None:
        verified = self.service.verify_receipt(self.election_id, "0" * 64)
        self.assertFalse(verified["found"])
        self.assertNotIn("ballot", verified)

    def test_audit_chain_is_valid_after_voting(self) -> None:
        self._cast_vote("CERT-SQLITE-004", "cand-a")
        self._cast_vote("CERT-SQLITE-005", "cand-b")
        result = self.service.verify_audit_chain()
        self.assertTrue(result["valid"])
        self.assertGreaterEqual(result["total"], 1)
        self.assertEqual(len(result["head_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
