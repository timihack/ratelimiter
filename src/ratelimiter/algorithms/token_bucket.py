from pydantic import Field
from pydantic.dataclasses import dataclass

from ratelimiter.algorithms.base import Backend, Result
from ratelimiter.errors import InvalidCostError


@dataclass(frozen=True)
class TokenBucketRule:
    """Token bucket parameters.

    Args:
        capacity: Maximum tokens held, which is also the maximum burst size.
        refill_rate: Tokens added per second.
    """

    capacity: int = Field(gt=0)
    refill_rate: float = Field(gt=0)


class TokenBucket:
    """Token bucket limiter delegating atomic state updates to a backend."""

    def __init__(self, backend: Backend, rule: TokenBucketRule) -> None:
        self._backend = backend
        self._rule = rule

    async def check(self, key: str, cost: int = 1) -> Result:
        """Consume ``cost`` tokens for ``key`` if available.

        Raises:
            InvalidCostError: If ``cost`` is below 1 or above the bucket capacity.
        """
        if not 1 <= cost <= self._rule.capacity:
            raise InvalidCostError(f"cost must be between 1 and {self._rule.capacity}, got {cost}")
        return await self._backend.token_bucket(
            key, self._rule.capacity, self._rule.refill_rate, cost
        )
