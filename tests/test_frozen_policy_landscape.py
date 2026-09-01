from __future__ import annotations

from rsicontext.eval import EvaluationItem, ReaderOutput, extractive_span_match
from rsicontext.experiment.frozen_policy_landscape import (
    build_interleaved_schedule,
    gold_recall,
    run_frozen_policy_landscape,
)
from rsicontext.policy import Artifact, Budget, ContextPack, DocumentChunk, TruncationPolicy


def _item() -> EvaluationItem:
    gold = DocumentChunk("gold", "doc", 0, 4, "the answer is amber", 4)
    noise = DocumentChunk("noise", "doc", 4, 8, "unrelated filler text", 4)
    artifact = Artifact("doc", (gold, noise))
    return EvaluationItem(
        item_id="q1",
        query="what colour",
        answer="amber",
        artifact=artifact,
        gold_chunk_ids=frozenset({"gold"}),
    )


class _GoldReader:
    def read(self, query: str, context: ContextPack) -> ReaderOutput:
        del query
        text = " ".join(span.text for span in context.spans)
        answer = "amber" if "amber" in text else "no"
        return ReaderOutput(answer=answer, input_tokens=8, output_tokens=1)


def test_interleaved_schedule_is_seeded_and_complete() -> None:
    first = build_interleaved_schedule(("a", "b"), ("head", "tail"), seed=7)
    second = build_interleaved_schedule(("a", "b"), ("head", "tail"), seed=7)
    assert first == second
    assert set(first) == {("a", "head"), ("a", "tail"), ("b", "head"), ("b", "tail")}


def test_frozen_landscape_scores_open_arms_without_imputing_zeros() -> None:
    item = _item()
    result = run_frozen_policy_landscape(
        items=(item,),
        factories={
            "head": lambda: TruncationPolicy("head"),
            "tail": lambda: TruncationPolicy("tail"),
        },
        reader=_GoldReader(),
        scorer=extractive_span_match,
        budget=Budget(4),
        schedule=(("q1", "head"), ("q1", "tail")),
    )
    scores = {arm.policy_name: arm.score for arm in result.arms}
    assert scores["head"] == 1.0
    assert scores["tail"] == 0.0
    assert result.reader_calls == 2
    assert result.rsi_launch_eligible is False
    pack = TruncationPolicy("head").assemble(item.artifact, item.query, Budget(4))
    assert gold_recall(pack, item) == 1.0
