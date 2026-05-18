from __future__ import annotations

import threading
import unittest
from unittest import mock

from internet_voting_system.app import VotingRequestHandler, build_rate_limiter_from_env
from internet_voting_system.rate_limit import (
    RateLimiter,
    RateLimiterProtocol,
    RedisRateLimiter,
)
from internet_voting_system.repository import InMemoryRepository
from internet_voting_system.service import VotingService


class AuditCheckpointTest(unittest.TestCase):
    """Verify the checkpoint variant of `verify_audit_chain`."""

    def setUp(self) -> None:
        self.repo = InMemoryRepository()
        self.service = VotingService(repository=self.repo)
        # Generate a few audit entries so the chain has internal nodes.
        for i in range(5):
            self.service.authenticate_voter("demo-2026", f"CERT-CHK-{i:03d}", "1980-01-01")

    def test_full_verification_still_works(self) -> None:
        result = self.service.verify_audit_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["verified_from"], 0)
        self.assertEqual(len(result["head_hash"]), 64)

    def test_checkpoint_resumes_from_middle(self) -> None:
        # Pick an interior entry as the checkpoint.
        midpoint = self.repo.audit_logs[2]
        result = self.service.verify_audit_chain(
            from_log_id=midpoint.log_id,
            expected_prev_hash=midpoint.log_hash,
        )
        self.assertTrue(result["valid"], msg=result)
        self.assertEqual(result["verified_from"], midpoint.log_id)
        # head_hash must equal the last log's log_hash.
        self.assertEqual(result["head_hash"], self.repo.audit_logs[-1].log_hash)

    def test_checkpoint_with_wrong_hash_fails(self) -> None:
        midpoint = self.repo.audit_logs[2]
        result = self.service.verify_audit_chain(
            from_log_id=midpoint.log_id,
            expected_prev_hash="0" * 64,  # not the real hash
        )
        self.assertFalse(result["valid"])
        # The next entry after the checkpoint is what fails to match.
        self.assertEqual(result["broken_at"], midpoint.log_id + 1)

    def test_from_log_id_without_prev_hash_is_rejected(self) -> None:
        result = self.service.verify_audit_chain(from_log_id=3)
        self.assertFalse(result["valid"])
        self.assertEqual(result["broken_at"], 3)
        self.assertIn("expected_prev_hash", result["reason"])


class RedisRateLimiterFakeBackendTest(unittest.TestCase):
    """Validate RedisRateLimiter logic using a fake redis client.

    The fake client emulates the Lua script's state machine so we can prove
    the Python side wires the right arguments without requiring redis at all.
    """

    def setUp(self) -> None:
        self.fake_state: dict[str, dict[str, float]] = {}
        fake_client = mock.Mock()

        def _eval(script: str, numkeys: int, key: str, capacity: float, refill: float, now: float, ttl: float) -> int:
            entry = self.fake_state.setdefault(key, {"tokens": float(capacity), "last": float(now)})
            elapsed = max(0.0, float(now) - entry["last"])
            entry["tokens"] = min(float(capacity), entry["tokens"] + elapsed * float(refill))
            entry["last"] = float(now)
            if entry["tokens"] >= 1.0:
                entry["tokens"] -= 1.0
                return 1
            return 0

        fake_client.eval.side_effect = _eval
        self.client = fake_client
        self.rl = RedisRateLimiter(
            url="redis://fake",
            write_capacity=2,
            read_capacity=2,
            write_refill_per_sec=0,
            read_refill_per_sec=0,
            client=fake_client,
        )

    def test_check_consumes_tokens(self) -> None:
        self.assertTrue(self.rl.check("9.9.9.9", "write"))
        self.assertTrue(self.rl.check("9.9.9.9", "write"))
        self.assertFalse(self.rl.check("9.9.9.9", "write"))

    def test_satisfies_protocol(self) -> None:
        self.assertIsInstance(self.rl, RateLimiterProtocol)

    def test_unknown_group_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.rl.check("9.9.9.9", "delete")


class BuildRateLimiterFromEnvBackendTest(unittest.TestCase):
    def test_memory_backend_default(self) -> None:
        rl = build_rate_limiter_from_env({})
        self.assertIsInstance(rl, RateLimiter)

    def test_redis_backend_requires_url(self) -> None:
        with self.assertRaises(ValueError):
            build_rate_limiter_from_env({"IVS_RATE_LIMIT_BACKEND": "redis"})

    def test_redis_backend_constructs_with_url(self) -> None:
        # We can't actually connect to redis here; bypass the constructor by
        # patching the redis import path the lazy importer uses.
        with mock.patch.dict("sys.modules", {"redis": mock.MagicMock()}):
            rl = build_rate_limiter_from_env(
                {
                    "IVS_RATE_LIMIT_BACKEND": "redis",
                    "IVS_RATE_LIMIT_REDIS_URL": "redis://localhost:6379/0",
                }
            )
        self.assertIsInstance(rl, RedisRateLimiter)

    def test_invalid_backend_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            build_rate_limiter_from_env({"IVS_RATE_LIMIT_BACKEND": "etcd"})
        self.assertIn("memory", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
