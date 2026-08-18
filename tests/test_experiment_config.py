from __future__ import annotations

import pytest

from rsicontext.experiment.config import BudgetSpec, ModelSpec, RunSpec, Split, Track
from rsicontext.policy import Budget


def _run_dict() -> dict[str, object]:
    return RunSpec(
        experiment="toy",
        dataset_revision="data-sha",
        evaluator_revision="eval-sha",
        policy_hash="policy-sha",
        serving_profile_hash="serving-sha",
        reader_profile_hash="reader-sha",
        chat_template_enable_thinking=None,
        model=ModelSpec("model", "revision", "tokenizer-revision", 8_192),
        budget=BudgetSpec(4_096, 64, target_calls=1),
        split=Split.VISIBLE,
        track=Track.SINGLE_READER,
        seed=42,
    ).to_dict()


def test_run_id_is_stable_and_changes_with_frozen_input() -> None:
    model = ModelSpec(
        model_id="Qwen/Qwen3.6-27B",
        revision="abc123",
        tokenizer_revision="abc123",
        max_model_len=131_072,
    )
    budget = BudgetSpec(context_tokens=32_000, output_tokens=128, target_calls=1)
    first = RunSpec(
        experiment="toy",
        dataset_revision="data-sha",
        evaluator_revision="eval-sha",
        policy_hash="policy-sha",
        serving_profile_hash="serving-sha",
        reader_profile_hash="reader-sha",
        chat_template_enable_thinking=False,
        model=model,
        budget=budget,
        split=Split.VISIBLE,
        track=Track.SINGLE_READER,
        seed=42,
    )
    same = RunSpec.from_dict(first.to_dict())
    changed = RunSpec.from_dict({**first.to_dict(), "seed": 43})
    changed_thinking = RunSpec.from_dict({**first.to_dict(), "chat_template_enable_thinking": True})

    assert first.run_id == same.run_id
    assert first.run_id != changed.run_id
    assert first.run_id != changed_thinking.run_id
    assert first.policy_budget == Budget(max_tokens=32_000)


def test_single_reader_rejects_multiple_target_calls() -> None:
    with pytest.raises(ValueError, match="exactly one target call"):
        RunSpec(
            experiment="bad",
            dataset_revision="data",
            evaluator_revision="eval",
            policy_hash="policy",
            serving_profile_hash="serving",
            reader_profile_hash="reader",
            chat_template_enable_thinking=None,
            model=ModelSpec("m", "r", "r", 8_192),
            budget=BudgetSpec(4_096, 64, target_calls=2),
            split=Split.VISIBLE,
            track=Track.SINGLE_READER,
            seed=0,
        )


def test_budget_reserves_output_tokens() -> None:
    with pytest.raises(ValueError, match="model length"):
        RunSpec(
            experiment="bad",
            dataset_revision="data",
            evaluator_revision="eval",
            policy_hash="policy",
            serving_profile_hash="serving",
            reader_profile_hash="reader",
            chat_template_enable_thinking=None,
            model=ModelSpec("m", "r", "r", 4_096),
            budget=BudgetSpec(4_096, 1, target_calls=1),
            split=Split.VISIBLE,
            track=Track.SINGLE_READER,
            seed=0,
        )


@pytest.mark.parametrize("seed", [True, 1.9, "42", None])
def test_run_spec_rejects_coerced_seed_values(seed: object) -> None:
    with pytest.raises(TypeError, match="seed"):
        RunSpec.from_dict({**_run_dict(), "seed": seed})


def test_run_spec_rejects_unknown_or_malformed_fields() -> None:
    with pytest.raises(ValueError, match="unexpected"):
        RunSpec.from_dict({**_run_dict(), "temperature": 0.0})
    run_dict = _run_dict()
    model = run_dict["model"]
    assert isinstance(model, dict)
    with pytest.raises(ValueError, match="unexpected"):
        RunSpec.from_dict(
            {
                **run_dict,
                "model": {**model, "chat_template": "changed"},
            }
        )
    with pytest.raises(TypeError, match="policy_hash"):
        RunSpec.from_dict({**_run_dict(), "policy_hash": None})


def test_numeric_specs_reject_booleans_and_non_finite_values() -> None:
    with pytest.raises(TypeError, match="context_tokens"):
        BudgetSpec(context_tokens=True, output_tokens=1, target_calls=1)
    with pytest.raises(ValueError, match="finite"):
        BudgetSpec(
            context_tokens=1, output_tokens=1, target_calls=1, wall_time_seconds=float("inf")
        )
    with pytest.raises(TypeError, match="max_model_len"):
        ModelSpec("model", "revision", "tokenizer", True)
    with pytest.raises(ValueError, match="mutable"):
        ModelSpec("model", "main", "tokenizer", 8_192)


@pytest.mark.parametrize("track", [Track.ADAPTIVE, Track.KV])
def test_run_spec_rejects_unimplemented_tracks(track: Track) -> None:
    raw = _run_dict()
    raw["track"] = track.value

    with pytest.raises(ValueError, match="not implemented"):
        RunSpec.from_dict(raw)
