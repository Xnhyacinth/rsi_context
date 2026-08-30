from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from rsicontext.analysis.musique_qualification import (
    MuSiQueOfflineMeasurements,
    evaluate_musique_offline_qualification,
    measure_musique_evaluator_items,
    measure_musique_records,
)
from rsicontext.datasets.musique import musique_answerable_record
from rsicontext.datasets.musique_long_context import pack_musique_long_context
from rsicontext.registry.tokenizer import verify_tokenizer_snapshot


def _passing() -> MuSiQueOfflineMeasurements:
    return MuSiQueOfflineMeasurements(
        n_items=100,
        duplicate_item_ids=0,
        hop_counts=((2, 50), (3, 30), (4, 20)),
        pack_budget_tokens=8192,
        source_token_min=20_000,
        source_token_median=32_000.0,
        source_token_p95=40_000,
        source_token_max=45_000,
        pack_binding_rate=1.0,
        answer_in_support_rate=1.0,
        answer_in_nonsupport_rate=0.0,
        intermediate_answers_in_support_rate=1.0,
        intermediate_answers_in_nonsupport_rate=0.0,
        source_sha256="a" * 64,
        official_source_sha256="a" * 64,
        source_revision="1" * 40,
        tokenizer_id="model@revision",
    )


def test_musique_offline_gate_accepts_a_pinned_causal_long_source() -> None:
    result = evaluate_musique_offline_qualification(_passing())

    assert result.passed is True
    assert result.failures == ()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"n_items": 39, "hop_counts": ((2, 20), (3, 10), (4, 9))}, "fewer than 40"),
        ({"duplicate_item_ids": 1}, "duplicate"),
        ({"hop_counts": ((2, 100),)}, "fewer than two hop strata"),
        ({"pack_binding_rate": 0.94}, "not binding"),
        ({"answer_in_support_rate": 0.94}, "supporting evidence"),
        ({"answer_in_nonsupport_rate": 0.01}, "non-supporting evidence"),
        (
            {"intermediate_answers_in_support_rate": 0.94},
            "intermediate answers are absent",
        ),
        ({"intermediate_answers_in_nonsupport_rate": 0.01}, "intermediate answer appears"),
        ({"official_source_sha256": None}, "official source bytes"),
    ],
)
def test_musique_offline_gate_reports_each_preregistered_failure(
    change: dict[str, object], message: str
) -> None:
    result = evaluate_musique_offline_qualification(replace(_passing(), **change))  # type: ignore[arg-type]

    assert result.passed is False
    assert any(message in failure for failure in result.failures)


def _raw(item_id: str, *, answer_in_decoy: bool) -> dict[str, object]:
    answer = "target answer"
    bridge = f"{item_id} intermediate"
    decoy = f"A decoy repeats {answer}." if answer_in_decoy else "A clean decoy."
    return {
        "id": item_id,
        "paragraphs": [
            {
                "idx": 0,
                "title": f"{item_id} First",
                "paragraph_text": f"The bridge entity is {bridge}.",
                "is_supporting": True,
            },
            {
                "idx": 1,
                "title": f"{item_id} Second",
                "paragraph_text": f"The result is {answer}.",
                "is_supporting": True,
            },
            {
                "idx": 2,
                "title": f"{item_id} Decoy",
                "paragraph_text": decoy,
                "is_supporting": False,
            },
        ],
        "question": "What is the result?",
        "question_decomposition": [
            {
                "id": f"{item_id}-1",
                "question": "Find the bridge",
                "answer": bridge,
                "paragraph_support_idx": 0,
            },
            {
                "id": f"{item_id}-2",
                "question": "Use the bridge",
                "answer": answer,
                "paragraph_support_idx": 1,
            },
        ],
        "answer": answer,
        "answer_aliases": [],
        "answerable": True,
    }


def test_measurement_is_aggregate_only_and_detects_answer_leakage() -> None:
    records = (
        musique_answerable_record(_raw("one", answer_in_decoy=False)),
        musique_answerable_record(_raw("two", answer_in_decoy=True)),
    )

    measurements = measure_musique_records(
        records,
        token_counter=lambda text: len(text.split()),
        pack_budget_tokens=8,
        source_sha256="a" * 64,
        source_revision="1" * 40,
        official_source_sha256=None,
        tokenizer_id="word-counter@test",
    )

    assert measurements.n_items == 2
    assert measurements.hop_counts == ((2, 2),)
    assert measurements.answer_in_support_rate == 1.0
    assert measurements.answer_in_nonsupport_rate == 0.5
    assert measurements.intermediate_answers_in_support_rate == 1.0
    assert measurements.intermediate_answers_in_nonsupport_rate == 0.0
    assert measurements.source_token_min <= measurements.source_token_max
    assert not hasattr(measurements, "item_ids")
    assert not hasattr(measurements, "answers")


def test_measures_packed_evaluator_items_without_emitting_labels() -> None:
    target = musique_answerable_record(_raw("target", answer_in_decoy=False))
    distractors = tuple(
        musique_answerable_record(_raw(f"d{index}", answer_in_decoy=False)) for index in range(20)
    )
    packed = pack_musique_long_context(
        target,
        distractors,
        token_counter=lambda text: len(text.split()),
        target_source_tokens=100,
        position="distributed",
        seed=9,
    )

    measurements = measure_musique_evaluator_items(
        (packed,),
        pack_budget_tokens=8,
        source_sha256="a" * 64,
        source_revision="1" * 40,
        official_source_sha256=None,
        tokenizer_id="word-counter@test",
    )

    assert measurements.n_items == 1
    assert measurements.pack_binding_rate == 1.0
    assert measurements.answer_in_support_rate == 1.0
    assert measurements.answer_in_nonsupport_rate == 0.0
    assert measurements.intermediate_answers_in_support_rate == 1.0
    assert measurements.intermediate_answers_in_nonsupport_rate == 0.0
    assert not hasattr(measurements, "answers")


def test_measurement_detects_intermediate_answer_leakage() -> None:
    raw = _raw("one", answer_in_decoy=False)
    raw["paragraphs"][2]["paragraph_text"] = (  # type: ignore[index]
        "A decoy repeats one intermediate."
    )
    record = musique_answerable_record(raw)

    measurements = measure_musique_records(
        (record,),
        token_counter=lambda text: len(text.split()),
        pack_budget_tokens=8,
        source_sha256="a" * 64,
        source_revision="1" * 40,
        official_source_sha256=None,
        tokenizer_id="word-counter@test",
    )

    assert measurements.intermediate_answers_in_nonsupport_rate == 1.0


def test_tokenizer_snapshot_verification_binds_exact_files(tmp_path: Path) -> None:
    tokenizer_json = tmp_path / "tokenizer.json"
    tokenizer_config = tmp_path / "tokenizer_config.json"
    tokenizer_json.write_bytes(b"tokenizer")
    tokenizer_config.write_bytes(b"config")
    expected = (
        ("tokenizer.json", hashlib.sha256(b"tokenizer").hexdigest()),
        ("tokenizer_config.json", hashlib.sha256(b"config").hexdigest()),
    )

    identity = verify_tokenizer_snapshot(tmp_path, expected)

    assert len(identity) == 64
    tokenizer_json.write_bytes(b"changed")
    with pytest.raises(ValueError, match="tokenizer snapshot digest mismatch"):
        verify_tokenizer_snapshot(tmp_path, expected)
