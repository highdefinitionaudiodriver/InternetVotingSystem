from __future__ import annotations

import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys

from internet_voting_system.app import VotingRequestHandler
from internet_voting_system.service import VotingService

ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT / "tools"))

from smoke_check import SmokeConfig, run_smoke_check


class SmokeCheckToolTest(unittest.TestCase):
    def setUp(self) -> None:
        VotingRequestHandler.service = VotingService()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), VotingRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_smoke_check_completes_full_flow(self) -> None:
        report = run_smoke_check(SmokeConfig(base_url=self.base_url, election_id="demo-2026", timeout=5))
        self.assertEqual("ok", report["status"])
        self.assertEqual("demo-2026", report["election_id"])
        self.assertEqual(64, len(report["receipt_hash"]))
        self.assertEqual(64, len(report["audit_head_hash"]))


if __name__ == "__main__":
    unittest.main()
