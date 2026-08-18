from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from rsicontext.campaign.hard_causal_gate import (
    DEFAULT_CAUSAL_DATASET_SEED,
    counterfactual_evaluation_item,
    run_hard_causal_gate,
    write_hard_causal_gate,
)
from rsicontext.datasets import HardTaskProfile, generate_hard_long_context_dataset
from rsicontext.eval import ReaderOutput
from rsicontext.experiment import load_api_profiles
from rsicontext.policy import CANONICAL_POLICY_SPECS_V1, ContextPack

ROOT = Path(__file__).parents[1]
_IDENTIFIER = re.compile(r"(?:nd|vl)-[0-9a-f]{12}")


def _word_tokens(text: str) -> int:
    return len(text.split())


class InterventionAwareReader:
    def __init__(self, *, seed: str, items_per_profile: int) -> None:
        dataset = generate_hard_long_context_dataset(
            seed=seed,
            items_per_profile=items_per_profile,
            requested_tokens=32_768,
            token_counter=_word_tokens,
            tokenizer_id="test-word-tokenizer-v1",
        )
        self.items = tuple(dataset.visible_items())
        self.chunk_owner = {
            chunk.chunk_id: private_item
            for private_item in self.items
            for chunk in private_item.evaluation_item.artifact.chunks
        }
        self.calls = 0

    def read(self, query: str, context: ContextPack) -> ReaderOutput:
        self.calls += 1
        owners = {
            self.chunk_owner[span.chunk_id]
            for span in context.spans
            if span.chunk_id in self.chunk_owner
        }
        if len(owners) != 1:
            prediction = "incorrect"
        else:
            private_item = owners.pop()
            item = private_item.evaluation_item
            selected = {span.chunk_id for span in context.spans}
            if not item.gold_chunk_ids <= selected:
                prediction = "incorrect"
            else:
                original = {chunk.chunk_id: chunk.text for chunk in item.artifact.chunks}
                replacement: str | None = None
                for span in context.spans:
                    if span.chunk_id not in item.gold_chunk_ids:
                        continue
                    before = set(_IDENTIFIER.findall(original[span.chunk_id]))
                    after = set(_IDENTIFIER.findall(span.text))
                    candidates = after - before
                    if candidates:
                        replacement = sorted(candidates)[0]
                        break
                prediction = replacement or item.answer
        return ReaderOutput(
            prediction,
            input_tokens=context.token_count + len(query.split()) + 7,
            output_tokens=1,
            response_id=f"response-{self.calls}",
            response_model="reader-model-v1",
        )


