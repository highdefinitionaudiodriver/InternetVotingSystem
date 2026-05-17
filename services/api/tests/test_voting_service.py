from __future__ import annotations

import unittest

from internet_voting_system.service import VotingService


class VotingServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = VotingService()
        self.election_id = "demo-2026"

    def test_full_voting_flow(self) -> None:
        auth = self.service.authenticate_voter(self.election_id, "CERT-1234567890", "1980-01-01")
        token = self.service.issue_token(self.election_id, auth["voter_hash"])
        prepared = self.service.prepare_vote(self.election_id, "cand-a")
        receipt = self.service.submit_ballot(
            self.election_id,
            token["blind_token"],
            prepared["encrypted_vote"],
            prepared["zk_proof"],
        )
        board = self.service.public_board(self.election_id)
        tally = self.service.tally(self.election_id)

        self.assertEqual(receipt["election_id"], self.election_id)
        self.assertEqual(len(board["ballots"]), 1)
        self.assertEqual(tally["counts"]["cand-a"], 1)
        self.assertEqual(tally["accepted_ballots"], 1)

    def test_revote_uses_latest_ballot_per_token(self) -> None:
        auth = self.service.authenticate_voter(self.election_id, "CERT-REVOTE-1", "1980-01-01")
        token = self.service.issue_token(self.election_id, auth["voter_hash"])

        first = self.service.prepare_vote(self.election_id, "cand-a")
        second = self.service.prepare_vote(self.election_id, "cand-b")
        self.service.submit_ballot(self.election_id, token["blind_token"], first["encrypted_vote"], first["zk_proof"])
        self.service.submit_ballot(self.election_id, token["blind_token"], second["encrypted_vote"], second["zk_proof"])

        tally = self.service.tally(self.election_id)
        self.assertEqual(tally["accepted_ballots"], 1)
        self.assertEqual(tally["counts"]["cand-a"], 0)
        self.assertEqual(tally["counts"]["cand-b"], 1)

    def test_rejects_invalid_zk_proof(self) -> None:
        auth = self.service.authenticate_voter(self.election_id, "CERT-INVALID-1", "1980-01-01")
        token = self.service.issue_token(self.election_id, auth["voter_hash"])
        prepared = self.service.prepare_vote(self.election_id, "cand-a")
        prepared["zk_proof"] = prepared["zk_proof"][:-1] + ("A" if prepared["zk_proof"][-1] != "A" else "B")

        with self.assertRaises(ValueError):
            self.service.submit_ballot(
                self.election_id,
                token["blind_token"],
                prepared["encrypted_vote"],
                prepared["zk_proof"],
            )

    def test_no_mynumber_field_is_needed(self) -> None:
        auth = self.service.authenticate_voter(self.election_id, "CERT-NO-MYNUMBER", "1990-01-01")
        self.assertNotIn("mynumber", auth)
        self.assertNotIn("individual_number", auth)


if __name__ == "__main__":
    unittest.main()
