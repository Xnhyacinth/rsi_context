"""Pre-dispatch spend accounting for reader calls and researcher API cost."""

from __future__ import annotations

import math
from dataclasses import dataclass


class SpendCapError(RuntimeError):
    """Raised when a debit would exceed a committed experiment cap."""


def _nonnegative_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field} must be an integer")
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


def _nonnegative_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return number


@dataclass(frozen=True, slots=True)
class SpendCaps:
    max_reader_calls: int
    max_reader_input_tokens: int
    max_cost_usd: float
    max_gpu_seconds: float
    max_wall_seconds: float
    max_retries: int

    def __post_init__(self) -> None:
        for field in (
            "max_reader_calls",
            "max_reader_input_tokens",
        ):
            count = _nonnegative_int(getattr(self, field), field)
            if count <= 0:
                raise ValueError(f"{field} must be positive")
        _nonnegative_int(self.max_retries, "max_retries")
        _nonnegative_number(self.max_cost_usd, "max_cost_usd")
        for field in ("max_gpu_seconds", "max_wall_seconds"):
            seconds = _nonnegative_number(getattr(self, field), field)
            if seconds <= 0:
                raise ValueError(f"{field} must be positive")


@dataclass(frozen=True, slots=True)
class SpendSnapshot:
    reader_calls: int
    reader_input_tokens: int
    reader_output_tokens: int
    researcher_calls: int
    researcher_cost_usd: float
    gpu_seconds: float
    wall_seconds: float
    retries: int

    def to_ledger_pairs(self) -> tuple[tuple[str, int | float], ...]:
        return (
            ("gpu_seconds", self.gpu_seconds),
            ("reader_calls", self.reader_calls),
            ("reader_input_tokens", self.reader_input_tokens),
            ("reader_output_tokens", self.reader_output_tokens),
            ("researcher_calls", self.researcher_calls),
            ("researcher_cost_usd", self.researcher_cost_usd),
            ("retries", self.retries),
            ("wall_seconds", self.wall_seconds),
        )


class SpendLedger:
    """Authorize every debit against committed caps before work is dispatched."""

    def __init__(self, caps: SpendCaps) -> None:
        if not isinstance(caps, SpendCaps):
            raise TypeError("caps must be a SpendCaps value")
        self._caps = caps
        self._reader_calls = 0
        self._reader_input_tokens = 0
        self._reader_output_tokens = 0
        self._researcher_calls = 0
        self._researcher_cost_usd = 0.0
        self._gpu_seconds = 0.0
        self._wall_seconds = 0.0
        self._retries = 0

    @property
    def caps(self) -> SpendCaps:
        return self._caps

    def snapshot(self) -> SpendSnapshot:
        return SpendSnapshot(
            reader_calls=self._reader_calls,
            reader_input_tokens=self._reader_input_tokens,
            reader_output_tokens=self._reader_output_tokens,
            researcher_calls=self._researcher_calls,
            researcher_cost_usd=self._researcher_cost_usd,
            gpu_seconds=self._gpu_seconds,
            wall_seconds=self._wall_seconds,
            retries=self._retries,
        )

    def authorize_reader(
        self,
        *,
        calls: int = 1,
        input_tokens: int,
        output_tokens: int = 0,
        gpu_seconds: float = 0.0,
        wall_seconds: float = 0.0,
        retry: bool = False,
    ) -> None:
        calls = _nonnegative_int(calls, "calls")
        input_tokens = _nonnegative_int(input_tokens, "input_tokens")
        output_tokens = _nonnegative_int(output_tokens, "output_tokens")
        gpu_seconds = _nonnegative_number(gpu_seconds, "gpu_seconds")
        wall_seconds = _nonnegative_number(wall_seconds, "wall_seconds")
        if calls == 0:
            raise ValueError("reader authorization requires a positive call count")
        retries = self._retries + (1 if retry else 0)
        self._reject(
            reader_calls=self._reader_calls + calls,
            reader_input_tokens=self._reader_input_tokens + input_tokens,
            researcher_cost_usd=self._researcher_cost_usd,
            gpu_seconds=self._gpu_seconds + gpu_seconds,
            wall_seconds=self._wall_seconds + wall_seconds,
            retries=retries,
        )
        self._reader_calls += calls
        self._reader_input_tokens += input_tokens
        self._reader_output_tokens += output_tokens
        self._gpu_seconds += gpu_seconds
        self._wall_seconds += wall_seconds
        self._retries = retries

    def authorize_researcher(
        self,
        *,
        cost_usd: float,
        wall_seconds: float = 0.0,
        calls: int = 1,
    ) -> None:
        calls = _nonnegative_int(calls, "calls")
        cost_usd = _nonnegative_number(cost_usd, "cost_usd")
        wall_seconds = _nonnegative_number(wall_seconds, "wall_seconds")
        if calls == 0:
            raise ValueError("researcher authorization requires a positive call count")
        self._reject(
            reader_calls=self._reader_calls,
            reader_input_tokens=self._reader_input_tokens,
            researcher_cost_usd=self._researcher_cost_usd + cost_usd,
            gpu_seconds=self._gpu_seconds,
            wall_seconds=self._wall_seconds + wall_seconds,
            retries=self._retries,
        )
        self._researcher_calls += calls
        self._researcher_cost_usd += cost_usd
        self._wall_seconds += wall_seconds

    def _reject(
        self,
        *,
        reader_calls: int,
        reader_input_tokens: int,
        researcher_cost_usd: float,
        gpu_seconds: float,
        wall_seconds: float,
        retries: int,
    ) -> None:
        checks = (
            (reader_calls, self._caps.max_reader_calls, "reader_calls"),
            (reader_input_tokens, self._caps.max_reader_input_tokens, "reader_input_tokens"),
            (researcher_cost_usd, self._caps.max_cost_usd, "cost_usd"),
            (gpu_seconds, self._caps.max_gpu_seconds, "gpu_seconds"),
            (wall_seconds, self._caps.max_wall_seconds, "wall_seconds"),
            (retries, self._caps.max_retries, "retries"),
        )
        for actual, limit, name in checks:
            if actual > limit:
                raise SpendCapError(f"{name} cap would be exceeded")