def test_hard_causal_gate_records_causal_replay_and_strata(tmp_path: Path) -> None:
    seed = "disposable-causal-gate"
    items_per_profile = 4
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    reader = InterventionAwareReader(seed=seed, items_per_profile=items_per_profile)
    tick = [0.0]

    def timer() -> float:
        value = tick[0]
        tick[0] += 0.1
        return value

    result = run_hard_causal_gate(
        profile,
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="secret-value",
        reader=reader,
        token_counter=_word_tokens,
        tokenizer_id="test-word-tokenizer-v1",
        dataset_seed=seed,
        items_per_profile=items_per_profile,
        replay_repeats=3,
        timer=timer,
        started_at="2026-08-14T00:00:00Z",
    )

    item_count = items_per_profile * len(result.task_profiles)
    assert result.schema_version == 2
    assert result.split == "visible"
    assert result.qualification_only is True
    assert result.difficulty_assessment == "failed"
    assert result.difficulty_results
    assert all(not passed for _, passed, _ in result.difficulty_results)
    assert result.no_context.score == 0.0
    assert result.gold_only.score == 1.0
    assert result.bounded_oracle.score == 1.0
    assert result.dataset_seed_hash != seed
    assert len(result.dataset_fingerprint) == 64
    assert result.tokenizer_id == "test-word-tokenizer-v1"
    assert result.reader_profile_id == profile.id
    assert result.reader_profile_hash == profile.profile_hash
    assert result.requested_model == profile.model
    assert result.reader_implementation.endswith("InterventionAwareReader")
    assert result.observed_response_models == ("reader-model-v1",)
    assert result.gold_drop.score == 0.0
    assert result.gold_drop_decrease == 1.0
    assert result.counterfactual.score == 1.0
    assert len(result.counterfactual_fingerprint) == 64
    assert result.counterfactual_following == 1.0
    assert result.counterfactual.transformation_failures == ()
    assert len(result.counterfactual_rewrite_audits) == item_count
    assert all(
        audit.original_gold_occurrences >= 1
        and audit.transformed_query_original_occurrences == 0
        and audit.transformed_gold_original_occurrences == 0
        and audit.transformed_query_new_occurrences + audit.transformed_gold_new_occurrences
        == audit.original_query_occurrences + audit.original_gold_occurrences
        and audit.transformed_nongold_original_occurrences == audit.original_nongold_occurrences
        and audit.nongold_unchanged
        for audit in result.counterfactual_rewrite_audits
    )
    assert result.replay.policy_name == result.strongest_non_oracle_policies[0]
    assert len(result.replay.repeats) == 3
    assert result.replay.standard_deviation == 0.0
    assert all(len(repeat.items) == item_count for repeat in result.replay.repeats)
    assert all(
        len(item.prediction) > 0
        and item.reader_input_tokens > 0
        and item.reader_output_tokens == 1
        and item.reader_calls == 1
        and item.wall_seconds == pytest.approx(0.1)
        for repeat in result.replay.repeats
        for item in repeat.items
    )
    assert len(result.fixed_policies) == 3
    assert len(result.policy_search_space) == len(CANONICAL_POLICY_SPECS_V1)
    assert len(result.policy_spec_v1_hashes) == 4
    assert all(
        len(condition.profiles) == len(result.task_profiles)
        and all(
            len(profile_observation.items) == items_per_profile
            and profile_observation.reader_calls == items_per_profile
            and 0.0 <= profile_observation.mean_gold_recall <= 1.0
            for profile_observation in condition.profiles
        )
        for condition in result.policy_search_space
    )
    assert len(result.strongest_non_oracle_policies) == 2
    assert 0.0 <= result.strongest_policy_item_disagreement <= 1.0
    assert len(result.strata) == len(result.task_profiles) * 4
    assert {stratum.policy_name for stratum in result.strata} == {
        result.strongest_non_oracle_policies[0]
    }
    assert {stratum.evidence_position for stratum in result.strata} == {
        "head",
        "middle",
        "tail",
        "distributed",
    }
    assert all(stratum.item_count == 1 for stratum in result.strata)
    assert (
        result.reader_calls
        == (len(result.fixed_policies) + len(CANONICAL_POLICY_SPECS_V1) + 6 + result.replay_repeats)
        * item_count
    )
    assert reader.calls == result.reader_calls
    assert result.reader_calls == sum(
        item.reader_calls
        for condition in (
            *result.fixed_policies,
            *result.policy_search_space,
            result.full_context,
            result.no_context,
            result.gold_only,
            result.bounded_oracle,
            result.gold_drop,
            result.counterfactual,
        )
        for item in condition.items
    ) + sum(item.reader_calls for repeat in result.replay.repeats for item in repeat.items)
    assert result.reader_input_tokens > 0
    assert result.reader_output_tokens == result.reader_calls
    assert result.wall_seconds == pytest.approx(result.reader_calls * 0.1)
    assert "secret-value" not in json.dumps(result.to_dict())

    output = tmp_path / "causal-gate.json"
    write_hard_causal_gate(result, output)
    stored = json.loads(output.read_text(encoding="utf-8"))
    assert stored["qualification_only"] is True
    assert stored["difficulty_assessment"] == "failed"
    with pytest.raises(FileExistsError):
        write_hard_causal_gate(result, output)


