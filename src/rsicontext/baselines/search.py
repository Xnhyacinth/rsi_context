"""Finite search controls with explicit evaluator-call accounting."""

from __future__ import annotations

import itertools
import math
import random
from collections import deque
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeAlias

Scalar: TypeAlias = str | int | float | bool | None
Configuration: TypeAlias = dict[str, Scalar]
Evaluator: TypeAlias = Callable[[Configuration], float]


@dataclass(frozen=True, slots=True)
class SearchObservation:
    config: Configuration
    score: float


@dataclass(frozen=True, slots=True)
class SearchResult:
    observations: tuple[SearchObservation, ...]
    best_index: int
    metric_calls: int

    @property
    def best(self) -> SearchObservation:
        return self.observations[self.best_index]


def _space_axes(
    space: Mapping[str, Sequence[Scalar]],
) -> tuple[tuple[str, ...], tuple[tuple[Scalar, ...], ...]]:
    if not space:
        raise ValueError("search space must contain at least one parameter")
    names = tuple(space)
    values: list[tuple[Scalar, ...]] = []
    for name in names:
        options = tuple(space[name])
        if not options:
            raise ValueError(f"search parameter {name!r} has no values")
        if len(options) != len(set(options)):
            raise ValueError(f"search parameter {name!r} contains duplicate values")
        values.append(options)
    return names, tuple(values)


def _configurations(space: Mapping[str, Sequence[Scalar]]) -> Iterator[Configuration]:
    names, values = _space_axes(space)
    return (
        dict(zip(names, combination, strict=True)) for combination in itertools.product(*values)
    )


def _require_metric_calls(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("max_metric_calls must be an integer")
    if value <= 0:
        raise ValueError("max_metric_calls must be positive")
    return value


def _evaluate(
    configurations: Iterable[Configuration],
    evaluator: Evaluator,
    max_metric_calls: int,
) -> SearchResult:
    _require_metric_calls(max_metric_calls)
    observations: list[SearchObservation] = []
    for config in itertools.islice(configurations, max_metric_calls):
        raw_score = evaluator(dict(config))
        if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
            raise TypeError("evaluator score must be numeric")
        score = float(raw_score)
        if not math.isfinite(score):
            raise ValueError("evaluator returned a non-finite score")
        observations.append(SearchObservation(dict(config), score))
    if not observations:
        raise ValueError("search produced no observations")
    best_index = max(range(len(observations)), key=lambda index: observations[index].score)
    return SearchResult(tuple(observations), best_index, len(observations))


def grid_search(
    space: Mapping[str, Sequence[Scalar]],
    evaluator: Evaluator,
    *,
    max_metric_calls: int,
) -> SearchResult:
    """Evaluate the stable Cartesian-product prefix under a hard call budget."""

    return _evaluate(_configurations(space), evaluator, max_metric_calls)


def random_search(
    space: Mapping[str, Sequence[Scalar]],
    evaluator: Evaluator,
    *,
    max_metric_calls: int,
    seed: int = 0,
) -> SearchResult:
    """Sample finite configurations without replacement using a local RNG."""

    call_budget = _require_metric_calls(max_metric_calls)
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError("seed must be an integer")
    names, values = _space_axes(space)
    total = math.prod(len(options) for options in values)
    # This is a reproducible benchmark control, not security randomness.
    indices = random.Random(seed).sample(  # nosec B311
        range(total), min(call_budget, total)
    )

    def sampled_configurations() -> Iterator[Configuration]:
        for index in indices:
            positions: list[int] = []
            remainder = index
            for options in reversed(values):
                remainder, position = divmod(remainder, len(options))
                positions.append(position)
            selected = tuple(
                options[position]
                for options, position in zip(values, reversed(positions), strict=True)
            )
            yield dict(zip(names, selected, strict=True))

    configurations = sampled_configurations()
    return _evaluate(configurations, evaluator, max_metric_calls)


def _freeze(config: Configuration) -> tuple[tuple[str, Scalar], ...]:
    return tuple(sorted(config.items()))


def hamming_distance(left: Configuration, right: Configuration) -> int:
    """Count differing values between two configurations that share keys."""

    if set(left) != set(right):
        raise ValueError("configurations must share keys")
    return sum(left[key] != right[key] for key in left)


def sequential_search(
    space: Mapping[str, Sequence[Scalar]],
    evaluator: Evaluator,
    *,
    max_metric_calls: int,
    start: Configuration | None = None,
) -> SearchResult:
    """Walk Hamming-one neighbors from a start configuration in canonical order.

    The path is a breadth-first traversal of the Hamming-one graph and does not
    use gold evidence. Tie-breaking follows the stable Cartesian-product catalog.
    """

    _space_axes(space)
    catalog = [dict(config) for config in _configurations(space)]
    by_key = {_freeze(config): config for config in catalog}
    if start is None:
        origin = catalog[0]
    else:
        frozen_start = _freeze(dict(start))
        if frozen_start not in by_key:
            raise ValueError("start configuration is not in the search space")
        origin = by_key[frozen_start]

    def neighbors(config: Configuration) -> tuple[Configuration, ...]:
        return tuple(candidate for candidate in catalog if hamming_distance(config, candidate) == 1)

    budget = _require_metric_calls(max_metric_calls)
    ordered: list[Configuration] = []
    seen: set[tuple[tuple[str, Scalar], ...]] = {_freeze(origin)}
    queue: deque[Configuration] = deque([origin])
    while queue and len(ordered) < budget:
        node = queue.popleft()
        ordered.append(dict(node))
        for neighbor in neighbors(node):
            key = _freeze(neighbor)
            if key not in seen:
                seen.add(key)
                queue.append(neighbor)
    return _evaluate(ordered, evaluator, max_metric_calls)
