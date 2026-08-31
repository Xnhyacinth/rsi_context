from __future__ import annotations

import hashlib
import json
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from rsicontext.analysis.longmemeval_qualification import measure_longmemeval_dataset
from rsicontext.datasets.longmemeval_v2 import LongMemEvalDataError, load_longmemeval_v2

_REVISION = "f152293e235517d504809563c833d7190b8c713b"
_TOKENIZER_ID = "unit-word-tokenizer@sha256:test"


def _token_count(text: str) -> int:
    return len(text.split())


def _question(question_id: str, *, image: str | None = None) -> dict[str, object]:
    return {
        "id": question_id,
        "domain": "web",
        "environment": "shopping",
        "question_type": "static-state",
        "question": f"What happened in {question_id}?",
        "image": image,
        "answer": f"EVALUATOR-SECRET-{question_id}",
        "eval_function": "norm_phrase_set_match|require_non_empty=true",
    }


def _state(index: int) -> dict[str, object]:
    return {
        "state_index": index,
        "step": index + 10,
        "url": f"https://example.test/{index}",
        "action": None if index == 0 else f"click('{index}')",
        "thought": None if index == 0 else f"thought-{index}",
        "accessibility_tree": f"tree-{index}",
        "screenshot": f"screenshots/t1/{index}.png",
    }


def _trajectory(trajectory_id: str, *, states: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": trajectory_id,
        "domain": "web",
        "environment": "shopping",
        "goal": f"goal-{trajectory_id}",
        "outcome": "success",
        "start_url": "https://example.test/start",
        "states": states,
    }


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _fixture(
    tmp_path: Path,
) -> tuple[Path, list[dict[str, object]], list[dict[str, object]], dict[str, list[str]]]:
    root = tmp_path / "longmemeval-v2"
    (root / "haystacks").mkdir(parents=True)
    questions = [
        _question("q-text"),
        _question("q-image", image="question_screenshots/q-image.png"),
    ]
    trajectories = [
        _trajectory("t1", states=[_state(0), _state(1)]),
        _trajectory("t2", states=[_state(0)]),
        _trajectory("t3", states=[_state(0)]),
    ]
    haystack = {"q-text": ["t2", "t1"], "q-image": ["t3"]}
    _write_jsonl(root / "questions.jsonl", questions)
    _write_jsonl(root / "trajectories.jsonl", trajectories)
    (root / "haystacks" / "lme_v2_small.json").write_text(
        json.dumps(haystack, sort_keys=True), encoding="utf-8"
    )
    return root, questions, trajectories, haystack


def _rewrite_fixture(
    root: Path,
    questions: list[dict[str, object]],
    trajectories: list[dict[str, object]],
    haystack: dict[str, list[str]],
) -> None:
    _write_jsonl(root / "questions.jsonl", questions)
    _write_jsonl(root / "trajectories.jsonl", trajectories)
    (root / "haystacks" / "lme_v2_small.json").write_text(
        json.dumps(haystack, sort_keys=True), encoding="utf-8"
    )


def test_loads_text_only_trajectory_states_in_haystack_and_state_order(tmp_path: Path) -> None:
    root, _, _, _ = _fixture(tmp_path)

    dataset = load_longmemeval_v2(
        root,
        source_revision=_REVISION,
        token_counter=_token_count,
        tokenizer_id=_TOKENIZER_ID,
        tier="small",
    )

    assert dataset.excluded_image_question_count == 1
    assert len(dataset.policy_items()) == len(dataset.evaluator_items()) == 1
    policy_item = dataset.policy_items()[0]
    evaluator_item = dataset.evaluator_items()[0]
    assert policy_item.question_id == "q-text"
    assert policy_item.trajectory_ids == ("t2", "t1")
    assert policy_item.full_haystack_size == 2
    assert evaluator_item.policy_item == policy_item
    assert evaluator_item.answer == "EVALUATOR-SECRET-q-text"
    assert evaluator_item.eval_function == "norm_phrase_set_match|require_non_empty=true"

    chunks = policy_item.artifact.chunks
    assert [chunk.chunk_id for chunk in chunks] == [
        "lmev2:t2:metadata",
        "lmev2:t2:state:0",
        "lmev2:t1:metadata",
        "lmev2:t1:state:0",
        "lmev2:t1:state:1",
    ]
    assert [chunk.role for chunk in chunks] == [
        "trajectory_metadata",
        "trajectory_state",
        "trajectory_metadata",
        "trajectory_state",
        "trajectory_state",
    ]
    assert all(chunk.document_id == policy_item.artifact.document_id for chunk in chunks)
    assert chunks[0].start == 0
    assert all(left.end < right.start for left, right in pairwise(chunks))
    assert "domain: web" in chunks[0].text
    assert "environment: shopping" in chunks[0].text
    assert "goal: goal-t2" in chunks[0].text
    assert "outcome: success" in chunks[0].text
    assert "start_url: https://example.test/start" in chunks[0].text
    assert "step: 10" in chunks[1].text
    assert "url: https://example.test/0" in chunks[1].text
    assert "action: <none>" in chunks[1].text
    assert "thought: <none>" in chunks[1].text
    assert "action: click('1')" in chunks[-1].text
    assert "thought: thought-1" in chunks[-1].text
    assert "accessibility_tree:\ntree-1" in chunks[-1].text


