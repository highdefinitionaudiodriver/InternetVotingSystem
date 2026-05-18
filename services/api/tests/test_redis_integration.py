from __future__ import annotations

import os
import time
import unittest

from internet_voting_system.rate_limit import RedisRateLimiter


REDIS_URL = os.environ.get("IVS_TEST_REDIS_URL")


@unittest.skipUnless(REDIS_URL, "IVS_TEST_REDIS_URL not set; skipping Redis integration tests")
class RedisRateLimiterIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import redis  # type: ignore[import-not-found]
        except ImportError as exc:
            raise unittest.SkipTest("redis package is not installed") from exc
        assert REDIS_URL is not None
        self.client = redis.Redis.from_url(REDIS_URL, decode_responses=False)
        try:
            self.client.ping()
        except Exception as exc:  # pragma: no cover - depends on external Redis
            raise unittest.SkipTest(f"Redis is not reachable: {exc}") from exc
        self.client.delete(
            "ivs:ratelimit:write:redis-integration",
            "ivs:ratelimit:read:redis-integration",
            "ivs:ratelimit:write:redis-ttl",
        )

    def tearDown(self) -> None:
        self.client.delete(
            "ivs:ratelimit:write:redis-integration",
            "ivs:ratelimit:read:redis-integration",
            "ivs:ratelimit:write:redis-ttl",
        )

    def test_token_bucket_is_shared_across_instances(self) -> None:
        assert REDIS_URL is not None
        first = RedisRateLimiter(
            url=REDIS_URL,
            write_capacity=2,
            write_refill_per_sec=0,
            read_capacity=1,
            read_refill_per_sec=0,
        )
        second = RedisRateLimiter(
            url=REDIS_URL,
            write_capacity=2,
            write_refill_per_sec=0,
            read_capacity=1,
            read_refill_per_sec=0,
        )

        self.assertTrue(first.check("redis-integration", "write"))
        self.assertTrue(second.check("redis-integration", "write"))
        self.assertFalse(first.check("redis-integration", "write"))

    def test_bucket_key_expires(self) -> None:
        assert REDIS_URL is not None
        limiter = RedisRateLimiter(
            url=REDIS_URL,
            write_capacity=1,
            write_refill_per_sec=0,
            read_capacity=1,
            read_refill_per_sec=0,
            ttl_seconds=1,
        )

        self.assertTrue(limiter.check("redis-ttl", "write"))
        self.assertFalse(limiter.check("redis-ttl", "write"))
        time.sleep(1.2)
        self.assertTrue(limiter.check("redis-ttl", "write"))


if __name__ == "__main__":
    unittest.main()
