from __future__ import annotations

import signal
import unittest
from unittest import mock

from internet_voting_system import app as app_module
from internet_voting_system.service import VotingService


class MetricsSummaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = VotingService()
        self.election_id = "demo-2026"

    def _cast(self, cert: str, candidate: str) -> dict:
        auth = self.service.authenticate_voter(self.election_id, cert, "1980-01-01")
        token = self.service.issue_token(self.election_id, auth["voter_hash"])
        prepared = self.service.prepare_vote(self.election_id, candidate)
        return self.service.submit_ballot(
            self.election_id, token["blind_token"], prepared["encrypted_vote"], prepared["zk_proof"]
        )

    def test_metrics_summary_aggregates_only(self) -> None:
        self._cast("CERT-METRIC-1", "cand-a")
        self._cast("CERT-METRIC-2", "cand-b")
        m = self.service.metrics_summary()
        self.assertEqual(m["total_elections"], 1)
        self.assertEqual(m["total_ballots_recorded"], 2)
        self.assertGreaterEqual(m["audit_log_entries"], 2)
        elections = m["elections"]
        self.assertEqual(len(elections), 1)
        self.assertEqual(elections[0]["ballots_recorded"], 2)
        self.assertEqual(elections[0]["status"], "open")

    def test_metrics_summary_does_not_leak_identity_or_candidate_counts(self) -> None:
        self._cast("CERT-METRIC-3", "cand-c")
        m = self.service.metrics_summary()
        # No per-candidate breakdown — that lives in /tally only.
        self.assertNotIn("counts", m)
        self.assertNotIn("candidate", str(m).lower())
        # No voter identity fields anywhere in the response.
        flat = str(m)
        for forbidden in ("voter_hash", "certificate_serial", "mynumber", "individual_number"):
            self.assertNotIn(forbidden, flat)


class GracefulShutdownTest(unittest.TestCase):
    """Validate signal-handler installation without actually starting a server."""

    def test_install_graceful_shutdown_registers_handlers(self) -> None:
        fake_server = mock.Mock()
        installed: dict[int, object] = {}

        def fake_signal(sig: int, handler: object) -> None:
            installed[sig] = handler

        with mock.patch("internet_voting_system.app.signal.signal", side_effect=fake_signal):
            app_module.install_graceful_shutdown(fake_server)

        # SIGINT must always be handled. SIGTERM is handled on POSIX and our
        # code falls back gracefully when it is absent.
        self.assertIn(signal.SIGINT, installed)
        if hasattr(signal, "SIGTERM"):
            self.assertIn(signal.SIGTERM, installed)

    def test_handler_triggers_server_shutdown(self) -> None:
        fake_server = mock.Mock()
        captured: dict[str, object] = {}

        def fake_signal(sig: int, handler: object) -> None:
            captured.setdefault("handler", handler)

        with mock.patch("internet_voting_system.app.signal.signal", side_effect=fake_signal):
            app_module.install_graceful_shutdown(fake_server)

        # Simulate the OS firing the signal. Because the handler spawns a
        # daemon thread to call server.shutdown(), we must wait for it.
        with mock.patch("internet_voting_system.app.threading.Thread") as fake_thread:
            captured["handler"](signal.SIGINT, None)  # type: ignore[operator]
            # The handler must construct a thread whose target is shutdown.
            args, kwargs = fake_thread.call_args
            self.assertIs(kwargs["target"], fake_server.shutdown)
            fake_thread.return_value.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
