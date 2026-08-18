from __future__ import annotations

import json
from pathlib import Path

import pytest

from rsicontext.campaign.hard_baseline_gate import (
    DEFAULT_HARD_PROFILES,
    run_hard_baseline_gate,
    write_hard_baseline_gate,
)
from rsicontext.datasets import HardTaskProfile, generate_hard_long_context_dataset
from rsicontext.eval import ReaderOutput
from rsicontext.experiment import load_api_profiles
from rsicontext.policy import ContextPack

ROOT = Path(__file__).parents[1]


def _word_tokens(text: str) -> int:
    return len(text.split())


class CompleteEvidenceReader:
    def __init__(self, *, seed: str, items_per_profile: int) -> None:
        dataset = generate_hard_long_context_dataset(
            seed=seed,
            items_per_profile=items_per_profile,
            requested_tokens=32_768,
            token_counter=_word_tokens,
            tokenizer_id="test-word-tokenizer-v1",
        )
        self.expected = {
            private_item.evaluation_item.query: (
                private_item.evaluation_item.answer,
                private_item.evaluation_item.gold_chunk_ids,
            )
            for private_item in dataset.visible_items()
        }
        self.calls = 0

    def read(self, query: str, context: ContextPack) -> ReaderOutput:
        self.calls += 1
        answer, gold_ids = self.expected[query]
        selected_ids = {span.chunk_id for span in context.spans}
        prediction = answer if gold_ids <= selected_ids else "incorrect"
        return ReaderOutput(
            prediction,
            input_tokens=context.token_count + 13,
            output_tokens=1,
        )


def test_hard_gate_records_fixed_baselines_and_evaluator_instruments(tmp_path: Path) -> None:
    seed = "disposable-hard-gate"
    items_per_profile = 4
    api_profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    reader = CompleteEvidenceReader(seed=seed, items_per_profile=items_per_profile)
    tick = [0.0]

    def timer() -> float:
        value = tick[0]
        tick[0] += 0.1
        return value

    result = run_hard_baseline_gate(
        api_profile,
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="secret-value",
        reader=reader,
        token_counter=_word_tokens,
        tokenizer_id="test-word-tokenizer-v1",
        dataset_seed=seed,
        items_per_profile=items_per_profile,
        timer=timer,
        started_at="2026-08-14T00:00:00Z",
    )

    assert result.schema_version == 4
    assert result.split == "visible"
    assert result.requested_target_tokens == 32_768
    assert result.source_target_tokens_min == 32_768
    assert result.source_target_tokens_max == 32_768
    assert result.target_token_tolerance == 656
    assert result.semantic_words_min == 32_768
    assert result.semantic_words_max == 32_768
    assert result.policy_budget_target_tokens == 8_192
    assert result.tokenizer_id == "test-word-tokenizer-v1"
    assert result.task_profiles == tuple(profile.value for profile in DEFAULT_HARD_PROFILES)
    assert len(result.dataset_fingerprint) == 64
    assert len(result.dataset_seed_hash) == 64
    assert len(result.qualification_profile_hash) == 64
    assert result.reader_profile_id == api_profile.id
    assert result.reader_profile_hash == api_profile.profile_hash
    assert result.qualification_only is True
    assert result.difficulty_assessment == "not_assessed"

    conditions = {observation.condition_name: observation for observation in result.conditions}
    assert set(conditions) == {
        "head-8k",
        "head-tail-8k",
        "lexical-8k",
        "full-context-unbudgeted-instrument",
        "no-context-instrument",
        "gold-only-instrument",
        "bounded-oracle-8k-instrument",
    }
    assert {condition.condition_role for condition in result.conditions} == {
        "fixed_baseline",
        "evaluator_instrument",
    }
    assert all(
        {profile.task_profile for profile in condition.profiles}
        == {profile.value for profile in DEFAULT_HARD_PROFILES}
        for condition in result.conditions
    )
    assert all(
        len(profile.item_ids)
        == len(profile.predictions)
        == len(profile.item_scores)
        == len(profile.gold_recall)
        == len(profile.context_tokens)
        == items_per_profile
        for condition in result.conditions
        for profile in condition.profiles
    )
    assert all(
        prediction
        in {
            private_item.evaluation_item.answer,
            "incorrect",
        }
        for condition in result.conditions
        for profile in condition.profiles
        for prediction, private_item in zip(
            profile.predictions,
            (
                private_item
                for private_item in generate_hard_long_context_dataset(
                    seed=seed,
                    items_per_profile=items_per_profile,
                    requested_tokens=32_768,
                    token_counter=_word_tokens,
                    tokenizer_id="test-word-tokenizer-v1",
                ).visible_items()
                if private_item.task_profile.value == profile.task_profile
            ),
            strict=True,
        )
    )
    assert conditions["no-context-instrument"].score == 0.0
    assert conditions["no-context-instrument"].mean_gold_recall == 0.0
    assert conditions["gold-only-instrument"].score == 1.0
    assert conditions["gold-only-instrument"].mean_gold_recall == 1.0
    assert conditions["bounded-oracle-8k-instrument"].score == 1.0
    assert conditions["bounded-oracle-8k-instrument"].mean_gold_recall == 1.0
    assert conditions["full-context-unbudgeted-instrument"].score == 1.0
    assert conditions["full-context-unbudgeted-instrument"].mean_gold_recall == 1.0
    assert conditions["full-context-unbudgeted-instrument"].condition_role == (
        "evaluator_instrument"
    )

    expected_calls = 7 * len(DEFAULT_HARD_PROFILES) * items_per_profile
    assert result.reader_calls == expected_calls
    assert reader.calls == expected_calls
    assert result.reader_input_tokens == sum(
        profile.reader_input_tokens
        for condition in result.conditions
        for profile in condition.profiles
    )
    assert result.reader_output_tokens == expected_calls
    assert result.wall_seconds == pytest.approx(7 * len(DEFAULT_HARD_PROFILES) * 0.1)
    assert "secret-value" not in json.dumps(result.to_dict())

    path = tmp_path / "hard-gate.json"
    write_hard_baseline_gate(result, path)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["qualification_only"] is True
    assert stored["difficulty_assessment"] == "not_assessed"
    with pytest.raises(FileExistsError):
        write_hard_baseline_gate(result, path)


