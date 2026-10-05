import heapq
from dataclasses import dataclass

from ratelimiter.algorithms.base import Result
from ratelimiter.clock import Clock, SystemClock


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated_at: float
    expires_at: float


class MemoryBackend:
    """In-process backend for tests and development. Not shared across processes."""

    def __init__(self, clock: Clock | None = None) -> None:
        self._clock = clock or SystemClock()
        self._buckets: dict[str, _Bucket] = {}
        self._expiry: list[tuple[float, str]] = []

    def size(self) -> int:
        """Return the number of stored keys, including expired ones not yet evicted."""
        return len(self._buckets)

    async def token_bucket(self, key: str, capacity: int, refill_rate: float, cost: int) -> Result:
        """Atomically refill the bucket for ``key`` and try to consume ``cost`` tokens."""
        now = self._clock.now()
        self._evict(now)
        bucket = self._buckets.get(key)
        tokens = capacity if bucket is None else bucket.tokens
        updated_at = now if bucket is None else bucket.updated_at
        tokens = min(float(capacity), tokens + (now - updated_at) * refill_rate)

        allowed = tokens >= cost
        if allowed:
            tokens -= cost
        retry_after = 0.0 if allowed else (cost - tokens) / refill_rate
        reset_after = (capacity - tokens) / refill_rate

        expires_at = now + reset_after
        self._buckets[key] = _Bucket(tokens, now, expires_at)
        heapq.heappush(self._expiry, (expires_at, key))
        return Result(allowed, int(tokens), capacity, reset_after, retry_after)

    def _evict(self, now: float) -> None:
        while self._expiry and self._expiry[0][0] <= now:
            expires_at, key = heapq.heappop(self._expiry)
            bucket = self._buckets.get(key)
            if bucket is not None and bucket.expires_at == expires_at:
                del self._buckets[key]
