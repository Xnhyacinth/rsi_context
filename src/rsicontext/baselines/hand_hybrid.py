"""Named human-designed hybrid reference inside the frozen V1 grammar."""

from __future__ import annotations

from rsicontext.policy import (
    AllocatorV1,
    GraphHopsV1,
    OrderV1,
    PolicySpecV1,
    PositionReserveV1,
    SelectorV1,
)

HAND_HYBRID_SPEC_V1 = PolicySpecV1(
    SelectorV1.QUERY_BM25,
    GraphHopsV1.TWO,
    AllocatorV1.RANK,
    PositionReserveV1.NONE,
    OrderV1.EDGE_INTERLEAVE,
)
HAND_HYBRID_NAME = "hand-hybrid"
