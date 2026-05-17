from __future__ import annotations

import unittest

from internet_voting_system.repository import InMemoryRepository
from internet_voting_system.service import VotingService


class ReceiptVerificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = VotingService()
        self.election_id = "demo-2026"

    def _cast(self, cert: str, candidate: str) -> dict:
        auth = self.service.authenticate_voter(self.election_id, cert, "1980-01-01")
        token = self.service.issue_token(self.election_id, auth["voter_hash"])
        prepared = self.service.prepare_vote(self.election_id, candidate)
        return self.service.submit_ballot(
            self.election_id,
            token["blind_token"],
            prepared["encrypted_vote"],
            prepared["zk_proof"],
        )

    def test_verify_receipt_finds_record(self) -> None:
        receipt = self._cast("CERT-RCPT-001", "cand-a")
        result = self.service.verify_receipt(self.election_id, receipt["receipt_hash"])
        self.assertTrue(result["found"])
        self.assertTrue(result["integrity_ok"])
        # The verification must NOT leak any voter identity.
        self.assertNotIn("voter_hash", result["ballot"])
        self.assertNotIn("accepted_candidate_id", result["ballot"])

    def test_verify_receipt_unknown_hash(self) -> None:
        result = self.service.verify_receipt(self.election_id, "0" * 64)
        self.assertFalse(result["found"])


class AuditChainTest(unittest.TestCase):
    def test_chain_detects_tampering(self) -> None:
        repo = InMemoryRepository()
        service = VotingService(repository=repo)
        auth = service.authenticate_voter("demo-2026", "CERT-AUDIT-1", "1980-01-01")
        token = service.issue_token("demo-2026", auth["voter_hash"])
        prepared = service.prepare_vote("demo-2026", "cand-a")
        service.submit_ballot(
            "demo-2026",
            token["blind_token"],
            prepared["encrypted_vote"],
            prepared["zk_proof"],
        )
        # Sanity: chain is currently valid.
        self.assertTrue(service.verify_audit_chain()["valid"])

        # Tamper with a middle entry and re-verify.
        tampered = repo.audit_logs[1]
        tampered.payload = dict(tampered.payload)
        tampered.payload["election_id"] = "tampered"
        result = service.verify_audit_chain()
        self.assertFalse(result["valid"])
        self.assertEqual(result["broken_at"], tampered.log_id)


class MyNumberAbsenceTest(unittest.TestCase):
    """Regression guard: every public response must omit individual-number fields."""

    FORBIDDEN_FIELDS = {"mynumber", "individual_number", "個人番号", "my_number"}

    def _assert_clean(self, obj: object) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                self.assertNotIn(key, self.FORBIDDEN_FIELDS)
                self._assert_clean(value)
        elif isinstance(obj, list):
            for item in obj:
                self._assert_clean(item)

    def test_responses_do_not_contain_individual_number(self) -> None:
        service = VotingService()
        auth = service.authenticate_voter("demo-2026", "CERT-CLEAN-1", "1980-01-01")
        token = service.issue_token("demo-2026", auth["voter_hash"])
        prepared = service.prepare_vote("demo-2026", "cand-a")
        receipt = service.submit_ballot(
            "demo-2026", token["blind_token"], prepared["encrypted_vote"], prepared["zk_proof"]
        )
        for payload in [
            auth,
            token,
            prepared,
            receipt,
            service.public_board("demo-2026"),
            service.tally("demo-2026"),
            service.verify_receipt("demo-2026", receipt["receipt_hash"]),
            service.verify_audit_chain(),
        ]:
            self._assert_clean(payload)


if __name__ == "__main__":
    unittest.main()
