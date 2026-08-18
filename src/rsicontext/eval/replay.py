"""Fixed-policy replay summaries."""

from dataclasses import dataclass
from statistics import fmean, pstdev, pvariance

from rsicontext.policy import Budget, ContextPolicy

from .core import EvaluationItem, FrozenReader, PolicyFactory, Scorer, _evaluate, exact_match


@dataclass(frozen=True, slots=True)
class ReplaySummary:
    scores: tuple[float, ...]
    mean: float
    variance: float
    standard_deviation: float


def replay(
    policy_factory: PolicyFactory,
    items: list[EvaluationItem] | tuple[EvaluationItem, ...],
    reader: FrozenReader,
    budget: Budget,
    *,
    repeats: int = 3,
    scorer: Scorer = exact_match,
) -> ReplaySummary:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    seen_policies: list[ContextPolicy] = []
    scores = tuple(
        _evaluate(
            policy_factory,
            items,
            reader,
            budget,
            scorer,
            seen_policies=seen_policies,
        ).score
        for _ in range(repeats)
    )
    return ReplaySummary(
        scores=scores,
        mean=fmean(scores),
        variance=pvariance(scores),
        standard_deviation=pstdev(scores),
    )
