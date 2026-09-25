"""R3 worker request capture and local token-position regression tests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import pytest

from rsicontext.analysis.chat_geometry import measure_chat_geometry

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from r10_chat_geometry import _capture_legacy_payload, _offline_requests, _span_anchor


class _CharacterTokenizer:
    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
        **kwargs: Any,
    ) -> str | list[int]:
        assert add_generation_prompt
        suffix = "<assistant-think>" if kwargs.get("enable_thinking") is False else "<assistant>"
        rendered = "".join(f"<{item['role']}>{item['content']}" for item in messages) + suffix
        return [ord(character) for character in rendered] if tokenize else rendered

    def __call__(
        self,
        text: str,
        *,
        add_special_tokens: bool,
        return_offsets_mapping: bool,
    ) -> dict[str, list[Any]]:
        assert not add_special_tokens and return_offsets_mapping
        return {
            "input_ids": [ord(character) for character in text],
            "offset_mapping": [(index, index + 1) for index in range(len(text))],
        }


def test_local_geometry_counts_wrapper_and_later_query_distance() -> None:
    messages = [
        {"role": "system", "content": "frozen"},
        {"role": "user", "content": "Read EVIDENCE and then answer QUERY"},
    ]
    geometry = measure_chat_geometry(
        _CharacterTokenizer(),
        messages,
        enable_thinking=False,
        evidence="EVIDENCE",
        query="QUERY",
    )
    assert geometry["rendered_input_tokens"] == len(
        "<system>frozen<user>Read EVIDENCE and then answer QUERY<assistant-think>"
    )
    assert geometry["span_status"] == "unique_later_query"
    assert geometry["evidence_to_query_tokens"] == len(" and then answer ")


def test_repeated_or_reverse_spans_are_unavailable() -> None:
    messages = [
        {"role": "system", "content": "frozen"},
        {"role": "user", "content": "QUERY EVIDENCE EVIDENCE"},
    ]
    geometry = measure_chat_geometry(
        _CharacterTokenizer(),
        messages,
        enable_thinking=None,
        evidence="EVIDENCE",
        query="QUERY",
    )
    assert geometry["span_status"] == "unavailable"
    assert geometry["evidence_to_query_tokens"] is None


def test_template_ids_must_agree_with_rendered_offsets() -> None:
    class BadTokenizer(_CharacterTokenizer):
        def __call__(
            self,
            text: str,
            *,
            add_special_tokens: bool,
            return_offsets_mapping: bool,
        ) -> dict[str, list[Any]]:
            result = super().__call__(
                text,
                add_special_tokens=add_special_tokens,
                return_offsets_mapping=return_offsets_mapping,
            )
            result["input_ids"] = result["input_ids"][:-1]
            return result

    with pytest.raises(ValueError, match="disagree"):
        measure_chat_geometry(
            BadTokenizer(),
            [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
            enable_thinking=None,
        )


def test_legacy_payload_is_captured_without_network_or_thinking_override() -> None:
    payload = _capture_legacy_payload("exact prompt")
    assert payload["messages"] == [
        {
            "role": "system",
            "content": "You are the project worker. Follow the requested output format exactly.",
        },
        {"role": "user", "content": "exact prompt"},
    ]
    assert payload["model"] == "Qwen/Qwen3.6-27B"
    assert payload["seed"] == 42
    assert payload["temperature"] == 0.0
    assert "chat_template_kwargs" not in payload


@pytest.mark.parametrize("group", ["B", "C"])
def test_capture_full_offline_fixed_baseline_prompts(group: str) -> None:
    prompts, run, worlds = _offline_requests(group)
    assert worlds and prompts
    assert len(prompts) == run["model_calls"]
    assert any("[[doc:" in prompt for prompt in prompts)
    transcript = cast(list[dict[str, Any]], run["model_transcript"])
    anchored = [
        _span_anchor(prompt, entry["stage_id"], worlds)
        for prompt, entry in zip(prompts, transcript, strict=True)
    ]
    assert any(
        evidence and query and kind == "visible_stage_document_to_question"
        for evidence, query, kind in anchored
    )
