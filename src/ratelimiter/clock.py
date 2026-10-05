import time
from typing import Protocol


class Clock(Protocol):
    """Source of the current time in seconds."""

    def now(self) -> float: ...


class SystemClock:
    """Clock backed by the wall clock."""

    def now(self) -> float:
        return time.time()
