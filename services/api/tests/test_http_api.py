from __future__ import annotations

import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from typing import Any

from internet_voting_system.app import VotingRequestHandler
from internet_voting_system.service import VotingService


class HttpApiTest(unittest.TestCase):
    def setUp(self) -> None:
        VotingRequestHandler.service = VotingService()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), VotingRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        try:
            conn.request(method, path, body=payload, headers=headers)
            response = conn.getresponse()
            raw = response.read()
            data = json.loads(raw.decode("utf-8")) if raw else {}
            return response.status, data
        finally:
            conn.close()

    def test_health_endpoint(self) -> None:
        status, data = self.request("GET", "/health")
        self.assertEqual(200, status)
        self.assertEqual({"status": "ok"}, data)

    def test_not_found_uses_standard_error_envelope(self) -> None:
        status, data = self.request("GET", "/missing")
        self.assertEqual(404, status)
        self.assertEqual("not_found", data["error"]["code"])
        self.assertIn("message", data["error"])

    def test_unknown_receipt_returns_found_false(self) -> None:
        missing_receipt = "0" * 64
        status, data = self.request("GET", f"/elections/demo-2026/receipts/{missing_receipt}")
        self.assertEqual(200, status)
        self.assertEqual({"found": False, "receipt_hash": missing_receipt}, data)

    def test_full_http_voting_flow_and_receipt_verification(self) -> None:
        status, auth = self.request(
            "POST",
            "/elections/demo-2026/authenticate",
            {"certificate_serial": "HTTP-CERT-000001", "birthdate": "1980-01-01"},
        )
        self.assertEqual(200, status)

        status, token = self.request(
            "POST",
            "/elections/demo-2026/issue-token",
            {"voter_hash": auth["voter_hash"]},
        )
        self.assertEqual(201, status)

        status, prepared = self.request(
            "POST",
            "/elections/demo-2026/prepare-vote",
            {"candidate_id": "cand-a"},
        )
        self.assertEqual(200, status)

        status, ballot = self.request(
            "POST",
            "/elections/demo-2026/ballots",
            {
                "blind_token": token["blind_token"],
                "encrypted_vote": prepared["encrypted_vote"],
                "zk_proof": prepared["zk_proof"],
            },
        )
        self.assertEqual(201, status)

        status, receipt = self.request(
            "GET",
            f"/elections/demo-2026/receipts/{ballot['receipt_hash']}",
        )
        self.assertEqual(200, status)
        self.assertTrue(receipt["found"])
        self.assertTrue(receipt["integrity_ok"])
        self.assertNotIn("voter_hash", json.dumps(receipt))


if __name__ == "__main__":
    unittest.main()
