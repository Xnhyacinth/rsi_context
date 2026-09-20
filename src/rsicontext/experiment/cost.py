"""Two-column cost accounting: improvement versus deployment (contract v2).

Offline one-shot records (``CostRecord``/``amortized_total``) and the online
per-task serve/update/maintain decomposition for continuously-updating
systems (``OnlineCostRecord``/``amortized_online_total``).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


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


def _optional_nonnegative_number(value: object, field: str) -> float | None:
    if value is None:
        return None
    return _nonnegative_number(value, field)


def _memory_ops(value: object, field: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field} must be a string-keyed mapping")
    result: dict[str, int] = {}
    for key, count in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field} keys must be non-empty strings")
        result[key] = _nonnegative_int(count, f"{field}[{key!r}]")
    return result


def _sum_optional(values: Iterable[float | None]) -> float | None:
    """Aggregate dollar estimates only when every constituent carries one."""

    total: float = 0.0
    for value in values:
        if value is None:
            return None
        total += float(value)
    return total


def _horizons(values: tuple[int, ...]) -> tuple[int, ...]:
    seen: list[int] = []
    for value in values:
        horizon = _nonnegative_int(value, "horizon")
        if horizon < 1:
            raise ValueError("horizon must be a positive integer")
        if horizon in seen:
            raise ValueError(f"horizon {horizon} is duplicated")
        seen.append(horizon)
    return tuple(seen)


@dataclass(frozen=True, slots=True)
class CostRecord:
    """One round/session of the two-column ledger.

    The improve column carries the improvement loop's own tokens, dollars,
    and wall time (the 2026 wave's under-reported ``C_improve``); the deploy
    column carries the per-deployment-unit service cost that a horizon N
    multiplies (the contract's ``C_deploy``). ``horizon_tasks`` is
    provenance: how many tasks the record's deployment covered.
    ``memory_ops`` is the session memory-op ledger (writes/reads/bytes/ops);
    it is copied on construction and must be treated as read-only.
    """

    improve_tokens_in: int
    improve_tokens_out: int
    improve_wall_seconds: float
    improve_dollar_estimate: float | None
    deploy_tokens_in: int
    deploy_tokens_out: int
    deploy_wall_seconds: float
    deploy_dollar_estimate: float | None
    memory_ops: Mapping[str, int]
    horizon_tasks: int

    def __post_init__(self) -> None:
        for field_name, value in (
            ("improve_tokens_in", self.improve_tokens_in),
            ("improve_tokens_out", self.improve_tokens_out),
            ("deploy_tokens_in", self.deploy_tokens_in),
            ("deploy_tokens_out", self.deploy_tokens_out),
        ):
            _nonnegative_int(value, field_name)
        for field_name, seconds in (
            ("improve_wall_seconds", self.improve_wall_seconds),
            ("deploy_wall_seconds", self.deploy_wall_seconds),
        ):
            _nonnegative_number(seconds, field_name)
        _optional_nonnegative_number(self.improve_dollar_estimate, "improve_dollar_estimate")
        _optional_nonnegative_number(self.deploy_dollar_estimate, "deploy_dollar_estimate")
        _nonnegative_int(self.horizon_tasks, "horizon_tasks")
        object.__setattr__(self, "memory_ops", _memory_ops(self.memory_ops, "memory_ops"))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "deploy_dollar_estimate": self.deploy_dollar_estimate,
            "deploy_tokens_in": self.deploy_tokens_in,
            "deploy_tokens_out": self.deploy_tokens_out,
            "deploy_wall_seconds": self.deploy_wall_seconds,
            "horizon_tasks": self.horizon_tasks,
            "improve_dollar_estimate": self.improve_dollar_estimate,
            "improve_tokens_in": self.improve_tokens_in,
            "improve_tokens_out": self.improve_tokens_out,
            "improve_wall_seconds": self.improve_wall_seconds,
            "memory_ops": dict(sorted(self.memory_ops.items())),
        }
        return payload


@dataclass(frozen=True, slots=True)
class TotalCost:
    """Amortized two-column cost at one deployment horizon N.

    ``C_total(N) = C_improve + N·C_deploy`` with per-token and wall
    components kept separate; the dollar estimate is present only when
    every contributing record carried one.
    """

    horizon: int
    improve_tokens_in: int
    improve_tokens_out: int
    improve_wall_seconds: float
    improve_dollar_estimate: float | None
    deploy_tokens_in: int
    deploy_tokens_out: int
    deploy_wall_seconds: float
    deploy_dollar_estimate: float | None

    @property
    def tokens_in(self) -> int:
        return self.improve_tokens_in + self.horizon * self.deploy_tokens_in

    @property
    def tokens_out(self) -> int:
        return self.improve_tokens_out + self.horizon * self.deploy_tokens_out

    @property
    def wall_seconds(self) -> float:
        return self.improve_wall_seconds + self.horizon * self.deploy_wall_seconds

    @property
    def dollar_estimate(self) -> float | None:
        if self.improve_dollar_estimate is None or self.deploy_dollar_estimate is None:
            return None
        return self.improve_dollar_estimate + self.horizon * self.deploy_dollar_estimate

    def to_dict(self) -> dict[str, Any]:
        return {
            "deploy_dollar_estimate": self.deploy_dollar_estimate,
            "deploy_tokens_in": self.deploy_tokens_in,
            "deploy_tokens_out": self.deploy_tokens_out,
            "deploy_wall_seconds": self.deploy_wall_seconds,
            "dollar_estimate": self.dollar_estimate,
            "horizon": self.horizon,
            "improve_dollar_estimate": self.improve_dollar_estimate,
            "improve_tokens_in": self.improve_tokens_in,
            "improve_tokens_out": self.improve_tokens_out,
            "improve_wall_seconds": self.improve_wall_seconds,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "wall_seconds": self.wall_seconds,
        }


def amortized_total(rec: CostRecord, horizon: int) -> TotalCost:
    """Amortize one record's two columns over a deployment horizon N."""

    _nonnegative_int(horizon, "horizon")
    if horizon < 1:
        raise ValueError("horizon must be a positive integer")
    return TotalCost(
        horizon=horizon,
        improve_tokens_in=rec.improve_tokens_in,
        improve_tokens_out=rec.improve_tokens_out,
        improve_wall_seconds=rec.improve_wall_seconds,
        improve_dollar_estimate=rec.improve_dollar_estimate,
        deploy_tokens_in=rec.deploy_tokens_in,
        deploy_tokens_out=rec.deploy_tokens_out,
        deploy_wall_seconds=rec.deploy_wall_seconds,
        deploy_dollar_estimate=rec.deploy_dollar_estimate,
    )


@dataclass(frozen=True, slots=True)
class OnlineCostRecord:
    """One served task's cost decomposition for a continuously-updating system.

    While serving task ``t``, such a system spends ``serve`` tokens on the
    task itself, ``update`` tokens revising strategy/state from the restricted
    feedback, and ``maintain`` tokens on memory consolidation/compaction
    (state hygiene that changes no strategy). Tokens are the core accounting;
    wall seconds default to 0.0 and dollar estimates to ``None`` per stream
    when unmeasured/unpriced, mirroring the two-column ledger's convention.
    """

    task_index: int
    serve_tokens_in: int = 0
    serve_tokens_out: int = 0
    update_tokens_in: int = 0
    update_tokens_out: int = 0
    maintain_tokens_in: int = 0
    maintain_tokens_out: int = 0
    serve_wall_seconds: float = 0.0
    update_wall_seconds: float = 0.0
    maintain_wall_seconds: float = 0.0
    serve_dollar_estimate: float | None = None
    update_dollar_estimate: float | None = None
    maintain_dollar_estimate: float | None = None

    def __post_init__(self) -> None:
        _nonnegative_int(self.task_index, "task_index")
        for field_name, value in (
            ("serve_tokens_in", self.serve_tokens_in),
            ("serve_tokens_out", self.serve_tokens_out),
            ("update_tokens_in", self.update_tokens_in),
            ("update_tokens_out", self.update_tokens_out),
            ("maintain_tokens_in", self.maintain_tokens_in),
            ("maintain_tokens_out", self.maintain_tokens_out),
        ):
            _nonnegative_int(value, field_name)
        for field_name, seconds in (
            ("serve_wall_seconds", self.serve_wall_seconds),
            ("update_wall_seconds", self.update_wall_seconds),
            ("maintain_wall_seconds", self.maintain_wall_seconds),
        ):
            _nonnegative_number(seconds, field_name)
        for field_name, dollars in (
            ("serve_dollar_estimate", self.serve_dollar_estimate),
            ("update_dollar_estimate", self.update_dollar_estimate),
            ("maintain_dollar_estimate", self.maintain_dollar_estimate),
        ):
            _optional_nonnegative_number(dollars, field_name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "maintain_dollar_estimate": self.maintain_dollar_estimate,
            "maintain_tokens_in": self.maintain_tokens_in,
            "maintain_tokens_out": self.maintain_tokens_out,
            "maintain_wall_seconds": self.maintain_wall_seconds,
            "serve_dollar_estimate": self.serve_dollar_estimate,
            "serve_tokens_in": self.serve_tokens_in,
            "serve_tokens_out": self.serve_tokens_out,
            "serve_wall_seconds": self.serve_wall_seconds,
            "task_index": self.task_index,
            "update_dollar_estimate": self.update_dollar_estimate,
            "update_tokens_in": self.update_tokens_in,
            "update_tokens_out": self.update_tokens_out,
            "update_wall_seconds": self.update_wall_seconds,
        }


def _stream_dollars(dollars: float | None, *components: float | int) -> float | None:
    """One cost stream's dollar contribution: priced, free, or unknown.

    A stream that never ran (every token/wall component zero) is free — no
    price required. A stream that ran but carries no price makes the total
    unknown (``None``), matching the ledger's convention that dollar
    estimates aggregate only when every contributing record carried one.
    """

    if dollars is not None:
        return dollars
    if all(component == 0 for component in components):
        return 0.0
    return None


def amortized_online_total(
    records: Sequence[OnlineCostRecord],
    initial_improve: CostRecord | None = None,
) -> TotalCost:
    """The online cost formula over a continuously-updating run.

    ``C_total(N) = C_initial_improve + Σ_t (C_serve,t + C_update,t +
    C_maintain,t)`` summed over the N task records, per token, wall, and
    dollar component. Only the improve column of ``initial_improve`` is read
    (its deploy column belongs to the offline model); an absent
    ``initial_improve`` contributes zero to every improve component. The
    returned ``horizon`` is pinned to 1 because the deploy column already
    sums the per-task costs over the tasks that actually executed — the
    offline ``C_improve + N·C_deploy`` is the special case where every
    task's cost equals the per-unit ``C_deploy``. Dollar estimates aggregate
    only when every stream that actually ran carried one; idle streams
    (zero tokens and zero wall) contribute zero without needing a price.
    """

    for record in records:
        if not isinstance(record, OnlineCostRecord):
            raise TypeError("online records must be OnlineCostRecord values")
    return TotalCost(
        horizon=1,
        improve_tokens_in=0 if initial_improve is None else initial_improve.improve_tokens_in,
        improve_tokens_out=0 if initial_improve is None else initial_improve.improve_tokens_out,
        improve_wall_seconds=(
            0.0 if initial_improve is None else initial_improve.improve_wall_seconds
        ),
        improve_dollar_estimate=(
            0.0 if initial_improve is None else initial_improve.improve_dollar_estimate
        ),
        deploy_tokens_in=sum(
            r.serve_tokens_in + r.update_tokens_in + r.maintain_tokens_in for r in records
        ),
        deploy_tokens_out=sum(
            r.serve_tokens_out + r.update_tokens_out + r.maintain_tokens_out for r in records
        ),
        deploy_wall_seconds=sum(
            r.serve_wall_seconds + r.update_wall_seconds + r.maintain_wall_seconds for r in records
        ),
        deploy_dollar_estimate=_sum_optional(
            dollars
            for r in records
            for dollars in (
                _stream_dollars(
                    r.serve_dollar_estimate,
                    r.serve_tokens_in,
                    r.serve_tokens_out,
                    r.serve_wall_seconds,
                ),
                _stream_dollars(
                    r.update_dollar_estimate,
                    r.update_tokens_in,
                    r.update_tokens_out,
                    r.update_wall_seconds,
                ),
                _stream_dollars(
                    r.maintain_dollar_estimate,
                    r.maintain_tokens_in,
                    r.maintain_tokens_out,
                    r.maintain_wall_seconds,
                ),
            )
        ),
    )


class CostLedger:
    """Accumulate CostRecords across rounds/sessions (reader calls all accounted)."""

    def __init__(self, records: Iterable[CostRecord] = ()) -> None:
        for record in records:
            if not isinstance(record, CostRecord):
                raise TypeError("ledger records must be CostRecord values")
        self._records: list[CostRecord] = list(records)

    @property
    def records(self) -> tuple[CostRecord, ...]:
        return tuple(self._records)

    def append(self, record: CostRecord) -> None:
        if not isinstance(record, CostRecord):
            raise TypeError("ledger records must be CostRecord values")
        self._records.append(record)

    def totals(self) -> TotalCost:
        """Sum both columns over every appended record (horizon 0 view)."""

        return TotalCost(
            horizon=0,
            improve_tokens_in=sum(r.improve_tokens_in for r in self._records),
            improve_tokens_out=sum(r.improve_tokens_out for r in self._records),
            improve_wall_seconds=sum(r.improve_wall_seconds for r in self._records),
            improve_dollar_estimate=_sum_optional(r.improve_dollar_estimate for r in self._records),
            deploy_tokens_in=sum(r.deploy_tokens_in for r in self._records),
            deploy_tokens_out=sum(r.deploy_tokens_out for r in self._records),
            deploy_wall_seconds=sum(r.deploy_wall_seconds for r in self._records),
            deploy_dollar_estimate=_sum_optional(r.deploy_dollar_estimate for r in self._records),
        )

    def memory_ops(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for record in self._records:
            for key, count in record.memory_ops.items():
                totals[key] = totals.get(key, 0) + count
        return dict(sorted(totals.items()))

    def summary(self, horizons: tuple[int, ...]) -> dict[int, TotalCost]:
        """The amortization table the contract requires, per horizon N.

        C_total(N) = C_improve + N·C_deploy, where C_deploy is the ledger's
        aggregated per-deployment-unit cost. Since the deploy column already
        sums per-unit costs across sessions, multiplying that aggregate by N
        charges every deployment unit's cost N times, which matches the
        per-unit-per-horizon reading of the contract's formula.
        """

        _horizons(horizons)
        totals = self.totals()
        table: dict[int, TotalCost] = {}
        for horizon in horizons:
            table[horizon] = TotalCost(
                horizon=horizon,
                improve_tokens_in=totals.improve_tokens_in,
                improve_tokens_out=totals.improve_tokens_out,
                improve_wall_seconds=totals.improve_wall_seconds,
                improve_dollar_estimate=totals.improve_dollar_estimate,
                deploy_tokens_in=totals.deploy_tokens_in,
                deploy_tokens_out=totals.deploy_tokens_out,
                deploy_wall_seconds=totals.deploy_wall_seconds,
                deploy_dollar_estimate=totals.deploy_dollar_estimate,
            )
        return table


def compose_from_ledger(
    *,
    reader_input_tokens: int = 0,
    reader_output_tokens: int = 0,
    reader_wall_seconds: float = 0.0,
    researcher_cost_usd: float | None = None,
    researcher_input_tokens: int = 0,
    researcher_output_tokens: int = 0,
    researcher_wall_seconds: float = 0.0,
    reader_dollar_estimate: float | None = None,
    memory_ops: Mapping[str, int] | None = None,
    horizon_tasks: int = 0,
) -> CostRecord:
    """Bridge the existing SpendLedger/RoundFeedback shapes to a CostRecord.

    Pure function over the values those objects already expose; no imports
    from ``experiment.ledger`` or ``experiment.feedback`` (the owner wires
    integration). Field mapping:

    - ``SpendSnapshot.reader_input_tokens`` / ``reader_output_tokens`` and
      (``.gpu_seconds`` or ``.wall_seconds``) land in the deploy column —
      reader calls are per-task deployment service cost; the optional
      ``reader_dollar_estimate`` pricing column is caller-supplied because
      SpendLedger tracks researcher dollars, not reader dollars.
    - ``researcher_cost_usd`` and/or TokenUsage-shaped researcher token
      fields (``input_tokens``/``output_tokens`` in the sense of
      ``researcher/streams.py``, whose ``total_input_tokens`` collapses
      cache fields) land in the improve column — the improvement loop's
      own tokens, dollars, and wall time (``C_improve``).
    - ``RoundFeedback.ledger`` keys are the same spend keys accepted here.
    """

    researcher_tokens_in = _nonnegative_int(researcher_input_tokens, "researcher_input_tokens")
    researcher_tokens_out = _nonnegative_int(researcher_output_tokens, "researcher_output_tokens")
    reader_tokens_in = _nonnegative_int(reader_input_tokens, "reader_input_tokens")
    reader_tokens_out = _nonnegative_int(reader_output_tokens, "reader_output_tokens")
    reader_wall = _nonnegative_number(reader_wall_seconds, "reader_wall_seconds")
    researcher_wall = _nonnegative_number(researcher_wall_seconds, "researcher_wall_seconds")
    researcher_dollars = _optional_nonnegative_number(researcher_cost_usd, "researcher_cost_usd")
    reader_dollars = _optional_nonnegative_number(reader_dollar_estimate, "reader_dollar_estimate")
    tasks = _nonnegative_int(horizon_tasks, "horizon_tasks")
    ops = _memory_ops({} if memory_ops is None else memory_ops, "memory_ops")
    return CostRecord(
        improve_tokens_in=researcher_tokens_in,
        improve_tokens_out=researcher_tokens_out,
        improve_wall_seconds=researcher_wall,
        improve_dollar_estimate=researcher_dollars,
        deploy_tokens_in=reader_tokens_in,
        deploy_tokens_out=reader_tokens_out,
        deploy_wall_seconds=reader_wall,
        deploy_dollar_estimate=reader_dollars,
        memory_ops=ops,
        horizon_tasks=tasks,
    )
