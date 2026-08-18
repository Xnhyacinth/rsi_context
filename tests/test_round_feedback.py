from __future__ import annotations

from rsicontext.experiment.feedback import RoundFeedback


def test_round_feedback_bytes_are_canonical_and_order_sensitive() -> None:
    first = RoundFeedback(
        round_index=0,
        visible_item_order=("a", "b"),
        parent_predictions=(("a", "yes"), ("b", "no")),
        parent_scores=(("a", 1.0), ("b", 0.0)),
        gold_chunk_ids=(("a", ("ck-1",)), ("b", ("ck-2",))),
        gold_texts=(("a", ("gold a",)), ("b", ("gold b",))),
        ledger=(("reader_calls", 4), ("researcher_cost_usd", 0.0)),
    )
    same = RoundFeedback(
        round_index=0,
        visible_item_order=("a", "b"),
        parent_predictions=(("a", "yes"), ("b", "no")),
        parent_scores=(("a", 1.0), ("b", 0.0)),
        gold_chunk_ids=(("a", ("ck-1",)), ("b", ("ck-2",))),
        gold_texts=(("a", ("gold a",)), ("b", ("gold b",))),
        ledger=(("reader_calls", 4), ("researcher_cost_usd", 0.0)),
    )
    reordered = RoundFeedback(
        round_index=0,
        visible_item_order=("b", "a"),
        parent_predictions=(("b", "no"), ("a", "yes")),
        parent_scores=(("b", 0.0), ("a", 1.0)),
        gold_chunk_ids=(("b", ("ck-2",)), ("a", ("ck-1",))),
        gold_texts=(("b", ("gold b",)), ("a", ("gold a",))),
        ledger=(("reader_calls", 4), ("researcher_cost_usd", 0.0)),
    )

    assert first.canonical_bytes() == same.canonical_bytes()
    assert first.sha256() == same.sha256()
    assert first.canonical_bytes() != reordered.canonical_bytes()
    assert first.sha256() != reordered.sha256()
