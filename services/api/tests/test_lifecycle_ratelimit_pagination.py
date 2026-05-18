from __future__ import annotations

import threading
import time
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from internet_voting_system.app import VotingRequestHandler, build_rate_limiter_from_env
from internet_voting_system.rate_limit import RateLimiter
from internet_voting_system.service import VotingService


class ElectionCloseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = VotingService()
        self.election_id = "demo-2026"

    def test_close_election_blocks_further_submissions(self) -> None:
        # Confirm we can authenticate while the election is open.
        auth = self.service.authenticate_voter(self.election_id, "CERT-CLOSE-1", "1980-01-01")
        token = self.service.issue_token(self.election_id, auth["voter_hash"])
        prepared = self.service.prepare_vote(self.election_id, "cand-a")

        closed = self.service.close_election(self.election_id)
        self.assertEqual(closed["status"], "closed")

        # Token issued before closing must not be acceptable for new ballots.
        with self.assertRaises(ValueError) as ctx:
            self.service.submit_ballot(
                self.election_id, token["blind_token"], prepared["encrypted_vote"], prepared["zk_proof"]
            )
        self.assertIn("not open", str(ctx.exception))

        # Authenticate is also blocked.
        with self.assertRaises(ValueError):
            self.service.authenticate_voter(self.election_id, "CERT-CLOSE-2", "1980-01-01")

    def test_close_appends_audit_entry(self) -> None:
        before = len(self.service.repository.audit_logs)
        self.service.close_election(self.election_id)
        after = self.service.repository.audit_logs
        self.assertGreater(len(after), before)
        self.assertEqual(after[-1].event_type, "election_closed")


class RateLimiterUnitTest(unittest.TestCase):
    def test_token_bucket_blocks_after_burst(self) -> None:
        clock_value = [1000.0]
        rl = RateLimiter(
            write_capacity=3, write_refill_per_sec=1,
            read_capacity=3, read_refill_per_sec=1,
            clock=lambda: clock_value[0],
        )
        for _ in range(3):
            self.assertTrue(rl.check("1.2.3.4", "write"))
        self.assertFalse(rl.check("1.2.3.4", "write"))
        # Advance clock 2 seconds → 2 tokens refilled.
        clock_value[0] += 2
        self.assertTrue(rl.check("1.2.3.4", "write"))
        self.assertTrue(rl.check("1.2.3.4", "write"))
        self.assertFalse(rl.check("1.2.3.4", "write"))

    def test_separate_ips_have_independent_buckets(self) -> None:
        rl = RateLimiter(write_capacity=1, write_refill_per_sec=0)
        self.assertTrue(rl.check("a", "write"))
        self.assertFalse(rl.check("a", "write"))
        # Different IP gets its own bucket.
        self.assertTrue(rl.check("b", "write"))

    def test_build_rate_limiter_from_env_supports_custom_limits(self) -> None:
        rl = build_rate_limiter_from_env(
            {
                "IVS_RATE_LIMIT_WRITE_CAPACITY": "1",
                "IVS_RATE_LIMIT_WRITE_REFILL_PER_SEC": "0",
                "IVS_RATE_LIMIT_READ_CAPACITY": "2",
                "IVS_RATE_LIMIT_READ_REFILL_PER_SEC": "0",
            }
        )
        self.assertIsNotNone(rl)
        assert rl is not None
        self.assertTrue(rl.check("a", "write"))
        self.assertFalse(rl.check("a", "write"))
        self.assertTrue(rl.check("a", "read"))
        self.assertTrue(rl.check("a", "read"))
        self.assertFalse(rl.check("a", "read"))

    def test_build_rate_limiter_from_env_can_disable_limiter(self) -> None:
        self.assertIsNone(build_rate_limiter_from_env({"IVS_RATE_LIMIT_ENABLED": "false"}))

    def test_build_rate_limiter_from_env_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            build_rate_limiter_from_env({"IVS_RATE_LIMIT_WRITE_CAPACITY": "nope"})


class HttpRateLimitTest(unittest.TestCase):
    def setUp(self) -> None:
        VotingRequestHandler.service = VotingService()
        # Override the limiter with a tight bucket for the test.
        VotingRequestHandler.rate_limiter = RateLimiter(
            write_capacity=2, write_refill_per_sec=0,
            read_capacity=2, read_refill_per_sec=0,
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), VotingRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        # Restore default limiter so other tests start clean.
        VotingRequestHandler.rate_limiter = RateLimiter()

    def _get(self, path: str) -> int:
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", path)
            return conn.getresponse().status
        finally:
            conn.close()

    def test_read_endpoint_returns_429_after_quota(self) -> None:
        self.assertEqual(self._get("/elections/demo-2026"), 200)
        self.assertEqual(self._get("/elections/demo-2026"), 200)
        self.assertEqual(self._get("/elections/demo-2026"), 429)

    def test_health_and_metrics_are_exempt(self) -> None:
        # Hammer health and metrics. They must always succeed.
        for _ in range(10):
            self.assertEqual(self._get("/health"), 200)
            self.assertEqual(self._get("/metrics"), 200)


class AuditLogPaginationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = VotingService()
        VotingRequestHandler.service = self.service
        VotingRequestHandler.rate_limiter = None  # disable rate limiting
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), VotingRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]
        # Generate enough audit entries to need pagination.
        for i in range(10):
            self.service.authenticate_voter("demo-2026", f"CERT-PAGE-{i:03d}", "1980-01-01")

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        VotingRequestHandler.rate_limiter = RateLimiter()

    def _get_json(self, path: str) -> dict:
        import json
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            return json.loads(resp.read().decode("utf-8"))
        finally:
            conn.close()

    def test_limit_caps_returned_entries(self) -> None:
        page = self._get_json("/audit-log?limit=3")
        self.assertEqual(len(page["audit_log"]), 3)
        self.assertTrue(page["has_more"])
        self.assertGreater(page["next_after"], 0)

    def test_after_advances_cursor(self) -> None:
        first = self._get_json("/audit-log?limit=3")
        cursor = first["next_after"]
        second = self._get_json(f"/audit-log?after={cursor}&limit=3")
        # No overlap between pages.
        first_ids = {entry["log_id"] for entry in first["audit_log"]}
        second_ids = {entry["log_id"] for entry in second["audit_log"]}
        self.assertEqual(first_ids & second_ids, set())

    def test_invalid_limit_returns_400(self) -> None:
        page = self._get_json("/audit-log?limit=99999")
        self.assertEqual(page["error"]["code"], "bad_request")


if __name__ == "__main__":
    unittest.main()
