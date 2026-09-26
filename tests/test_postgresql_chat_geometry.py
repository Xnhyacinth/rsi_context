"""The B worker profile must bind its actual two-stage request geometry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rsicontext.analysis.chat_geometry import measure_chat_geometry
from rsicontext.analysis.postgresql_chat_geometry import measure_pg_worker_prompt
from rsicontext.experiment.api import load_api_profiles

PROFILE = load_api_profiles(
    Path(__file__).resolve().parent.parent / "configs/r11_pg_siflow_worker_profile_v1.json"
).get("siflow-qwen3.6-27b-r11-pg-dev-2048")


class CharacterTokenizer:
    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
        **kwargs: Any,
    ) -> str | list[int]:
        if not add_generation_prompt or kwargs.get("enable_thinking") is not False:
            raise ValueError("expected explicit non-thinking generation wrapper")
        rendered = "".join(f"<{part['role']}>{part['content']}" for part in messages) + "<A>"
        return [ord(character) for character in rendered] if tokenize else rendered

    def __call__(
        self,
        text: str,
        *,
        add_special_tokens: bool,
        return_offsets_mapping: bool,
    ) -> dict[str, list[Any]]:
        if add_special_tokens or not return_offsets_mapping:
            raise ValueError("unexpected tokenizer options")
        return {
            "input_ids": [ord(character) for character in text],
            "offset_mapping": [(index, index + 1) for index in range(len(text))],
        }


class TrimmingTokenizer(CharacterTokenizer):
    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
        **kwargs: Any,
    ) -> str | list[int]:
        trimmed = [dict(item) for item in messages]
        trimmed[-1]["content"] = trimmed[-1]["content"].rstrip()
        return super().apply_chat_template(
            trimmed, tokenize=tokenize, add_generation_prompt=add_generation_prompt, **kwargs
        )


def test_template_trailing_newline_trim_is_recorded() -> None:
    result = measure_chat_geometry(
        TrimmingTokenizer(),
        [{"role": "system", "content": "s"}, {"role": "user", "content": "evidence\n"}],
        enable_thinking=False,
        evidence="evidence\n",
    )
    assert result["user_trailing_whitespace_trimmed_chars"] == 1
    assert result["evidence_span_tokens"] is not None


def test_survey_span_and_exact_frozen_payload() -> None:
    prompt = (
        "Read the complete upstream CREATE SUBSCRIPTION SGML below. "
        "Return parameters.\n\n<refentry>unique evidence</refentry>"
    )
    record = measure_pg_worker_prompt(CharacterTokenizer(), PROFILE, prompt)
    assert record["stage"] == "source-survey"
    assert record["request"]["chat_template_kwargs"] == {"enable_thinking": False}  # type: ignore[index]
    assert record["local_template_geometry"]["evidence_span_tokens"] is not None  # type: ignore[index]
    assert record["provider_template_parity"] == "unverified"


def test_later_query_span_is_after_catalog() -> None:
    prompt = (
        "Use ONLY the retained upstream parameter catalog.\n\n"
        "Retained catalog:\nparameters=failover,copy_data"
        "\n\nProject request:\n[[doc:project-request]] decide now"
    )
    record = measure_pg_worker_prompt(CharacterTokenizer(), PROFILE, prompt)
    assert record["stage"] == "project-request-stage"
    assert record["local_template_geometry"]["span_status"] == "unique_later_query"  # type: ignore[index]


@pytest.mark.parametrize(
    "prompt",
    [
        "Read the complete upstream CREATE SUBSCRIPTION SGML below.\n\nmissing source",
        "Use ONLY the retained upstream parameter catalog.\n\nRetained catalog:\nparameters=x",
        "unrecognized worker request",
    ],
)
def test_invalid_or_missing_decisive_spans_fail_closed(prompt: str) -> None:
    with pytest.raises(ValueError):
        measure_pg_worker_prompt(CharacterTokenizer(), PROFILE, prompt)
