from __future__ import annotations

import json
from pathlib import Path

import pytest

from rsicontext.campaign.api_dynamic_gate import (
    build_local_vllm_profile,
    dynamic_reader_output_limit,
    run_api_dynamic_gate,
    write_api_dynamic_gate,
)
from rsicontext.datasets import DynamicTaskProfile, generate_dynamic_long_context_dataset
from rsicontext.eval import ReaderOutput
from rsicontext.experiment import load_api_profiles
from rsicontext.policy import ContextPack
from rsicontext.registry import load_registry, load_serving_profiles

ROOT = Path(__file__).parents[1]


def test_local_vllm_profile_binds_registered_model_and_serving_stack() -> None:
    registry = load_registry(ROOT / "configs" / "registry.json")
    serving = load_serving_profiles(ROOT / "configs" / "serving_profiles.json", registry).get(
        "qwen3.6-27b-128k-bf16-h200x8"
    )
    model = next(entry for entry in registry.entries if entry.id == serving.model_id)

    profile = build_local_vllm_profile(serving, model, vllm_version="0.25.1")

    assert profile.model == "Qwen/Qwen3.6-27B"
    assert profile.provider == "vllm-0.25.1"
    assert profile.provider_revision == model.revision
    assert profile.evaluation_max_model_len == serving.max_model_len
    assert profile.max_output_tokens == 512
    assert profile.seed == serving.seed
    assert profile.chat_template_enable_thinking is False


def test_dynamic_tasks_reserve_output_budget_for_reasoning() -> None:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )

    assert dynamic_reader_output_limit(profile) == 512


class GoldEvidenceReader:
    def __init__(self, *, seed: str, items_per_profile: int) -> None:
        dataset = generate_dynamic_long_context_dataset(
            seed=seed,
            items_per_profile=items_per_profile,
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
        prediction = answer if gold_ids <= selected_ids else ""
        return ReaderOutput(
            prediction,
            input_tokens=context.token_count + 11,
            output_tokens=1 if prediction else 0,
        )


def test_dynamic_gate_reports_fixed_policies_by_visible_profile(tmp_path: Path) -> None:
    seed = "controlled-dynamic-gate"
    items_per_profile = 3
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    reader = GoldEvidenceReader(seed=seed, items_per_profile=items_per_profile)
    tick = [0.0]

    def timer() -> float:
        value = tick[0]
        tick[0] += 0.1
        return value

    result = run_api_dynamic_gate(
        profile,
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="secret-value",
        reader=reader,
        dataset_seed=seed,
        items_per_profile=items_per_profile,
        timer=timer,
        started_at="2026-08-14T00:00:00Z",
        serving_profile_id="qwen-test-profile",
        serving_profile_hash="a" * 64,
    )

    assert result.schema_version == 2
    assert result.max_output_tokens == 512
    assert result.serving_profile_id == "qwen-test-profile"
    assert result.serving_profile_hash == "a" * 64
    assert result.split == "visible"
    assert result.items_per_profile == 3
    assert (
        result.dataset_fingerprint
        == generate_dynamic_long_context_dataset(
            seed=seed,
            items_per_profile=items_per_profile,
        ).fingerprint
    )
    assert result.reader_calls == 24
    assert reader.calls == 24
    assert result.qualification_only is True
    assert {observation.policy_name for observation in result.policies} == {
        "head-8k",
        "head-tail-8k",
        "lexical-8k",
        "full-32k",
    }
    assert all(
        {profile_result.task_profile for profile_result in observation.profiles}
        == {profile.value for profile in DynamicTaskProfile}
        for observation in result.policies
    )
    assert all(
        len(profile_result.item_scores) == items_per_profile
        and len(profile_result.gold_recall) == items_per_profile
        and profile_result.wall_seconds == pytest.approx(0.1)
        for observation in result.policies
        for profile_result in observation.profiles
    )

    observations = {
        (observation.policy_name, profile_result.task_profile): profile_result
        for observation in result.policies
        for profile_result in observation.profiles
    }
    sparse = DynamicTaskProfile.SPARSE_MULTI_HOP.value
    dense = DynamicTaskProfile.DENSE_COMPETING_VALUES.value
    assert observations[("head-8k", sparse)].item_scores == (1.0, 0.0, 0.0)
    assert observations[("head-8k", sparse)].gold_recall == (1.0, 0.0, 0.0)
    assert observations[("head-8k", dense)].gold_recall == (1.0, 0.25, 0.0)
    assert observations[("head-tail-8k", sparse)].item_scores == (1.0, 0.0, 1.0)
    assert observations[("head-tail-8k", dense)].gold_recall == (1.0, 0.25, 1.0)
    assert all(
        profile_result.score == 1.0 and profile_result.mean_gold_recall == 1.0
        for profile_result in next(
            observation for observation in result.policies if observation.policy_name == "full-32k"
        ).profiles
    )
    assert result.reader_input_tokens == sum(
        profile_result.reader_input_tokens
        for observation in result.policies
        for profile_result in observation.profiles
    )
    assert "secret-value" not in json.dumps(result.to_dict())

    path = tmp_path / "dynamic-gate.json"
    write_api_dynamic_gate(result, path)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["dataset_fingerprint"] == result.dataset_fingerprint
    assert stored["qualification_only"] is True
    with pytest.raises(FileExistsError):
        write_api_dynamic_gate(result, path)


@pytest.mark.parametrize("items_per_profile", [0, False])
def test_dynamic_gate_rejects_invalid_panel_size(items_per_profile: int) -> None:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )

    with pytest.raises((TypeError, ValueError)):
        run_api_dynamic_gate(
            profile,
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            reader=GoldEvidenceReader(seed="valid", items_per_profile=1),
            items_per_profile=items_per_profile,
        )
