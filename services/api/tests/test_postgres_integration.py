"""End-to-end tests against a real PostgreSQL instance.

These tests are SKIPPED unless the ``IVS_TEST_PG_DSN`` environment variable
points at a reachable PostgreSQL server. In CI we set this to the dsn of the
``services: postgres`` container; on developer machines the env var is
normally unset and the tests are skipped cleanly.

The tests mirror ``test_sqlite_repository.py`` so that any divergence in
semantics between the SQLite reference implementation and the Postgres
implementation is caught as a unit-test failure rather than a production
incident.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

PG_DSN = os.environ.get("IVS_TEST_PG_DSN")

SCHEMA_FILE = (
    Path(__file__).resolve().parents[1]
    / "internet_voting_system"
    / "sql"
    / "postgresql_schema.sql"
)


@unittest.skipUnless(PG_DSN, "IVS_TEST_PG_DSN not set; skipping Postgres integration tests")
class PostgresBackedServiceTest(unittest.TestCase):
    """Full voting flow against a real Postgres database.

    The setUp:
      1. Drops the ``voting`` schema (idempotent reset between tests).
      2. Re-applies ``postgresql_schema.sql``.
      3. Constructs a fresh ``PostgresRepository`` and ``VotingService``.
    """

    @classmethod
    def setUpClass(cls) -> None:
        try:
            import psycopg  # noqa: F401  (verify availability before tests run)
        except ImportError:
            raise unittest.SkipTest("psycopg not installed")
        cls._psycopg = __import__("psycopg")

    def setUp(self) -> None:
        from internet_voting_system.postgres_repository import PostgresRepository
        from internet_voting_system.service import VotingService

        with self._psycopg.connect(PG_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("DROP SCHEMA IF EXISTS voting CASCADE")
                cur.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
        self.repository = PostgresRepository(PG_DSN)
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
        receipt = self._cast_vote("CERT-PG-001", "cand-a")
        self.assertEqual(receipt["election_id"], self.election_id)
        tally = self.service.tally(self.election_id)
        self.assertEqual(tally["accepted_ballots"], 1)
        self.assertEqual(tally["counts"]["cand-a"], 1)

    def test_revote_replaces_earlier_ballot(self) -> None:
        auth = self.service.authenticate_voter(self.election_id, "CERT-PG-002", "1980-01-01")
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
        receipt = self._cast_vote("CERT-PG-003", "cand-b")
        verified = self.service.verify_receipt(self.election_id, receipt["receipt_hash"])
        self.assertTrue(verified["found"])
        self.assertTrue(verified["integrity_ok"])
        self.assertEqual(verified["ballot"]["ballot_id"], receipt["ballot_id"])

    def test_audit_chain_is_valid_after_voting(self) -> None:
        self._cast_vote("CERT-PG-004", "cand-a")
        self._cast_vote("CERT-PG-005", "cand-b")
        result = self.service.verify_audit_chain()
        self.assertTrue(result["valid"])
        self.assertGreaterEqual(result["total"], 2)
        self.assertEqual(len(result["head_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
