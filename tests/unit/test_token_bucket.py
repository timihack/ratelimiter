import asyncio

import pytest
from pydantic import ValidationError

from ratelimiter.algorithms.base import Result
from ratelimiter.algorithms.token_bucket import TokenBucket, TokenBucketRule
from ratelimiter.backends.memory import MemoryBackend
from ratelimiter.errors import InvalidCostError
from tests.fakes import FakeClock


def make(capacity: int = 5, refill_rate: float = 1.0) -> tuple[TokenBucket, FakeClock]:
    clock = FakeClock()
    limiter = TokenBucket(MemoryBackend(clock), TokenBucketRule(capacity, refill_rate))
    return limiter, clock


async def test_first_request_allowed_with_full_bucket() -> None:
    limiter, _ = make()
    result = await limiter.check("k")
    assert result == Result(allowed=True, remaining=4, limit=5, reset_after=1.0, retry_after=0.0)


async def test_burst_exhausts_capacity_then_denies() -> None:
    limiter, _ = make()
    results = [await limiter.check("k") for _ in range(6)]
    assert [r.allowed for r in results] == [True] * 5 + [False]
    assert results[-1].remaining == 0
    assert results[-1].retry_after == pytest.approx(1.0)
    assert results[-1].reset_after == pytest.approx(5.0)


async def test_refill_over_time() -> None:
    limiter, clock = make()
    for _ in range(5):
        await limiter.check("k")
    clock.advance(2.0)
    result = await limiter.check("k")
    assert result.allowed
    assert result.remaining == 1


async def test_tokens_never_exceed_capacity() -> None:
    limiter, clock = make()
    await limiter.check("k")
    clock.advance(1000.0)
    result = await limiter.check("k")
    assert result.remaining == 4


async def test_fractional_refill_accumulates() -> None:
    limiter, clock = make(capacity=1, refill_rate=1.0)
    await limiter.check("k")
    clock.advance(0.5)
    assert not (await limiter.check("k")).allowed
    clock.advance(0.5)
    assert (await limiter.check("k")).allowed


async def test_keys_are_isolated() -> None:
    limiter, _ = make(capacity=1)
    assert (await limiter.check("a")).allowed
    assert (await limiter.check("b")).allowed
    assert not (await limiter.check("a")).allowed


async def test_cost_consumes_multiple_tokens() -> None:
    limiter, _ = make()
    result = await limiter.check("k", cost=3)
    assert result.allowed
    assert result.remaining == 2


async def test_denied_request_does_not_consume_tokens() -> None:
    limiter, _ = make(capacity=3)
    await limiter.check("k", cost=2)
    denied = await limiter.check("k", cost=2)
    assert not denied.allowed
    assert denied.remaining == 1
    assert (await limiter.check("k", cost=1)).allowed


@pytest.mark.parametrize("cost", [0, -1, 6])
async def test_invalid_cost_raises(cost: int) -> None:
    limiter, _ = make()
    with pytest.raises(InvalidCostError):
        await limiter.check("k", cost=cost)


async def test_idle_keys_expire() -> None:
    clock = FakeClock()
    backend = MemoryBackend(clock)
    limiter = TokenBucket(backend, TokenBucketRule(5, 1.0))
    await limiter.check("k")
    clock.advance(10.0)
    assert backend.size() == 1
    await limiter.check("other")
    assert backend.size() == 1


async def test_concurrent_checks_never_exceed_capacity() -> None:
    limiter, _ = make(capacity=10)
    results = await asyncio.gather(*(limiter.check("k") for _ in range(50)))
    assert sum(r.allowed for r in results) == 10


@pytest.mark.parametrize(("capacity", "refill_rate"), [(0, 1.0), (-1, 1.0), (5, 0.0), (5, -1.0)])
def test_rule_validation(capacity: int, refill_rate: float) -> None:
    with pytest.raises(ValidationError):
        TokenBucketRule(capacity, refill_rate)
