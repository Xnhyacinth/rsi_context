"""Budget-matched non-agent reference optimizers."""

from rsicontext.baselines.gold_aware import gold_aware_select_v1
from rsicontext.baselines.hand_hybrid import HAND_HYBRID_NAME, HAND_HYBRID_SPEC_V1
from rsicontext.baselines.search import (
    SearchObservation,
    SearchResult,
    grid_search,
    hamming_distance,
    random_search,
    sequential_search,
)

__all__ = [
    "HAND_HYBRID_NAME",
    "HAND_HYBRID_SPEC_V1",
    "SearchObservation",
    "SearchResult",
    "gold_aware_select_v1",
    "grid_search",
    "hamming_distance",
    "random_search",
    "sequential_search",
]
