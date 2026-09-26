"""The OTel worker preflight binds source bytes, decisive row, and later query."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import pytest

import rsicontext.analysis.otel_chat_geometry as otel_geometry
from rsicontext.analysis.otel_model_screen import run_case
from rsicontext.experiment.api import load_api_profiles
from rsicontext.lifecycle.material_otel_source_contrast import build_otel_source_contrast_sessions

PROFILE = load_api_profiles(
    Path(__file__).resolve().parent.parent / "configs/r12_otel_siflow_worker_profile_v1.json"
).get(otel_geometry.PROFILE_ID)
_MARKER = "[[doc:upstream-db]]\n"
_ROW = (
    "| [`db.query.text`](attributes.md) | `Recommended` | string | "
    "The database query being executed. | `SELECT ?` |\n"
)
_RAW = "# Database client span\n\n| Key | Requirement | Type | Description | Example |\n" + _ROW


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


@pytest.fixture
def pinned_synthetic_source(monkeypatch: pytest.MonkeyPatch) -> str:
    deleted = _RAW.replace(_ROW, "", 1)
    monkeypatch.setattr(otel_geometry, "SOURCE_SHA256", {"1.43": _sha(_RAW)})
    monkeypatch.setattr(otel_geometry, "_ROW_SHA256", {"1.43": _sha(_ROW)})
    monkeypatch.setattr(otel_geometry, "_DELETED_143_RAW_SHA256", _sha(deleted))
    monkeypatch.setattr(otel_geometry, "_DELETED_143_MATERIAL_SHA256", _sha(_MARKER + deleted))
    return _MARKER + _RAW


def _survey(source: str) -> str:
    return (
        "Read the complete upstream database client span convention below. "
        "Return exactly attribute=<key>.\n\n" + source
    )


def test_full_source_row_has_unique_local_span(pinned_synthetic_source: str) -> None:
    result = otel_geometry.measure_otel_worker_prompt(
        CharacterTokenizer(), PROFILE, _survey(pinned_synthetic_source)
    )
    assert result["stage"] == "source-survey"
    assert result["source_revision"] == "1.43"
    assert result["source_sha256"] == _sha(_RAW)
    assert result["visible_source_sha256"] == _sha(pinned_synthetic_source)
    assert result["decisive_row_status"] == "unique"
    assert result["decisive_row_sha256"] == _sha(_ROW)
    full = result["full_source_span_tokens"]
    decisive = result["local_template_geometry"]["evidence_span_tokens"]  # type: ignore[index]
    assert full[0] <= decisive[0] < decisive[1] <= full[1]  # type: ignore[index]
    assert result["request"]["chat_template_kwargs"] == {"enable_thinking": False}  # type: ignore[index]
    assert result["provider_template_parity"] == "unverified"


def test_exact_registered_row_deletion_is_labeled(pinned_synthetic_source: str) -> None:
    deleted = otel_geometry.remove_otel_decisive_row(pinned_synthetic_source)
    assert deleted == pinned_synthetic_source.replace(_ROW, "", 1)
    result = otel_geometry.measure_otel_worker_prompt(
        CharacterTokenizer(), PROFILE, _survey(deleted)
    )
    assert result["decisive_row_status"] == "removed"
    assert result["decisive_row_sha256"] is None
    assert result["full_source_span_tokens"] is not None


def test_arbitrary_missing_or_ambiguous_row_fails_closed(
    monkeypatch: pytest.MonkeyPatch, pinned_synthetic_source: str
) -> None:
    with pytest.raises(ValueError, match="approved pinned"):
        otel_geometry.measure_otel_worker_prompt(
            CharacterTokenizer(),
            PROFILE,
            _survey(pinned_synthetic_source.replace(_ROW, "").replace("span", "spans")),
        )
    duplicated = _RAW + _ROW
    monkeypatch.setattr(otel_geometry, "SOURCE_SHA256", {"1.43": _sha(duplicated)})
    with pytest.raises(ValueError, match="ambiguous"):
        otel_geometry.measure_otel_worker_prompt(
            CharacterTokenizer(), PROFILE, _survey(_MARKER + duplicated)
        )


def test_later_request_span_is_after_retained_attribute() -> None:
    prompt = (
        "Use only the retained upstream attribute and the visible new "
        "instrumentation request.\n\nRetained attribute:\nattribute=db.query.text"
        "\n\nProject request:\n[[doc:project-request]] Choose one field."
    )
    result = otel_geometry.measure_otel_worker_prompt(CharacterTokenizer(), PROFILE, prompt)
    assert result["stage"] == "project-request-stage"
    assert result["source_revision"] is None
    assert result["local_template_geometry"]["span_status"] == "unique_later_query"  # type: ignore[index]


@pytest.mark.parametrize(
    "prompt",
    [
        "unknown OTel worker prompt",
        "Use only the retained upstream attribute.\n\nRetained attribute:\nattribute=db.query.text",
        "Use only the retained upstream attribute.\n\nRetained attribute:\nattribute=db.query.text"
        "\n\nProject request:\nno marked request",
    ],
)
def test_missing_boundary_or_request_fails_closed(prompt: str) -> None:
    with pytest.raises(ValueError):
        otel_geometry.measure_otel_worker_prompt(CharacterTokenizer(), PROFILE, prompt)


def test_registered_deletion_surveys_twice_when_reread_is_available() -> None:
    configured = os.environ.get("RSICONTEXT_OTEL_SOURCE_ROOT")
    if not configured:
        pytest.skip("set RSICONTEXT_OTEL_SOURCE_ROOT to pinned detached checkout")
    sessions = build_otel_source_contrast_sessions(Path(configured), revision="1.43")
    source = sessions[0].stages[0].documents[0].text
    case = run_case(
        "registered-row-deleted-143",
        sessions,
        source_text=otel_geometry.remove_otel_decisive_row(source),
    )
    assert len(case.worker.prompts) == 2
    assert case.worker.prompts[0] == case.worker.prompts[1]
    assert case.worker.replies == ["invalid", "invalid"]