def test_uses_the_frozen_target_tokenizer_and_binds_its_identity(tmp_path: Path) -> None:
    root, _, _, _ = _fixture(tmp_path)

    dataset = load_longmemeval_v2(
        root,
        source_revision=_REVISION,
        tier="small",
        token_counter=lambda text: len(text.split()) + text.count("\n"),
        tokenizer_id="frozen-tokenizer@revision#sha256:test",
    )

    chunk = dataset.policy_items()[0].artifact.chunks[0]
    assert chunk.token_count == len(chunk.text.split()) + chunk.text.count("\n")
    assert dataset.tokenizer_id == "frozen-tokenizer@revision#sha256:test"


def test_shared_trajectories_are_tokenized_once_across_distinct_haystacks(
    tmp_path: Path,
) -> None:
    root, questions, trajectories, haystack = _fixture(tmp_path)
    questions[1] = _question("q-second")
    haystack = {"q-text": ["t1", "t2"], "q-second": ["t2", "t1"]}
    _rewrite_fixture(root, questions, trajectories, haystack)
    counted_texts: list[str] = []

    def count_once(text: str) -> int:
        counted_texts.append(text)
        return _token_count(text)

    dataset = load_longmemeval_v2(
        root,
        source_revision=_REVISION,
        token_counter=count_once,
        tokenizer_id=_TOKENIZER_ID,
        tier="small",
    )

    assert len(dataset.policy_items()) == 2
    assert len({item.artifact.document_id for item in dataset.policy_items()}) == 2
    assert len(counted_texts) == 5
    assert len(counted_texts) == len(set(counted_texts))
    first_chunks, second_chunks = (item.artifact.chunks for item in dataset.policy_items())
    assert [chunk.chunk_id for chunk in first_chunks] == [
        "lmev2:t1:metadata",
        "lmev2:t1:state:0",
        "lmev2:t1:state:1",
        "lmev2:t2:metadata",
        "lmev2:t2:state:0",
    ]
    assert [chunk.chunk_id for chunk in second_chunks] == [
        "lmev2:t2:metadata",
        "lmev2:t2:state:0",
        "lmev2:t1:metadata",
        "lmev2:t1:state:0",
        "lmev2:t1:state:1",
    ]
    for item in dataset.policy_items():
        assert all(chunk.document_id == item.artifact.document_id for chunk in item.artifact.chunks)
        assert all(left.end < right.start for left, right in pairwise(item.artifact.chunks))
        assert all(chunk.token_count == _token_count(chunk.text) for chunk in item.artifact.chunks)


def test_policy_view_never_embeds_evaluator_fields_or_screenshot_content(tmp_path: Path) -> None:
    root, _, _, _ = _fixture(tmp_path)

    dataset = load_longmemeval_v2(
        root,
        source_revision=_REVISION,
        token_counter=_token_count,
        tokenizer_id=_TOKENIZER_ID,
        tier="small",
    )

    policy_item = dataset.policy_items()[0]
    policy_text = "\n".join(
        (policy_item.query, *(chunk.text for chunk in policy_item.artifact.chunks))
    )
    assert "EVALUATOR-SECRET" not in policy_text
    assert "exact_match" not in policy_text
    assert "screenshot" not in policy_text
    assert not hasattr(policy_item, "answer")
    assert not hasattr(policy_item, "eval_function")


def test_limits_are_deterministic_and_report_full_haystack_coverage(tmp_path: Path) -> None:
    root, _, _, _ = _fixture(tmp_path)

    first = load_longmemeval_v2(
        root,
        source_revision=_REVISION,
        token_counter=_token_count,
        tokenizer_id=_TOKENIZER_ID,
        tier="small",
        question_limit=1,
        trajectories_per_question=1,
    )
    second = load_longmemeval_v2(
        root,
        source_revision=_REVISION,
        token_counter=_token_count,
        tokenizer_id=_TOKENIZER_ID,
        tier="small",
        question_limit=1,
        trajectories_per_question=1,
    )

    item = first.policy_items()[0]
    assert item.trajectory_ids == ("t2",)
    assert item.full_haystack_size == 2
    assert first.loaded_trajectory_ids == frozenset({"t2"})
    assert first.fingerprint == second.fingerprint


