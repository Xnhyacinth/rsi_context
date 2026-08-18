from __future__ import annotations

from dataclasses import replace

import pytest

from rsicontext.analysis.public_difficulty import (
    PublicOfflineMeasurements,
    PublicReaderMeasurements,
    answer_in_haystack,
    evaluate_public_offline_difficulty,
    evaluate_public_reader_difficulty,
)


def _passing() -> PublicOfflineMeasurements:
    return PublicOfflineMeasurements(
        cell_id="helmet-recall-niah-mk2-32k-to-8k",
        n_items=32,
        pack_budget_tokens=8192,
        median_source_tokens=32768.0,
        pack_binding_rate=1.0,
        answer_in_source_rate=1.0,
        packer_answer_rates=(("head-8k", 0.25), ("lexical-8k", 0.55)),
        packer_answer_disagreement=0.40,
    )


def test_public_offline_gate_accepts_a_binding_unsaturated_cell() -> None:
    result = evaluate_public_offline_difficulty(_passing())
    assert result.passed is True
    assert result.failures == ()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"n_items": 8}, "fewer than 16"),
        ({"median_source_tokens": 4096.0}, "does not exceed the pack budget"),
        ({"pack_binding_rate": 0.94}, "not binding"),
        ({"answer_in_source_rate": 0.89}, "missing from the source"),
        (
            {"packer_answer_rates": (("head-8k", 0.90), ("lexical-8k", 1.0))},
            "already places the answer",
        ),
        (
            {"packer_answer_rates": (("head-8k", 0.50), ("lexical-8k", 0.55))},
            "range is below 0.20",
        ),
        ({"packer_answer_disagreement": 0.19}, "disagreement"),
    ],
)
def test_public_offline_gate_reports_each_preregistered_failure(
    change: dict[str, object], message: str
) -> None:
    result = evaluate_public_offline_difficulty(replace(_passing(), **change))  # type: ignore[arg-type]
    assert result.passed is False
    assert any(message in failure for failure in result.failures)


def test_answer_in_haystack_is_casefold_substring() -> None:
    assert answer_in_haystack("The Value is Ottawa.", "ottawa")
    assert not answer_in_haystack("Ottawa is the capital.", "Toronto")


def _passing_reader() -> PublicReaderMeasurements:
    return PublicReaderMeasurements(
        cell_id="helmet-recall-qa2-128k-to-8k",
        n_items=32,
        gold_only_accuracy=0.90,
        no_context_accuracy=0.05,
        packer_scores=(("head", 0.30), ("lexical", 0.65)),
        packer_disagreement=0.35,
        replay_standard_deviation=0.01,
        median_meaningful_delta=0.10,
    )


def test_public_reader_gate_accepts_an_unsaturated_extractive_cell() -> None:
    result = evaluate_public_reader_difficulty(_passing_reader())
    assert result.passed is True
    assert result.failures == ()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"n_items": 8}, "fewer than 16"),
        ({"gold_only_accuracy": 0.84}, "gold-only"),
        ({"no_context_accuracy": 0.11}, "no-context"),
        ({"packer_scores": (("head", 0.10), ("lexical", 0.20))}, "outside [0.25, 0.75]"),
        ({"packer_scores": (("head", 0.90), ("lexical", 1.0))}, "saturates"),
        ({"packer_scores": (("head", 0.50), ("lexical", 0.55))}, "range is below 0.20"),
        ({"packer_disagreement": 0.19}, "disagreement"),
        ({"replay_standard_deviation": 0.02}, "replay noise"),
    ],
)
def test_public_reader_gate_reports_each_preregistered_failure(
    change: dict[str, object], message: str
) -> None:
    result = evaluate_public_reader_difficulty(replace(_passing_reader(), **change))  # type: ignore[arg-type]
    assert result.passed is False
    assert any(message in failure for failure in result.failures)
