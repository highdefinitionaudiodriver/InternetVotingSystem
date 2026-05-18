"""Token-bucket rate limiters.

Two implementations live here:

- :class:`RateLimiter` — in-process, ``dict``-backed. Safe across threads in
  a single API instance, but isolated per replica. This is the default.
- :class:`RedisRateLimiter` — shared across replicas via a Redis Lua
  script. Use this when multiple API pods sit behind a load balancer and
  must respect a single global budget per client IP.

Both classes satisfy the :class:`RateLimiterProtocol`, so the HTTP layer
calls ``.check(client_ip, group)`` without knowing which backend is wired
in. ``snapshot()`` is in-memory-only and is a test helper; the Redis
implementation returns an empty mapping rather than rescanning Redis.

The limiter never inspects request bodies, so it cannot leak voter identity.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


@runtime_checkable
class RateLimiterProtocol(Protocol):
    """Minimal surface every rate limiter must expose."""

    def check(self, client_ip: str, group: str) -> bool: ...
    def snapshot(self) -> dict: ...


# ---------------------------------------------------------------------------
# Redis-backed token bucket. Atomicity is achieved with a single EVAL of the
# Lua script below, so concurrent API replicas cannot race past the budget.
# ---------------------------------------------------------------------------

_REDIS_TOKEN_BUCKET_LUA = """
local key      = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill   = tonumber(ARGV[2])
local now      = tonumber(ARGV[3])
local ttl      = tonumber(ARGV[4])

local data    = redis.call('HMGET', key, 'tokens', 'last')
local tokens  = tonumber(data[1])
local last    = tonumber(data[2])
if tokens == nil then tokens = capacity end
if last   == nil then last   = now      end

local elapsed = math.max(0, now - last)
tokens = math.min(capacity, tokens + elapsed * refill)

local allowed = 0
if tokens >= 1 then
  tokens  = tokens - 1
  allowed = 1
end

redis.call('HMSET',  key, 'tokens', tokens, 'last', now)
redis.call('EXPIRE', key, ttl)
return allowed
"""


class RedisRateLimiter:
    """Distributed token-bucket backed by a Redis Lua script.

    Parameters mirror :class:`RateLimiter`. Construct via the public
    constructor or via :func:`build_rate_limiter_from_env` (see ``app.py``)
    which selects the backend from ``IVS_RATE_LIMIT_BACKEND``.

    Notes
    -----
    - The ``redis`` package is imported lazily so prototype installs that
      never set ``IVS_RATE_LIMIT_BACKEND=redis`` do not need it on disk.
    - The Lua script is registered once per process via ``script_load``.
    - The TTL on each bucket key is 300 seconds; idle buckets expire so
      Redis memory does not grow unbounded under churn.
    """

    KEY_PREFIX = "ivs:ratelimit:"

    def __init__(
        self,
        *,
        url: str,
        write_capacity: float = 30,
        read_capacity: float = 120,
        write_refill_per_sec: float = 5,
        read_refill_per_sec: float = 30,
        ttl_seconds: int = 300,
        client: object | None = None,
    ) -> None:
        if client is None:
            try:
                import redis  # type: ignore[import-not-found]
            except ImportError as exc:
                raise RuntimeError(
                    "RedisRateLimiter requires the 'redis' package. "
                    "Install it with `pip install 'redis>=5'`."
                ) from exc
            self._client = redis.Redis.from_url(url, decode_responses=False)
        else:
            # Tests inject a fake Redis client. Must support .eval() and .ping().
            self._client = client
        self._capacity = {"write": float(write_capacity), "read": float(read_capacity)}
        self._refill = {"write": float(write_refill_per_sec), "read": float(read_refill_per_sec)}
        self._ttl = int(ttl_seconds)
        self._url = url

    def check(self, client_ip: str, group: str) -> bool:
        if group not in self._capacity:
            raise ValueError(f"unknown rate-limit group: {group!r}")
        key = f"{self.KEY_PREFIX}{group}:{client_ip}"
        now = time.time()
        result = self._client.eval(
            _REDIS_TOKEN_BUCKET_LUA,
            1,
            key,
            self._capacity[group],
            self._refill[group],
            now,
            self._ttl,
        )
        return int(result) == 1

    def snapshot(self) -> dict:
        # Implementation detail: rescanning Redis would be a privacy and
        # performance footgun in production. Test code can introspect via
        # the injected fake client directly.
        return {}


class RateLimiter:
    """Thread-safe token-bucket implementation.

    Parameters
    ----------
    write_capacity, read_capacity:
        Maximum burst per (ip, group). Defaults: 30 writes / 120 reads.
    write_refill_per_sec, read_refill_per_sec:
        Steady-state allowance per second. Defaults: 5 writes/s, 30 reads/s.
    """

    def __init__(
        self,
        *,
        write_capacity: float = 30,
        read_capacity: float = 120,
        write_refill_per_sec: float = 5,
        read_refill_per_sec: float = 30,
        clock: callable = time.monotonic,
    ) -> None:
        self._capacity = {"write": float(write_capacity), "read": float(read_capacity)}
        self._refill = {"write": float(write_refill_per_sec), "read": float(read_refill_per_sec)}
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._lock = threading.Lock()
        self._clock = clock

    def check(self, client_ip: str, group: str) -> bool:
        """Return True if the request is allowed; consume one token if so."""
        if group not in self._capacity:
            raise ValueError(f"unknown rate-limit group: {group!r}")
        now = self._clock()
        with self._lock:
            key = (client_ip, group)
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=self._capacity[group], last_refill=now)
                self._buckets[key] = bucket
            elapsed = max(0.0, now - bucket.last_refill)
            bucket.tokens = min(
                self._capacity[group],
                bucket.tokens + elapsed * self._refill[group],
            )
            bucket.last_refill = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True
            return False

    def snapshot(self) -> dict[tuple[str, str], float]:
        """Return a copy of remaining tokens per bucket. Test helper only."""
        with self._lock:
            return {key: bucket.tokens for key, bucket in self._buckets.items()}
