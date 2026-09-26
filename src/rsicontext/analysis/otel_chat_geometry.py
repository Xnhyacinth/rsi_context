"""Exact local Qwen geometry for the frozen OTel two-stage worker prompts.

The source-survey row and later project request occur in separate model calls.
Their token positions must therefore be reported separately, not as a single
cross-session token distance. Provider template parity is checked elsewhere.
"""

from __future__ import annotations

import hashlib
import json
import re

from rsicontext.analysis.chat_geometry import ChatTokenizer, measure_chat_geometry
from rsicontext.experiment.api import APIProfile
from rsicontext.lifecycle.material_otel_source_contrast import SOURCE_SHA256

SYSTEM_PROMPT = (
    "You are the project worker. Follow the requested output format exactly. "
    "For questions, return only the answer phrase."
)
PROFILE_ID = "siflow-qwen3.6-27b-r12-otel-dev-2048"
_SOURCE_MARKER = "[[doc:upstream-db]]\n"
_S1_PREFIX = "Read the complete upstream database client span convention below."
_S2_PREFIX = "Use only the retained upstream attribute and the visible new"
_RETAINED = "\n\nRetained attribute:\n"
_REQUEST = "\n\nProject request:\n"
_ROW_KEY = {"1.24": "db.statement", "1.43": "db.query.text"}
_ROW_SHA256 = {
    "1.24": "d1221e989b04f5aa686158198b90aa5667f61834b81f41e51d6498da0466b8ea",
    "1.43": "e72da5becec0b61970037df08120d2f2e5f5fd1596405f520224f219237173c8",
}
_DELETED_143_RAW_SHA256 = "09f04822434b135bf4be57406e51e561bb488764cc9e581962425ba11f306946"
_DELETED_143_MATERIAL_SHA256 = "80fab68f70ce6d1542c5cfeb45b95b1e6cf6dbbfe4d67aadbb59f87dd9ccd97c"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _row(source: str, revision: str) -> str:
    key = _ROW_KEY[revision]
    rows = [
        line
        for line in source.splitlines(keepends=True)
        if line.startswith(f"| [`{key}`]")
        and "Recommended" in line
        and f"The database {'statement' if revision == '1.24' else 'query'} being executed." in line
    ]
    if len(rows) != 1 or _sha(rows[0].encode("utf-8")) != _ROW_SHA256[revision]:
        raise ValueError("source has missing, ambiguous, or modified decisive table row")
    return rows[0]


def remove_otel_decisive_row(source: str) -> str:
    """Construct the sole preregistered 1.43 row-deletion material exactly."""

    if not source.startswith(_SOURCE_MARKER):
        raise ValueError("OTel source marker is missing")
    raw = source[len(_SOURCE_MARKER) :]
    if _sha(raw.encode("utf-8")) != SOURCE_SHA256["1.43"]:
        raise ValueError("row deletion requires the exact pinned 1.43 source")
    row = _row(raw, "1.43")
    if not row.endswith("\n") or raw.count(row) != 1:
        raise ValueError("decisive row must occur once with its trailing newline")
    deleted = _SOURCE_MARKER + raw.replace(row, "", 1)
    if _sha(deleted.encode("utf-8")) != _DELETED_143_MATERIAL_SHA256:
        raise ValueError("row deletion differs from preregistered material")
    return deleted


def _payload(profile: APIProfile, prompt: str) -> dict[str, object]:
    if (
        profile.id != PROFILE_ID
        or profile.provider != "Siflow"
        or profile.allowed_host != "api.siflow.cn"
        or profile.model != "Qwen/Qwen3.6-27B"
        or profile.protocol != "chat-completions-sse"
        or profile.evaluation_max_model_len != 262144
        or profile.max_output_tokens != 2048
        or profile.seed != 42
        or profile.temperature != 0.0
        or profile.chat_template_enable_thinking is not False
        or profile.system_prompt != SYSTEM_PROMPT
    ):
        raise ValueError("OTel worker profile differs from frozen Qwen request")
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


def _source_span(
    tokenizer: ChatTokenizer, messages: list[dict[str, str]], source: str
) -> list[int]:
    geometry = measure_chat_geometry(tokenizer, messages, enable_thinking=False, evidence=source)
    span = geometry["evidence_span_tokens"]
    if not isinstance(span, list):
        raise ValueError("local tokenizer could not locate complete OTel source")
    return span


