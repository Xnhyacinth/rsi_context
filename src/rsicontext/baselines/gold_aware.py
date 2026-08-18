"""Exhaustive gold-recall selector over the canonical V1 grammar.

This control sees visible gold chunk identities and does not call the frozen
reader. It is reported separately from five-call matched search.
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import fmean

from rsicontext.baselines.search import SearchObservation, SearchResult
from rsicontext.eval import EvaluationItem
from rsicontext.policy import (
    CANONICAL_POLICY_SPECS_V1,
    Budget,
    PolicySpecV1,
    PolicySpecV1Interpreter,
)


def gold_aware_select_v1(
    items: Sequence[EvaluationItem],
    budget: Budget,
    *,
    specs: Sequence[PolicySpecV1] = CANONICAL_POLICY_SPECS_V1,
) -> SearchResult:
    """Score every spec by mean gold-chunk recall without a target-reader call."""

    frozen_items = tuple(items)
    frozen_specs = tuple(specs)
    if not frozen_items:
        raise ValueError("gold-aware selection requires at least one item")
    if not frozen_specs:
        raise ValueError("gold-aware selection requires at least one spec")
    if any(not isinstance(item, EvaluationItem) for item in frozen_items):
        raise TypeError("items must contain EvaluationItem values")
    if any(not isinstance(spec, PolicySpecV1) for spec in frozen_specs):
        raise TypeError("specs must contain PolicySpecV1 values")
    if not isinstance(budget, Budget):
        raise TypeError("budget must be a Budget")

    interpreter = PolicySpecV1Interpreter()
    observations: list[SearchObservation] = []
    for spec in frozen_specs:
        policy = interpreter.materialize(spec)
        recalls: list[float] = []
        for item in frozen_items:
            if not item.gold_chunk_ids:
                raise ValueError("gold-aware selection requires gold chunk identities")
            pack = policy.assemble(item.artifact, item.query, budget)
            selected = {span.chunk_id for span in pack.spans}
            recalls.append(len(item.gold_chunk_ids & selected) / len(item.gold_chunk_ids))
        observations.append(SearchObservation(dict(spec.to_config()), fmean(recalls)))
    best_index = max(
        range(len(observations)),
        key=lambda index: (observations[index].score, -index),
    )
    return SearchResult(tuple(observations), best_index, len(observations))
