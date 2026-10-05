class RateLimiterError(Exception):
    """Base class for all errors raised by ratelimiter."""


class InvalidCostError(RateLimiterError, ValueError):
    """Raised when a request cost is non-positive or exceeds the limiter capacity."""
