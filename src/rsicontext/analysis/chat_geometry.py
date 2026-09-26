"""Local chat-template positions for an exactly captured two-message request.

These counts describe the pinned local tokenizer/template. Provider parity is
an independent attestation, so callers must label that boundary separately.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class ChatTokenizer(Protocol):
    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
        **kwargs: Any,
    ) -> str | list[int] | Mapping[str, Sequence[int]]: ...

    def __call__(
        self,
        text: str,
        *,
        add_special_tokens: bool,
        return_offsets_mapping: bool,
    ) -> Mapping[str, Sequence[Any]]: ...


def _unique_at(text: str, needle: str) -> int | None:
    if not needle:
        return None
    start = text.find(needle)
    if start < 0 or text.find(needle, start + 1) >= 0:
        return None
    return start


def _interval(offsets: Sequence[Any], start: int, end: int) -> list[int] | None:
    indices = [
        index
        for index, value in enumerate(offsets)
        if isinstance(value, (tuple, list))
        and len(value) == 2
        and isinstance(value[0], int)
        and isinstance(value[1], int)
        and value[1] > value[0]
        and value[0] < end
        and value[1] > start
    ]
    if not indices:
        return None
    return [indices[0], indices[-1] + 1]


def measure_chat_geometry(
    tokenizer: ChatTokenizer,
    messages: list[dict[str, str]],
    *,
    enable_thinking: bool | None,
    evidence: str | None = None,
    query: str | None = None,
) -> dict[str, object]:
    """Count complete rendered input and uniquely identifiable user spans.

    Offsets are half-open tokenizer indices. Missing or repeated spans are
    explicitly unavailable. The query must occur after the evidence in the
    same user message for a meaningful distance.
    """

    if len(messages) != 2 or [item.get("role") for item in messages] != ["system", "user"]:
        raise ValueError("expected frozen system and user messages")
    user = messages[1].get("content")
    if not isinstance(user, str) or not user:
        raise ValueError("expected a non-empty user prompt")
    kwargs: dict[str, Any] = {}
    if enable_thinking is not None:
        kwargs["enable_thinking"] = enable_thinking
    rendered = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, **kwargs
    )
    tokenized = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, **kwargs
    )
    ids = tokenized.get("input_ids") if isinstance(tokenized, Mapping) else tokenized
    if (
        not isinstance(rendered, str)
        or not isinstance(ids, list)
        or not all(isinstance(item, int) for item in ids)
    ):
        raise TypeError("tokenizer must render text and integer token IDs")
    encoded = tokenizer(rendered, add_special_tokens=False, return_offsets_mapping=True)
    encoded_ids = encoded["input_ids"]
    offsets = encoded["offset_mapping"]
    if list(encoded_ids) != ids or len(offsets) != len(ids):
        raise ValueError("rendered text and template token IDs disagree")
    user_start = _unique_at(rendered, user)
    if user_start is None:
        raise ValueError("user prompt is missing or repeated in rendered chat")
    result: dict[str, object] = {
        "rendered_input_tokens": len(ids),
        "rendered_utf8_bytes": len(rendered.encode("utf-8")),
        "user_span_tokens": _interval(offsets, user_start, user_start + len(user)),
        "evidence_span_tokens": None,
        "query_span_tokens": None,
        "evidence_to_query_tokens": None,
        "span_status": "unavailable",
    }
    evidence_start = _unique_at(user, evidence) if evidence is not None else None
    query_start = _unique_at(user, query) if query is not None else None
    evidence_interval = (
        _interval(offsets, user_start + evidence_start, user_start + evidence_start + len(evidence))
        if evidence_start is not None and evidence is not None
        else None
    )
    query_interval = (
        _interval(offsets, user_start + query_start, user_start + query_start + len(query))
        if query_start is not None and query is not None
        else None
    )
    result["evidence_span_tokens"] = evidence_interval
    result["query_span_tokens"] = query_interval
    if evidence_start is None or query_start is None or evidence is None or query is None:
        return result
    if query_start < evidence_start + len(evidence):
        return result
    if evidence_interval is None or query_interval is None:
        return result
    if evidence_interval[1] > query_interval[0]:
        return result
    result.update(
        evidence_span_tokens=evidence_interval,
        query_span_tokens=query_interval,
        evidence_to_query_tokens=query_interval[0] - evidence_interval[1],
        span_status="unique_later_query",
    )
    return result
