from __future__ import annotations

import sys
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from internet_voting_system.app import VotingRequestHandler
from internet_voting_system.service import VotingService


class PrometheusMetricsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = VotingService()
        VotingRequestHandler.service = self.service
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), VotingRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def _cast_one(self) -> None:
        auth = self.service.authenticate_voter("demo-2026", "CERT-PROM-1", "1980-01-01")
        token = self.service.issue_token("demo-2026", auth["voter_hash"])
        prepared = self.service.prepare_vote("demo-2026", "cand-a")
        self.service.submit_ballot(
            "demo-2026", token["blind_token"], prepared["encrypted_vote"], prepared["zk_proof"]
        )

    def _get(self, path: str, headers: dict[str, str] | None = None) -> tuple[int, str, str]:
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", path, headers=headers or {})
            response = conn.getresponse()
            body = response.read().decode("utf-8")
            return response.status, response.getheader("Content-Type") or "", body
        finally:
            conn.close()

    def test_metrics_returns_json_by_default(self) -> None:
        self._cast_one()
        status, content_type, body = self._get("/metrics")
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertIn("total_ballots_recorded", body)

    def test_metrics_returns_prometheus_with_query_param(self) -> None:
        self._cast_one()
        status, content_type, body = self._get("/metrics?format=prometheus")
        self.assertEqual(status, 200)
        self.assertIn("text/plain", content_type)
        self.assertIn("version=0.0.4", content_type)
        self.assertIn("internet_voting_total_ballots_recorded 1", body)
        self.assertIn('internet_voting_election_ballots{election_id="demo-2026"', body)
        # Must end with a newline per the Prometheus spec.
        self.assertTrue(body.endswith("\n"))

    def test_metrics_returns_prometheus_via_accept_header(self) -> None:
        status, content_type, body = self._get("/metrics", {"Accept": "text/plain"})
        self.assertEqual(status, 200)
        self.assertIn("text/plain", content_type)
        self.assertIn("# HELP internet_voting_total_elections", body)

    def test_prometheus_output_does_not_leak_identity(self) -> None:
        self._cast_one()
        body = self.service.metrics_prometheus()
        for forbidden in ("voter_hash", "ballot_id", "receipt_hash", "candidate_id="):
            self.assertNotIn(forbidden, body)


class PostgresRepositoryImportTest(unittest.TestCase):
    """Verify the pg adapter raises a friendly error when psycopg is absent.

    We never import psycopg in CI (it would require libpq), so the class must
    surface a clean RuntimeError instead of an opaque ImportError. We force
    psycopg out of sys.modules just for the test to make the check
    deterministic on developer machines that have it installed.
    """

    def test_missing_psycopg_yields_runtime_error(self) -> None:
        # Pretend psycopg is not installed by inserting a sentinel that
        # raises on attribute access.
        saved = sys.modules.pop("psycopg", None)
        sys.modules["psycopg"] = None  # type: ignore[assignment]
        try:
            from internet_voting_system.postgres_repository import PostgresRepository
            with self.assertRaises(RuntimeError) as ctx:
                PostgresRepository(dsn="postgresql://invalid")
            self.assertIn("psycopg", str(ctx.exception))
        finally:
            del sys.modules["psycopg"]
            if saved is not None:
                sys.modules["psycopg"] = saved


if __name__ == "__main__":
    unittest.main()
