"""Exact local geometry for the frozen PostgreSQL two-stage worker request.

The caller supplies the pinned local tokenizer. Counts and offsets are local
template evidence; a provider's prompt-token count must be checked separately.
"""

from __future__ import annotations

import hashlib
import json

from rsicontext.analysis.chat_geometry import ChatTokenizer, measure_chat_geometry
from rsicontext.experiment.api import APIProfile

SYSTEM_PROMPT = (
    "You are the project worker. Follow the requested output format exactly. "
    "For questions, return only the answer phrase."
)
_S1_PREFIX = "Read the complete upstream CREATE SUBSCRIPTION SGML below."
_S2_PREFIX = "Use ONLY the retained upstream parameter catalog"
_S2_CATALOG = "Retained catalog:\n"
_S2_REQUEST = "\n\nProject request:\n"


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _unique_tail(prompt: str, marker: str) -> str:
    if prompt.count(marker) != 1:
        raise ValueError(f"worker prompt must contain one {marker!r} delimiter")
    tail = prompt.split(marker, 1)[1]
    if not tail or prompt.count(tail) != 1:
        raise ValueError("worker evidence or query is missing or repeated")
    return tail


def _payload(profile: APIProfile, prompt: str) -> dict[str, object]:
    if (
        profile.model != "Qwen/Qwen3.6-27B"
        or profile.provider != "Siflow"
        or profile.system_prompt != SYSTEM_PROMPT
        or profile.chat_template_enable_thinking is not False
        or profile.protocol != "chat-completions-sse"
        or profile.temperature != 0.0
    ):
        raise ValueError("PostgreSQL worker profile does not match frozen Qwen request")
    return {
        "chat_template_kwargs": {"enable_thinking": False},
        "max_tokens": profile.max_output_tokens,
        "messages": [
            {"content": SYSTEM_PROMPT, "role": "system"},
            {"content": prompt, "role": "user"},
        ],
        "model": profile.model,
        "seed": profile.seed,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": 0.0,
    }


def measure_pg_worker_prompt(
    tokenizer: ChatTokenizer, profile: APIProfile, prompt: str
) -> dict[str, object]:
    """Preflight one actual S1/S2 prompt or reject unidentifiable source/query spans."""

    if not isinstance(prompt, str) or not prompt or "\x00" in prompt:
        raise ValueError("worker prompt must be non-empty text without NUL")
    payload = _payload(profile, prompt)
    query: str | None = None
    if prompt.startswith(_S1_PREFIX):
        stage = "source-survey"
        if "\n\n" not in prompt:
            raise ValueError("survey prompt has no source separator")
        evidence = prompt.split("\n\n", 1)[1]
        if prompt.count(evidence) != 1 or "<refentry" not in evidence:
            raise ValueError("survey prompt is missing complete SGML source")
    elif prompt.startswith(_S2_PREFIX):
        stage = "project-request-stage"
        if prompt.count(_S2_CATALOG) != 1 or prompt.count(_S2_REQUEST) != 1:
            raise ValueError("project prompt has missing or repeated section delimiters")
        evidence = prompt.split(_S2_CATALOG, 1)[1].split(_S2_REQUEST, 1)[0]
        query = _unique_tail(prompt, _S2_REQUEST)
        if not evidence.startswith("parameters=") or not query.startswith(
            "[[doc:project-request]]"
        ):
            raise ValueError("project prompt has an invalid catalog or visible request")
    else:
        raise ValueError("unexpected PostgreSQL fixed-policy worker prompt")
    messages = payload["messages"]
    if not isinstance(messages, list):
        raise ValueError("worker request messages are invalid")
    geometry = measure_chat_geometry(
        tokenizer, messages, enable_thinking=False, evidence=evidence, query=query
    )
    evidence_span = geometry["evidence_span_tokens"]
    if not isinstance(evidence_span, list):
        raise ValueError("local tokenizer could not locate unique worker evidence")
    if stage == "project-request-stage" and (
        geometry["span_status"] != "unique_later_query"
        or not isinstance(geometry["query_span_tokens"], list)
    ):
        raise ValueError("local tokenizer could not locate later project request")
    rendered_count = geometry["rendered_input_tokens"]
    if not isinstance(rendered_count, int) or rendered_count + profile.max_output_tokens > (
        profile.evaluation_max_model_len
    ):
        raise ValueError("local rendered request exceeds registered model length")
    canonical_request = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return {
        "stage": stage,
        "profile_hash": profile.profile_hash,
        "request_sha256": _sha(canonical_request),
        "prompt_sha256": _sha(prompt.encode("utf-8")),
        "evidence_sha256": _sha(evidence.encode("utf-8")),
        "query_sha256": _sha(query.encode("utf-8")) if query is not None else None,
        "request": payload,
        "local_template_geometry": geometry,
        "provider_template_parity": "unverified",
    }


__all__ = ["SYSTEM_PROMPT", "measure_pg_worker_prompt"]
