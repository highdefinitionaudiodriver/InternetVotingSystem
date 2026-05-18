from __future__ import annotations

import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from internet_voting_system.app import VotingRequestHandler
from internet_voting_system.rate_limit import RateLimiter
from internet_voting_system.service import VotingService


class AuditCheckpointsServiceTest(unittest.TestCase):
    """Pure-Python tests of the audit_checkpoints service method."""

    def setUp(self) -> None:
        self.service = VotingService()
        # Generate 12 audit entries so an interval of 5 yields multiple
        # internal checkpoints plus the tail entry.
        for i in range(12):
            self.service.authenticate_voter("demo-2026", f"CERT-CKP-{i:03d}", "1980-01-01")

    def test_default_interval_returns_only_tail(self) -> None:
        # With the default interval (1000) and ~13 entries, only the tail is
        # interesting; the response must still include it so clients always
        # have a usable checkpoint.
        result = self.service.audit_checkpoints()
        self.assertEqual(result["interval"], 1000)
        self.assertGreaterEqual(result["total_entries"], 12)
        self.assertEqual(len(result["checkpoints"]), 1)
        self.assertEqual(
            result["checkpoints"][0]["log_id"],
            self.service.repository.audit_logs[-1].log_id,
        )

    def test_small_interval_yields_multiple_checkpoints_newest_first(self) -> None:
        result = self.service.audit_checkpoints(interval=5, limit=10)
        ids = [cp["log_id"] for cp in result["checkpoints"]]
        # Newest first.
        self.assertEqual(ids, sorted(ids, reverse=True))
        # All hashes are SHA-256 hex.
        for cp in result["checkpoints"]:
            self.assertEqual(len(cp["log_hash"]), 64)

    def test_invalid_interval_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.service.audit_checkpoints(interval=0)

    def test_invalid_limit_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.service.audit_checkpoints(limit=0)
        with self.assertRaises(ValueError):
            self.service.audit_checkpoints(limit=101)

    def test_checkpoint_does_not_leak_identity(self) -> None:
        body = self.service.audit_checkpoints(interval=5)
        flat = str(body)
        for forbidden in ("voter_hash", "certificate_serial", "mynumber", "candidate"):
            self.assertNotIn(forbidden, flat)


class AuditCheckpointsRoundTripTest(unittest.TestCase):
    """Exercise the HTTP endpoint and prove the chain partially verifies."""

    def setUp(self) -> None:
        self.service = VotingService()
        VotingRequestHandler.service = self.service
        VotingRequestHandler.rate_limiter = None
        for i in range(8):
            self.service.authenticate_voter("demo-2026", f"CERT-CKE-{i:03d}", "1980-01-01")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), VotingRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        VotingRequestHandler.rate_limiter = RateLimiter()

    def _get_json(self, path: str) -> dict:
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", path)
            return json.loads(conn.getresponse().read().decode("utf-8"))
        finally:
            conn.close()

    def test_checkpoints_then_partial_verify(self) -> None:
        ckpts = self._get_json("/audit-log/checkpoints?interval=3&limit=10")
        self.assertGreater(len(ckpts["checkpoints"]), 0)

        # Use an interior checkpoint (not the tail) as the resume point.
        if len(ckpts["checkpoints"]) >= 2:
            mid = ckpts["checkpoints"][1]
        else:
            mid = ckpts["checkpoints"][0]

        verify = self._get_json(
            f"/audit-log/verify?from={mid['log_id']}&prev_hash={mid['log_hash']}"
        )
        self.assertTrue(verify["valid"], msg=verify)
        self.assertEqual(verify["verified_from"], mid["log_id"])

    def test_invalid_interval_returns_400(self) -> None:
        body = self._get_json("/audit-log/checkpoints?interval=0")
        self.assertEqual(body["error"]["code"], "bad_request")


if __name__ == "__main__":
    unittest.main()
