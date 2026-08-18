import math

import pytest

from rsicontext.eval import (
    EvaluationItem,
    ToyFrozenReader,
    causal_artifacts,
    contained_match,
    evaluate,
    exact_match,
    extractive_span_match,
    replay,
)
from rsicontext.policy import Artifact, Budget, ContextPack, DocumentChunk
from rsicontext.policy.baselines import LexicalPolicy


def make_item() -> EvaluationItem:
    chunks = (
        DocumentChunk("noise", "doc", 0, 20, "nothing useful here", 3),
        DocumentChunk("gold", "doc", 21, 63, "mars moons\nANSWER: Phobos and Deimos", 6),
    )
    return EvaluationItem(
        item_id="item",
        query="Which moons orbit Mars?",
        answer="Phobos and Deimos",
        artifact=Artifact("doc", chunks),
        gold_chunk_ids=frozenset({"gold"}),
    )


def test_toy_frozen_reader_and_scorer_are_deterministic() -> None:
    result = evaluate(
        LexicalPolicy,
        [make_item()],
        ToyFrozenReader(),
        Budget(max_tokens=6),
    )
    assert result.score == 1.0
    assert result.predictions == ("Phobos and Deimos",)
    assert result.reader_input_tokens == (10,)
    assert result.reader_output_tokens == (3,)
    assert exact_match("  PHOBOS   and Deimos ", "Phobos and Deimos") == 1.0


def test_replay_reports_within_policy_noise() -> None:
    summary = replay(
        LexicalPolicy,
        [make_item()],
        ToyFrozenReader(),
        Budget(max_tokens=6),
        repeats=3,
    )
    assert summary.scores == (1.0, 1.0, 1.0)
    assert summary.mean == 1.0
    assert summary.variance == 0.0
    assert summary.standard_deviation == 0.0


def test_evaluate_rejects_empty_duplicate_or_invalid_scores() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        evaluate(LexicalPolicy, [], ToyFrozenReader(), Budget(max_tokens=6))
    item = make_item()
    with pytest.raises(ValueError, match="unique"):
        evaluate(LexicalPolicy, [item, item], ToyFrozenReader(), Budget(max_tokens=6))
    for invalid_score in (-0.1, 1.1, math.nan, math.inf):
        with pytest.raises(ValueError, match=r"finite.*\[0, 1\]"):
            evaluate(
                LexicalPolicy,
                [item],
                ToyFrozenReader(),
                Budget(max_tokens=6),
                scorer=lambda prediction, reference, score=invalid_score: score,
            )


def test_replay_constructs_a_fresh_policy_for_every_evaluation() -> None:
    class FirstCallOnlyPolicy:
        def __init__(self) -> None:
            self.calls = 0

        def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
            del query, budget
            self.calls += 1
            spans = (artifact.chunks[1],) if self.calls == 1 else ()
            return ContextPack(
                spans=spans,
                ordering=tuple(chunk.chunk_id for chunk in spans),
                token_count=sum(chunk.token_count for chunk in spans),
            )

    summary = replay(
        FirstCallOnlyPolicy,
        [make_item()],
        ToyFrozenReader(),
        Budget(max_tokens=6),
        repeats=3,
    )

    assert summary.scores == (1.0, 1.0, 1.0)


def test_evaluate_rejects_unimplemented_reread_requests() -> None:
    class RereadPolicy:
        def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
            return ContextPack(request_reread="find the ledger")

    with pytest.raises(ValueError, match="not implemented"):
        evaluate(
            RereadPolicy,
            [make_item()],
            ToyFrozenReader(),
            Budget(max_tokens=32, max_free_text_tokens=32),
        )


def test_causal_variants_keep_and_drop_exact_gold_provenance() -> None:
    variants = causal_artifacts(make_item())
    assert tuple(chunk.chunk_id for chunk in variants["full"].chunks) == ("noise", "gold")
    assert tuple(chunk.chunk_id for chunk in variants["gold_only"].chunks) == ("gold",)
    assert tuple(chunk.chunk_id for chunk in variants["gold_drop"].chunks) == ("noise",)
    assert variants["no_context"].chunks == ()

    for artifact in variants.values():
        assert artifact.document_id == "doc"


def test_contained_match_accepts_answer_span_inside_prediction() -> None:
    assert contained_match("The country is France.", "France") == 1.0
    assert contained_match("france", "France") == 1.0
    assert contained_match("Paris", "France") == 0.0


def test_extractive_span_match_accepts_shorter_copied_span() -> None:
    assert extractive_span_match("3,677", "3,677 seated") == 1.0
    assert extractive_span_match("New York City", "Greenwich Village, New York City") == 1.0
    assert extractive_span_match("1986 to 2013", "from 1986 to 2013") == 1.0
    assert extractive_span_match("INSUFFICIENT", "yes") == 0.0