def test_records_portable_source_file_and_revision_fingerprints(tmp_path: Path) -> None:
    root, _, _, _ = _fixture(tmp_path)

    dataset = load_longmemeval_v2(
        root,
        source_revision=_REVISION,
        token_counter=_token_count,
        tokenizer_id=_TOKENIZER_ID,
        tier="small",
    )

    assert dataset.source.revision == _REVISION
    assert len(dataset.source.fingerprint) == 64
    assert len(dataset.fingerprint) == 64
    by_name = {record.relative_path: record.sha256 for record in dataset.source.files}
    assert set(by_name) == {
        "haystacks/lme_v2_small.json",
        "questions.jsonl",
        "trajectories.jsonl",
    }
    for relative_path, digest in by_name.items():
        assert digest == hashlib.sha256((root / relative_path).read_bytes()).hexdigest()


def test_aggregate_measurement_counts_states_without_metadata_chunks(tmp_path: Path) -> None:
    root, _, _, _ = _fixture(tmp_path)
    dataset = load_longmemeval_v2(
        root,
        source_revision=_REVISION,
        token_counter=_token_count,
        tokenizer_id=_TOKENIZER_ID,
        tier="small",
    )
    source_files = tuple(
        sorted((record.relative_path, record.sha256) for record in dataset.source.files)
    )

    measurements = measure_longmemeval_dataset(
        dataset,
        released_file_sha256=source_files,
    )

    chunks = dataset.policy_items()[0].artifact.chunks
    assert measurements.deterministic_item_count == 1
    assert measurements.weak_judge_item_count == 0
    assert measurements.state_count_min == measurements.state_count_max == 3
    assert measurements.single_chunk_token_max == max(chunk.token_count for chunk in chunks)


@pytest.mark.parametrize(
    "corrupt",
    [
        "missing-trajectory",
        "duplicate-haystack-id",
        "duplicate-trajectory-record",
        "missing-haystack-question",
        "duplicate-question-record",
        "out-of-order-state",
        "duplicate-state-index",
        "bad-state-type",
        "bad-question-type",
        "bad-trajectory-type",
    ],
)
def test_malformed_sources_fail_closed(tmp_path: Path, corrupt: str) -> None:
    root, questions, trajectories, haystack = _fixture(tmp_path)
    if corrupt == "missing-trajectory":
        trajectories = trajectories[:1] + trajectories[2:]
    elif corrupt == "duplicate-haystack-id":
        haystack["q-text"] = ["t1", "t1"]
    elif corrupt == "duplicate-trajectory-record":
        trajectories.append(trajectories[0])
    elif corrupt == "missing-haystack-question":
        del haystack["q-image"]
    elif corrupt == "duplicate-question-record":
        questions.append(questions[0])
    elif corrupt == "out-of-order-state":
        states = trajectories[0]["states"]
        assert isinstance(states, list)
        states.reverse()
    elif corrupt == "duplicate-state-index":
        states = trajectories[0]["states"]
        assert isinstance(states, list)
        state = states[1]
        assert isinstance(state, dict)
        state["state_index"] = 0
    elif corrupt == "bad-state-type":
        states = trajectories[0]["states"]
        assert isinstance(states, list)
        state = states[0]
        assert isinstance(state, dict)
        state["accessibility_tree"] = 17
    elif corrupt == "bad-question-type":
        questions[0]["question"] = ["not", "text"]
    elif corrupt == "bad-trajectory-type":
        trajectories[0]["states"] = "not-a-list"
    else:  # pragma: no cover - parametrization is exhaustive
        raise AssertionError(corrupt)
    _rewrite_fixture(root, questions, trajectories, haystack)

    with pytest.raises(LongMemEvalDataError):
        load_longmemeval_v2(
            root,
            source_revision=_REVISION,
            token_counter=_token_count,
            tokenizer_id=_TOKENIZER_ID,
            tier="small",
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"source_revision": "main"}, "immutable"),
        ({"source_revision": "release-v2"}, "immutable"),
        ({"source_revision": _REVISION, "tier": "large"}, "tier"),
        ({"source_revision": _REVISION, "question_limit": 0}, "question_limit"),
        (
            {"source_revision": _REVISION, "trajectories_per_question": True},
            "trajectories_per_question",
        ),
    ],
)
def test_loader_configuration_fails_closed(
    tmp_path: Path, kwargs: dict[str, Any], message: str
) -> None:
    root, _, _, _ = _fixture(tmp_path)

    with pytest.raises((LongMemEvalDataError, TypeError), match=message):
        load_longmemeval_v2(
            root,
            token_counter=_token_count,
            tokenizer_id=_TOKENIZER_ID,
            **kwargs,
        )
