from __future__ import annotations

import pytest

from rsicontext.baselines.search import hamming_distance, sequential_search

Scalar = str | int | float | bool | None


def _numeric_score(config: dict[str, Scalar], key: str) -> float:
    value = config[key]
    assert isinstance(value, (int, float)) and not isinstance(value, bool)
    return float(value)


def test_hamming_distance_counts_changed_axes_only() -> None:
    left: dict[str, Scalar] = {"k": 1, "order": "head"}
    right: dict[str, Scalar] = {"k": 2, "order": "head"}

    assert hamming_distance(left, right) == 1
    assert hamming_distance(left, left) == 0


def test_sequential_search_walks_hamming_one_neighbors_from_start() -> None:
    space = {"k": (1, 2, 3), "order": ("head", "tail")}
    result = sequential_search(
        space,
        lambda config: _numeric_score(config, "k"),
        max_metric_calls=4,
        start={"k": 2, "order": "head"},
    )

    assert result.metric_calls == 4
    assert result.observations[0].config == {"k": 2, "order": "head"}
    assert all(
        hamming_distance(result.observations[0].config, item.config) <= 2
        for item in result.observations
    )
    seen = [tuple(sorted(item.config.items())) for item in result.observations]
    assert len(seen) == len(set(seen))
    assert result.best.config["k"] == 3


def test_sequential_search_rejects_start_outside_the_space() -> None:
    with pytest.raises(ValueError, match="start configuration"):
        sequential_search(
            {"x": (1, 2)},
            lambda config: 0.0,
            max_metric_calls=1,
            start={"x": 9},
        )