def test_counterfactual_rewrites_query_and_every_answer_bearing_gold_chunk() -> None:
    dataset = generate_hard_long_context_dataset(
        seed=DEFAULT_CAUSAL_DATASET_SEED,
        items_per_profile=4,
        requested_tokens=32_768,
        token_counter=_word_tokens,
        tokenizer_id="test-word-tokenizer-v1",
    )

    transformed_profiles: set[HardTaskProfile] = set()
    for private_item in dataset.visible_items():
        if private_item.task_profile not in {
            HardTaskProfile.COMPOSITIONAL_MULTI_HOP,
            HardTaskProfile.DENSE_GLOBAL_COMPARISON,
            HardTaskProfile.TEMPORAL_STATE_RESOLUTION,
        }:
            continue
        transformed_profiles.add(private_item.task_profile)
        original = private_item.evaluation_item
        transformed = counterfactual_evaluation_item(private_item, _word_tokens)
        assert transformed.answer != original.answer
        assert len(transformed.answer) == len(original.answer)
        assert transformed.gold_chunk_ids == original.gold_chunk_ids
        assert transformed.artifact.chunk_ids == original.artifact.chunk_ids
        for original_chunk, transformed_chunk in zip(
            original.artifact.chunks, transformed.artifact.chunks, strict=True
        ):
            if original_chunk.chunk_id in original.gold_chunk_ids:
                assert transformed_chunk.text == original_chunk.text.replace(
                    original.answer, transformed.answer
                )
            else:
                assert transformed_chunk == original_chunk
        assert transformed.query == original.query.replace(original.answer, transformed.answer)
        original_union = (
            original.query
            + "\n"
            + "\n".join(
                chunk.text
                for chunk in original.artifact.chunks
                if chunk.chunk_id in original.gold_chunk_ids
            )
        )
        transformed_union = (
            transformed.query
            + "\n"
            + "\n".join(
                chunk.text
                for chunk in transformed.artifact.chunks
                if chunk.chunk_id in transformed.gold_chunk_ids
            )
        )
        assert transformed_union.count(original.answer) == 0
        assert transformed_union.count(transformed.answer) == original_union.count(original.answer)
        if private_item.task_profile is HardTaskProfile.DENSE_GLOBAL_COMPARISON:
            assert private_item.minimum_evidence_chunks == 13

    assert transformed_profiles == {
        HardTaskProfile.COMPOSITIONAL_MULTI_HOP,
        HardTaskProfile.DENSE_GLOBAL_COMPARISON,
        HardTaskProfile.TEMPORAL_STATE_RESOLUTION,
    }


def test_counterfactual_fails_closed_when_gold_does_not_contain_answer() -> None:
    private_item = generate_hard_long_context_dataset(
        seed="counterfactual-failure",
        items_per_profile=1,
        requested_tokens=32_768,
        token_counter=_word_tokens,
        tokenizer_id="test-word-tokenizer-v1",
    ).visible_items()[0]
    item = private_item.evaluation_item
    for gold_chunk in (
        chunk for chunk in item.artifact.chunks if chunk.chunk_id in item.gold_chunk_ids
    ):
        object.__setattr__(gold_chunk, "text", gold_chunk.text.replace(item.answer, "missing"))

    with pytest.raises(ValueError, match="answer-bearing gold evidence"):
        counterfactual_evaluation_item(private_item, _word_tokens)


@pytest.mark.parametrize("repeats", [0, 1, 2, False])
def test_hard_causal_gate_requires_at_least_three_replays(repeats: int) -> None:
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )
    with pytest.raises((TypeError, ValueError), match="replay_repeats"):
        run_hard_causal_gate(
            profile,
            endpoint="https://copilot.tencent.com/v2/chat/completions",
            api_key="key",
            reader=InterventionAwareReader(seed=DEFAULT_CAUSAL_DATASET_SEED, items_per_profile=1),
            token_counter=_word_tokens,
            tokenizer_id="test-word-tokenizer-v1",
            items_per_profile=1,
            replay_repeats=repeats,
        )