def measure_otel_worker_prompt(
    tokenizer: ChatTokenizer, profile: APIProfile, prompt: str
) -> dict[str, object]:
    """Preflight an actual frozen S1/S2 prompt, rejecting unknown material."""

    if not isinstance(prompt, str) or not prompt or "\x00" in prompt:
        raise ValueError("worker prompt must be non-empty text without NUL")
    payload = _payload(profile, prompt)
    messages = payload["messages"]
    if not isinstance(messages, list):
        raise ValueError("worker request messages are invalid")
    source_revision: str | None = None
    source_sha256: str | None = None
    visible_source_sha256: str | None = None
    decisive_row_sha256: str | None = None
    decisive_row_status: str | None = None
    full_source_span_tokens: list[int] | None = None
    query: str | None = None
    if prompt.startswith(_S1_PREFIX):
        stage = "source-survey"
        if prompt.count("\n\n" + _SOURCE_MARKER) != 1:
            raise ValueError("survey prompt must contain one marked upstream source")
        source = prompt.split("\n\n", 1)[1]
        if not source.startswith(_SOURCE_MARKER):
            raise ValueError("survey source marker is missing")
        raw = source[len(_SOURCE_MARKER) :]
        source_sha256 = _sha(raw.encode("utf-8"))
        visible_source_sha256 = _sha(source.encode("utf-8"))
        if source_sha256 == _DELETED_143_RAW_SHA256:
            if visible_source_sha256 != _DELETED_143_MATERIAL_SHA256:
                raise ValueError("row deletion material differs from registered bytes")
            source_revision = "1.43"
            decisive_row_status = "removed"
            if any(line.startswith("| [`db.query.text`]") for line in raw.splitlines()):
                raise ValueError("registered row deletion still contains decisive row")
            evidence = source
        else:
            matches = [rev for rev, digest in SOURCE_SHA256.items() if digest == source_sha256]
            if len(matches) != 1:
                raise ValueError("survey source is not an approved pinned OTel material")
            source_revision = matches[0]
            evidence = _row(raw, source_revision)
            decisive_row_sha256 = _sha(evidence.encode("utf-8"))
            if source.count(evidence) != 1:
                raise ValueError("decisive table row is repeated")
            decisive_row_status = "unique"
        full_source_span_tokens = _source_span(tokenizer, messages, source)
    elif prompt.startswith(_S2_PREFIX):
        stage = "project-request-stage"
        if prompt.count(_RETAINED) != 1 or prompt.count(_REQUEST) != 1:
            raise ValueError("project prompt has missing or repeated delimiters")
        evidence = prompt.split(_RETAINED, 1)[1].split(_REQUEST, 1)[0]
        query = prompt.split(_REQUEST, 1)[1]
        if (
            re.fullmatch(r"attribute=db[.][a-z.]+", evidence) is None
            or not query.startswith("[[doc:project-request]]")
            or prompt.count(evidence) != 1
            or prompt.count(query) != 1
        ):
            raise ValueError("project prompt has invalid retained attribute or request")
    else:
        raise ValueError("unexpected OTel fixed-policy worker prompt")
    geometry = measure_chat_geometry(
        tokenizer, messages, enable_thinking=False, evidence=evidence, query=query
    )
    evidence_span = geometry["evidence_span_tokens"]
    if not isinstance(evidence_span, list):
        raise ValueError("local tokenizer could not locate unique worker evidence")
    if stage == "source-survey" and (
        full_source_span_tokens is None
        or evidence_span[0] < full_source_span_tokens[0]
        or evidence_span[1] > full_source_span_tokens[1]
    ):
        raise ValueError("decisive row is outside the complete source span")
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
        "source_revision": source_revision,
        "source_sha256": source_sha256,
        "visible_source_sha256": visible_source_sha256,
        "decisive_row_status": decisive_row_status,
        "decisive_row_sha256": decisive_row_sha256,
        "full_source_span_tokens": full_source_span_tokens,
        "evidence_sha256": _sha(evidence.encode("utf-8")),
        "query_sha256": _sha(query.encode("utf-8")) if query is not None else None,
        "request": payload,
        "local_template_geometry": geometry,
        "provider_template_parity": "unverified",
    }


__all__ = ["PROFILE_ID", "SYSTEM_PROMPT", "measure_otel_worker_prompt", "remove_otel_decisive_row"]
