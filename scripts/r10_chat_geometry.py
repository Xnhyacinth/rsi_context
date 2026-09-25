#!/usr/bin/env python3
"""Capture R3 B/C fixed-baseline worker requests without network access.

This measures the pinned LOCAL Qwen chat template. The legacy R3 caller does
not send ``enable_thinking=False``; provider template parity remains unknown.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import cast
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import r3_compare
from r2a_compare import READER_ENDPOINT, READER_MODEL, _live_responder_factory, _offline_responder

from rsicontext.analysis.chat_geometry import ChatTokenizer, measure_chat_geometry
from rsicontext.lifecycle.group_baselines import (
    group_b_basline_policy_text,
    group_c_baseline_policy_text,
)
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.registry.tokenizer import verify_tokenizer_snapshot

_ROOT = Path(__file__).resolve().parent.parent
_TOKENIZER_FILES = (
    ("tokenizer.json", "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"),
    (
        "tokenizer_config.json",
        "dbfb3c20ce3d5b8370faeecd548e771c1dcc8e4fdcf636797fc24b0d0733fb02",
    ),
)
_QUERY_ANCHORS = (
    "Which verification check does this constraint require",
    "Does this change invalidate any verification evidence",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _offline_requests(group: str) -> tuple[list[str], dict[str, object], list[LifecycleInstance]]:
    if group == "B":
        worlds, _ = r3_compare._b_worlds()
        policy = group_b_basline_policy_text()
        turns = 2
    elif group == "C":
        worlds, _ = r3_compare._c_worlds()
        policy = group_c_baseline_policy_text()
        turns = 3
    else:
        raise ValueError("group must be B or C")
    prompts: list[str] = []

    def responder(prompt: str) -> str:
        prompts.append(prompt)
        return _offline_responder(prompt)

    spec = r3_compare.GroupSpec(
        group,
        worlds,
        [],
        shape="sequence",
        turns=turns,
        baseline_policy=policy,
        dev_experience_stages=[],
    )
    run = r3_compare._run_arm_on_group(spec, policy, responder)
    if len(prompts) != run["model_calls"]:
        raise ValueError("captured prompts do not match dispatched model calls")
    transcript = run["model_transcript"]
    if not isinstance(transcript, list) or len(transcript) != len(prompts):
        raise ValueError("model transcript does not match captured calls")
    for prompt, entry in zip(prompts, transcript, strict=True):
        if not isinstance(entry, dict) or entry.get("prompt_sha256") != _sha(prompt.encode())[:12]:
            raise ValueError("transcript prompt digest mismatch")
    return prompts, run, worlds


class _Response:
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"model":"offline","choices":[{"message":{"content":""},"finish_reason":"stop"}]}'


def _capture_legacy_payload(prompt: str) -> dict[str, object]:
    observed: list[dict[str, object]] = []

    def intercept(request: urllib.request.Request, *, timeout: int) -> _Response:
        if request.full_url != READER_ENDPOINT or timeout != 300 or request.data is None:
            raise ValueError("unexpected worker request envelope")
        if not isinstance(request.data, bytes):
            raise TypeError("worker request body must be bytes")
        body = json.loads(request.data)
        if not isinstance(body, dict):
            raise TypeError("worker request is not a JSON object")
        observed.append(body)
        return _Response()

    with (
        patch.dict(os.environ, {"SIFLOW_API_KEY": "offline-sentinel"}),
        patch.object(urllib.request, "urlopen", intercept),
    ):
        responder = _live_responder_factory()
        responder(prompt)
    if len(observed) != 1:
        raise ValueError("expected exactly one intercepted worker request")
    payload = observed[0]
    messages = payload.get("messages")
    if (
        payload.get("model") != READER_MODEL
        or not isinstance(messages, list)
        or len(messages) != 2
        or messages[1] != {"role": "user", "content": prompt}
        or "chat_template_kwargs" in payload
    ):
        raise ValueError("legacy R3 worker envelope changed")
    return payload


def _span_anchor(
    prompt: str, stage_id: str, worlds: list[LifecycleInstance]
) -> tuple[str | None, str | None, str]:
    candidates = [
        doc.text
        for world in worlds
        for stage in world.stages
        if stage.stage_id == stage_id
        for doc in stage.documents
        if prompt.count(doc.text) == 1
    ]
    anchors = [anchor for anchor in _QUERY_ANCHORS if prompt.count(anchor) == 1]
    if len(candidates) != 1 or len(anchors) != 1:
        return None, None, "no_unique_same_call_source_and_query"
    evidence, anchor = candidates[0], anchors[0]
    query_start = prompt.index(anchor)
    query_end = prompt.find("?", query_start + len(anchor))
    if query_end < 0:
        return None, None, "question_has_no_terminator"
    query = prompt[query_start : query_end + 1]
    if prompt.count(query) != 1:
        return None, None, "question_is_not_unique"
    if query_start < prompt.index(evidence) + len(evidence):
        return None, None, "query_not_later_than_source"
    return evidence, query, "visible_stage_document_to_full_question"


def build_report(tokenizer: ChatTokenizer, *, tokenizer_path: Path) -> dict[str, object]:
    snapshot = verify_tokenizer_snapshot(tokenizer_path, _TOKENIZER_FILES)
    groups: dict[str, object] = {}
    for group in ("B", "C"):
        prompts, run, worlds = _offline_requests(group)
        transcript = cast(list[dict[str, object]], run["model_transcript"])
        calls: list[dict[str, object]] = []
        for index, (prompt, entry) in enumerate(zip(prompts, transcript, strict=True)):
            payload = _capture_legacy_payload(prompt)
            messages = cast(list[dict[str, str]], payload["messages"])
            stage_id = str(entry["stage_id"])
            evidence, query, span_kind = _span_anchor(prompt, stage_id, worlds)
            geometry = measure_chat_geometry(
                tokenizer, messages, enable_thinking=None, evidence=evidence, query=query
            )
            calls.append(
                {
                    "index": index,
                    "stage_id": stage_id,
                    "request_sha256": _sha(_canonical(payload)),
                    "prompt_sha256": _sha(prompt.encode()),
                    "request": payload,
                    "span_kind": span_kind,
                    "evidence_sha256": _sha(evidence.encode()) if evidence is not None else None,
                    "query_sha256": _sha(query.encode()) if query is not None else None,
                    "local_template_geometry": geometry,
                }
            )
        groups[group] = {
            "world_sha256": [_sha(_canonical(world.to_dict())) for world in worlds],
            "policy_sha256": _sha(
                (
                    group_b_basline_policy_text()
                    if group == "B"
                    else group_c_baseline_policy_text()
                ).encode()
            ),
            "offline_model_calls": run["model_calls"],
            "offline_passed": run["passed"],
            "calls": calls,
        }
    return {
        "schema_version": 1,
        "scope": "legacy_r3_b_c_fixed_baseline_development_only",
        "interpretation": (
            "Exact request payloads captured from the legacy R3 worker factory without network; "
            "token counts and offsets are exact for the pinned LOCAL Qwen template only. "
            "The legacy R3 request omits chat_template_kwargs; Siflow provider template/default "
            "parity is unverified. These older B/C worlds do not qualify the R9 source pair."
        ),
        "tokenizer": {
            "revision": "Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b",
            "files_sha256": snapshot,
            "runtime": "transformers==5.15.0 tokenizers==0.22.2 jinja2==3.1.6 from uv.lock",
        },
        "source_sha256": {
            name: _sha((_ROOT / name).read_bytes())
            for name in (
                "scripts/r2a_compare.py",
                "scripts/r3_compare.py",
                "scripts/r10_chat_geometry.py",
                "src/rsicontext/analysis/chat_geometry.py",
                "src/rsicontext/lifecycle/group_baselines.py",
                "src/rsicontext/lifecycle/session_sequence.py",
                "uv.lock",
            )
        },
        "groups": groups,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES)
    try:
        import jinja2  # type: ignore[import-not-found]  # optional tokenizer runtime
        import tokenizers  # type: ignore[import-not-found]  # optional tokenizer runtime
        import transformers  # type: ignore[import-not-found]  # optional tokenizer runtime
    except ImportError as exc:
        raise RuntimeError(
            "install pinned transformers==5.15.0, tokenizers==0.22.2 and "
            "jinja2==3.1.6 in an "
            "isolated uv environment before measuring; no proxy count is emitted"
        ) from exc
    if (
        transformers.__version__ != "5.15.0"
        or tokenizers.__version__ != "0.22.2"
        or jinja2.__version__ != "3.1.6"
    ):
        raise ValueError("tokenizer runtime versions differ from uv.lock")
    tokenizer = cast(
        ChatTokenizer,
        transformers.AutoTokenizer.from_pretrained(
            str(args.tokenizer_path),
            local_files_only=True,  # nosec B615
        ),
    )
    report = build_report(tokenizer, tokenizer_path=args.tokenizer_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(json.dumps(report, indent=2, ensure_ascii=False).encode() + b"\n")
    print(f"{args.output} sha256={_sha(args.output.read_bytes())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