@pytest.mark.parametrize("items_per_profile", [0, False])
def test_hard_gate_rejects_invalid_panel_size(items_per_profile: int) -> None:
    api_profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )

    with pytest.raises((TypeError, ValueError)):
        run_hard_baseline_gate(
            api_profile,
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            reader=CompleteEvidenceReader(seed="valid", items_per_profile=1),
            token_counter=_word_tokens,
            tokenizer_id="test-word-tokenizer-v1",
            items_per_profile=items_per_profile,
        )


def test_hard_gate_fails_closed_on_invalid_profile_selection() -> None:
    api_profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    reader = CompleteEvidenceReader(seed="valid", items_per_profile=1)

    with pytest.raises(ValueError, match="non-empty and unique"):
        run_hard_baseline_gate(
            api_profile,
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            reader=reader,
            token_counter=_word_tokens,
            tokenizer_id="test-word-tokenizer-v1",
            task_profiles=(),
        )
    with pytest.raises(ValueError, match="non-empty and unique"):
        run_hard_baseline_gate(
            api_profile,
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            reader=reader,
            token_counter=_word_tokens,
            tokenizer_id="test-word-tokenizer-v1",
            task_profiles=(
                HardTaskProfile.COMPOSITIONAL_MULTI_HOP,
                HardTaskProfile.COMPOSITIONAL_MULTI_HOP,
            ),
        )
    with pytest.raises(ValueError, match="abstention"):
        run_hard_baseline_gate(
            api_profile,
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            reader=reader,
            token_counter=_word_tokens,
            tokenizer_id="test-word-tokenizer-v1",
            task_profiles=(HardTaskProfile.INSUFFICIENT_EVIDENCE,),
        )


def test_hard_gate_rejects_non_reader_output() -> None:
    class InvalidReader:
        def read(self, query: str, context: ContextPack) -> str:
            del query, context
            return "not-reader-output"

    api_profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    with pytest.raises(TypeError, match="ReaderOutput"):
        run_hard_baseline_gate(
            api_profile,
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            reader=InvalidReader(),  # type: ignore[arg-type]
            token_counter=_word_tokens,
            tokenizer_id="test-word-tokenizer-v1",
            items_per_profile=1,
        )


def test_hard_gate_requires_evaluator_owned_target_tokenizer() -> None:
    api_profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    with pytest.raises(TypeError, match="token_counter"):
        run_hard_baseline_gate(
            api_profile,
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            reader=CompleteEvidenceReader(seed="valid", items_per_profile=1),
            token_counter=None,  # type: ignore[arg-type]
            tokenizer_id="test",
            items_per_profile=1,
        )
