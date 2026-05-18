"""In-process token-bucket rate limiter.

Designed for the prototype's stdlib HTTP server. Real deployments should put
this behind a CDN/WAF (Cloudflare, AWS WAF) that handles distributed rate
limiting; this module is the last line of defence against accidental local
floods and trivial replay scripts.

Buckets are keyed by ``(client_ip, group)``. Two groups are distinguished:

- ``"write"``: POST endpoints that mutate state. Tighter bucket.
- ``"read"``:  GET endpoints. Looser bucket.

The limiter never inspects request bodies, so it cannot leak voter identity.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


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
