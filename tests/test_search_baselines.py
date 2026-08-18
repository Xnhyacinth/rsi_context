from __future__ import annotations

import itertools
from collections.abc import Iterable, Iterator

import pytest

from rsicontext.baselines.search import grid_search, random_search

Scalar = str | int | float | bool | None


def _numeric_score(config: dict[str, Scalar], key: str) -> float:
    value = config[key]
    assert isinstance(value, (int, float)) and not isinstance(value, bool)
    return float(value)


def test_grid_search_respects_metric_call_budget_and_keeps_best() -> None:
    result = grid_search(
        {"k": (1, 2, 3), "order": ("head", "tail")},
        lambda config: float(config["k"] == 2 and config["order"] == "tail"),
        max_metric_calls=4,
    )

    assert result.metric_calls == 4
    assert len(result.observations) == 4
    assert result.best.config == {"k": 2, "order": "tail"}
    assert result.best.score == 1.0


def test_random_search_is_seeded_and_does_not_repeat_configs() -> None:
    space = {"k": (1, 2, 3), "order": ("head", "tail")}
    first = random_search(
        space, lambda config: _numeric_score(config, "k"), max_metric_calls=5, seed=9
    )
    second = random_search(
        space, lambda config: _numeric_score(config, "k"), max_metric_calls=5, seed=9
    )

    assert first == second
    assert len({tuple(sorted(item.config.items())) for item in first.observations}) == 5


def test_search_rejects_budget_larger_than_finite_space() -> None:
    result = random_search(
        {"x": (1, 2)}, lambda config: _numeric_score(config, "x"), max_metric_calls=9
    )

    assert result.metric_calls == 2
    assert result.best.score == 2.0


def test_grid_search_only_consumes_the_budgeted_product_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_product = itertools.product

    def guarded_product(*values: Iterable[object]) -> Iterator[tuple[object, ...]]:
        for index, combination in enumerate(original_product(*values)):
            if index >= 3:
                raise AssertionError("Cartesian product was consumed beyond the call budget")
            yield combination

    monkeypatch.setattr("rsicontext.baselines.search.itertools.product", guarded_product)
    result = grid_search({"x": range(100), "y": range(100)}, lambda config: 0.0, max_metric_calls=3)

    assert result.metric_calls == 3


def test_search_rejects_boolean_budgets_and_seeds() -> None:
    with pytest.raises(TypeError, match="max_metric_calls"):
        grid_search({"x": (1,)}, lambda config: 0.0, max_metric_calls=True)
    with pytest.raises(TypeError, match="seed"):
        random_search({"x": (1,)}, lambda config: 0.0, max_metric_calls=1, seed=False)
