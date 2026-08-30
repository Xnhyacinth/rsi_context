from __future__ import annotations

from dataclasses import replace

import pytest

from rsicontext.analysis.longmemeval_qualification import (
    LONGMEMEVAL_V2_SMALL_RELEASED_FILES,
    LONGMEMEVAL_V2_SOURCE_REVISION,
    LONGMEMEVAL_V2_TOKENIZER_ID,
    LongMemEvalOfflineMeasurements,
    evaluate_longmemeval_offline_qualification,
)


def _passing() -> LongMemEvalOfflineMeasurements:
    source_files = LONGMEMEVAL_V2_SMALL_RELEASED_FILES
    return LongMemEvalOfflineMeasurements(
        tier="small",
        item_count=422,
        deterministic_item_count=294,
        weak_judge_item_count=128,
        excluded_image_item_count=29,
        unique_artifact_count=2,
        domain_counts=(("enterprise", 206), ("web", 216)),
        question_type_counts=(("dynamic-environment", 100), ("static-environment", 322)),
        evaluator_name_counts=(
            ("llm_abstention_checker", 128),
            ("mc_choice_match", 68),
            ("mc_choice_set_match", 1),
            ("norm_phrase_set_match", 199),
            ("norm_phrase_set_match_ordered", 26),
        ),
        haystack_size_min=100,
        haystack_size_max=100,
        source_token_min=200_000,
        source_token_median=300_000.0,
        source_token_p95=400_000,
        source_token_max=450_000,
        state_count_min=1_000,
        state_count_median=1_500.0,
        state_count_p95=2_000,
        state_count_max=2_100,
        single_chunk_token_max=120_000,
        binding_32k_rate=1.0,
        binding_128k_rate=1.0,
        binding_256k_rate=0.75,
        source_revision=LONGMEMEVAL_V2_SOURCE_REVISION,
        source_fingerprint="d" * 64,
        dataset_fingerprint="e" * 64,
        tokenizer_id=LONGMEMEVAL_V2_TOKENIZER_ID,
        source_file_sha256=source_files,
        released_file_sha256=source_files,
    )


def test_longmemeval_small_gate_accepts_real_long_memory_structure() -> None:
    result = evaluate_longmemeval_offline_qualification(_passing())

    assert result.passed is True
    assert result.failures == ()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            {
                "item_count": 421,
                "deterministic_item_count": 293,
                "domain_counts": (("enterprise", 205), ("web", 216)),
                "question_type_counts": (
                    ("dynamic-environment", 100),
                    ("static-environment", 321),
                ),
                "evaluator_name_counts": (
                    ("llm_abstention_checker", 128),
                    ("norm_phrase_set_match", 293),
                ),
            },
            "422",
        ),
        ({"deterministic_item_count": 293, "weak_judge_item_count": 129}, "294"),
        (
            {
                "evaluator_name_counts": (
                    ("llm_abstention_checker", 128),
                    ("mc_choice_match", 67),
                    ("mc_choice_set_match", 1),
                    ("new_unreviewed_metric", 1),
                    ("norm_phrase_set_match", 199),
                    ("norm_phrase_set_match_ordered", 26),
                )
            },
            "evaluator-family counts",
        ),
        ({"excluded_image_item_count": 28}, "29 image"),
        ({"unique_artifact_count": 1}, "shared histories"),
        ({"haystack_size_min": 99}, "100 trajectories"),
        ({"binding_128k_rate": 0.94}, "128K"),
        ({"source_revision": "1" * 40}, "source revision"),
        ({"tokenizer_id": "different@revision"}, "tokenizer identity"),
        (
            {"released_file_sha256": (("questions.jsonl", "0" * 64),)},
            "released file manifest",
        ),
        (
            {"source_file_sha256": (("questions.jsonl", "0" * 64),)},
            "released file checksums",
        ),
    ],
)
def test_longmemeval_small_gate_reports_preregistered_failures(
    change: dict[str, object], message: str
) -> None:
    result = evaluate_longmemeval_offline_qualification(
        replace(_passing(), **change)  # type: ignore[arg-type]
    )

    assert result.passed is False
    assert any(message in failure for failure in result.failures)


def test_measurements_do_not_expose_question_ids_answers_or_item_scores() -> None:
    measurements = _passing()

    assert not hasattr(measurements, "question_ids")
    assert not hasattr(measurements, "answers")
    assert not hasattr(measurements, "item_scores")
