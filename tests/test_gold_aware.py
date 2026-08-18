from __future__ import annotations

from rsicontext.baselines.gold_aware import gold_aware_select_v1
from rsicontext.eval import EvaluationItem
from rsicontext.policy import (
    AllocatorV1,
    Artifact,
    Budget,
    DocumentChunk,
    GraphHopsV1,
    OrderV1,
    PolicySpecV1,
    PositionReserveV1,
    SelectorV1,
)


def _item() -> EvaluationItem:
    chunks = (
        DocumentChunk("ck-a", "doc", 0, 4, "needle shared1x evidence", 4),
        DocumentChunk("ck-b", "doc", 5, 9, "shared1x other filler", 4),
        DocumentChunk("ck-c", "doc", 10, 14, "unrelated prose here", 4),
    )
    return EvaluationItem(
        item_id="item-1",
        query="needle",
        answer="secret",
        artifact=Artifact("doc", chunks),
        gold_chunk_ids=frozenset({"ck-a"}),
    )


def test_gold_aware_selector_scores_recall_without_a_reader() -> None:
    spec = PolicySpecV1(
        SelectorV1.QUERY_BM25,
        GraphHopsV1.ZERO,
        AllocatorV1.RANK,
        PositionReserveV1.NONE,
        OrderV1.RELEVANCE,
    )
    result = gold_aware_select_v1((_item(),), Budget(max_tokens=4, max_chunks=1), specs=(spec,))

    assert result.metric_calls == 1
    assert result.best.score == 1.0
    assert result.best.config["selector"] == "query_bm25"
