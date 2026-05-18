"""End-to-end SDK tests against an in-process VotingRequestHandler."""

from __future__ import annotations

import inspect
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

# Allow this test file to be discovered both via
#   `cd clients/python && python -m unittest discover -s tests`
# and from the repository root by `python tools/check_all.py`.
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "clients" / "python"))
sys.path.insert(0, str(ROOT / "services" / "api"))

from ivs_client import ApiError, VotingClient
from internet_voting_system.app import VotingRequestHandler
from internet_voting_system.rate_limit import RateLimiter
from internet_voting_system.service import VotingService


class _ServerFixture:
    def __enter__(self) -> str:
        VotingRequestHandler.service = VotingService()
        # Disable rate limiting so tests can fire many requests in a row.
        VotingRequestHandler.rate_limiter = None
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), VotingRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def __exit__(self, *_exc: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        VotingRequestHandler.rate_limiter = RateLimiter()


class VotingClientHappyPathTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = _ServerFixture()
        self.base_url = self.fixture.__enter__()
        self.client = VotingClient(self.base_url, timeout=5)
        self.service = VotingRequestHandler.service

    def tearDown(self) -> None:
        self.fixture.__exit__(None, None, None)

    def test_health_and_listing(self) -> None:
        self.assertEqual(self.client.health()["status"], "ok")
        elections = self.client.list_elections()
        self.assertTrue(any(e["election_id"] == "demo-2026" for e in elections))

    def test_metrics_text_and_json(self) -> None:
        self.assertIn("total_ballots_recorded", self.client.metrics())
        prom = self.client.metrics(prometheus=True)
        self.assertIsInstance(prom, str)
        self.assertIn("internet_voting_total_elections", prom)

    def test_receipt_round_trip_and_local_replay(self) -> None:
        # Drive one full ballot via the service so the API has data to verify.
        auth = self.service.authenticate_voter("demo-2026", "CERT-SDK-001", "1980-01-01")
        token = self.service.issue_token("demo-2026", auth["voter_hash"])
        prepared = self.service.prepare_vote("demo-2026", "cand-a")
        receipt = self.service.submit_ballot(
            "demo-2026",
            token["blind_token"],
            prepared["encrypted_vote"],
            prepared["zk_proof"],
        )

        verify = self.client.verify_receipt("demo-2026", receipt["receipt_hash"])
        self.assertTrue(verify["found"])
        self.assertTrue(verify["integrity_ok"])

        # Server-side audit verification.
        server_verify = self.client.verify_audit_chain()
        self.assertTrue(server_verify["valid"])

        # Local replay must agree byte-for-byte.
        local = self.client.verify_audit_chain_locally()
        self.assertTrue(local["valid"], msg=local)
        self.assertEqual(local["head_hash"], server_verify["head_hash"])

    def test_checkpoint_then_partial_verify(self) -> None:
        # Generate some audit entries.
        for i in range(6):
            self.service.authenticate_voter("demo-2026", f"CERT-SDK-CKP-{i:03d}", "1980-01-01")
        cps = self.client.audit_checkpoints(interval=2, limit=10)
        latest = cps["checkpoints"][0]
        result = self.client.verify_audit_chain(
            from_log_id=latest["log_id"], prev_hash=latest["log_hash"]
        )
        self.assertTrue(result["valid"], msg=result)

    def test_api_error_envelope_surfaces_through_exception(self) -> None:
        with self.assertRaises(ApiError) as ctx:
            self.client.verify_receipt("demo-2026", "not-hex")
        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(ctx.exception.code, "bad_request")


class VotingClientSurfaceTest(unittest.TestCase):
    """Surface-level invariants checked without a running server."""

    FORBIDDEN = ("mynumber", "individual_number", "個人番号", "my_number")

    def test_no_public_method_exposes_individual_number_parameter(self) -> None:
        for name, member in inspect.getmembers(VotingClient, predicate=inspect.isfunction):
            if name.startswith("_"):
                continue
            sig = inspect.signature(member)
            for param in sig.parameters:
                for forbidden in self.FORBIDDEN:
                    self.assertNotIn(
                        forbidden.lower(),
                        param.lower(),
                        f"VotingClient.{name} parameter {param!r} matches forbidden token {forbidden!r}",
                    )

    def test_base_url_must_be_http_or_https(self) -> None:
        with self.assertRaises(ValueError):
            VotingClient("ftp://example.com")


if __name__ == "__main__":
    unittest.main()
