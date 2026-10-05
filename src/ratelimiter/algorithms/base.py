from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Result:
    """Outcome of a limit check. Durations are in seconds."""

    allowed: bool
    remaining: int
    limit: int
    reset_after: float
    retry_after: float


class Limiter(Protocol):
    """A rate limiter that decides whether a request for ``key`` may proceed."""

    async def check(self, key: str, cost: int = 1) -> Result: ...


class Backend(Protocol):
    """Storage that executes limit checks atomically."""

    async def token_bucket(
        self, key: str, capacity: int, refill_rate: float, cost: int
    ) -> Result: ...
