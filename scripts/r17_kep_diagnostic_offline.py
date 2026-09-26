#!/usr/bin/env python3
"""Freeze or verify R17 KEP diagnostic requests and exercise a local fake path."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import r15_exact_profile_canary as canary  # noqa: E402

from rsicontext.analysis.chat_geometry import ChatTokenizer, measure_chat_geometry  # noqa: E402
from rsicontext.analysis.k8s_diagnostic_r17 import (  # noqa: E402
    CASE_ORDER,
    amendment_text,
    build_registration,
    interpret_reply,
    prompts,
)
from rsicontext.analysis.otel_siflow_pilot import _Worker  # noqa: E402
from rsicontext.experiment.api import APIProfile, ResolvedAPIEndpoint  # noqa: E402

REGISTRATION = ROOT / "configs/r17_kep_diagnostic_v1.json"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _fake_sse(
    request: urllib.request.Request,
    _timeout: float,
    *,
    tokenizer: ChatTokenizer,
    profile: APIProfile,
    answers: dict[str, str],
    expected: dict[str, str],
) -> bytes:
    if not isinstance(request.data, bytes):
        raise ValueError("synthetic request has no body")
    body = json.loads(request.data)
    messages = body.get("messages")
    if (
        body.get("model") != profile.model
        or not isinstance(messages, list)
        or len(messages) != 2
        or messages[0] != {"role": "system", "content": profile.system_prompt}
        or not isinstance(messages[1], dict)
        or not isinstance(messages[1].get("content"), str)
    ):
        raise ValueError("synthetic request differs from frozen profile")
    digest = _sha(messages[1]["content"].encode())
    case = expected.get(digest)
    if case is None:
        raise ValueError("synthetic request has unregistered prompt")
    answer = answers[case]
    input_tokens = measure_chat_geometry(
        tokenizer, messages, enable_thinking=False
    )["rendered_input_tokens"]
    output_tokens = len(
        tokenizer(answer, add_special_tokens=False, return_offsets_mapping=True)["input_ids"]
    )
    if not isinstance(input_tokens, int) or output_tokens <= 0:
        raise ValueError("synthetic tokenizer could not count request")
    identity = {"id": "offline-r17-" + case, "model": profile.model}
    content = {
        **identity,
        "choices": [{"delta": {"content": answer}, "finish_reason": "stop"}],
    }
    usage = {
        **identity,
        "choices": [],
        "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens},
    }
    return (
        "data: "
        + json.dumps(content)
        + "\n\ndata: "
        + json.dumps(usage)
        + "\n\ndata: [DONE]\n\n"
    ).encode()


def run_offline(
    source_root: Path,
    task_path: Path,
    *,
    tokenizer: ChatTokenizer,
    profile: APIProfile,
    registration: dict[str, object],
    answers: dict[str, str] | None = None,
) -> dict[str, object]:
    """Run exactly four fake target calls after byte-for-byte registration check."""

    generated = build_registration(source_root, task_path, profile=profile, tokenizer=tokenizer)
    if registration != generated:
        raise ValueError("R17 prompt, source, observation or tokenizer registration drifted")
    requests = registration.get("requests")
    if not isinstance(requests, list) or len(requests) != len(CASE_ORDER):
        raise ValueError("R17 request count differs from frozen cap")
    by_hash: dict[str, dict[str, object]] = {}
    expected: dict[str, str] = {}
    for case, item in zip(CASE_ORDER, requests, strict=True):
        if not isinstance(item, dict) or item.get("case") != case:
            raise ValueError("R17 registered case order drifted")
        digest = item.get("prompt_sha256")
        if not isinstance(digest, str) or digest in by_hash:
            raise ValueError("R17 prompt hash is invalid or duplicate")
        by_hash[digest] = item
        expected[digest] = case
    answer_map = answers or {
        "legacy-with-prior": "plan=hold-at-1000m",
        "rule-membership": "a_sidecar_m=0\nb_sidecar_m=300",
        "numeric-with-prior": "effective_cpu_m=1100\nplan=hold-at-1000m",
        "numeric-without-prior": "effective_cpu_m=800\nplan=admit-at-1000m",
    }
    if set(answer_map) != set(CASE_ORDER):
        raise ValueError("synthetic answer cases differ from registration")

    def preflight(prompt: str) -> dict[str, object]:
        item = by_hash.get(_sha(prompt.encode()))
        if item is None:
            raise ValueError("R17 worker prompt is unregistered")
        return {
            "stage": item["case"],
            "prompt_sha256": item["prompt_sha256"],
            "request_sha256": item["request_sha256"],
            "local_template_geometry": item["local_template_geometry"],
        }

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        return _fake_sse(
            request,
            timeout,
            tokenizer=tokenizer,
            profile=profile,
            answers=answer_map,
            expected=expected,
        )

    worker = _Worker(
        profile,
        ResolvedAPIEndpoint(endpoint=canary.ENDPOINT, api_key="synthetic-test-key"),
        preflight,
        transport,
    )
    rendered = prompts(amendment_text(source_root))
    results: list[dict[str, object]] = []
    for case in CASE_ORDER:
        reply = worker(rendered[case])
        results.append({"case": case, "reply": reply, **interpret_reply(case, reply)})
    if worker.failed or len(worker.attempts) != 4:
        raise ValueError("R17 fake target-call cap or worker contract failed")
    return {
        "scope": registration["scope"],
        "status": "completed-synthetic-diagnostic",
        "provider_evidence": False,
        "target_calls": len(worker.attempts),
        "auxiliary_calls": 0,
        "cases": results,
        "attempts": worker.attempts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--r16-task", type=Path, required=True)
    parser.add_argument("--tokenizer-path", type=Path, required=True)
    parser.add_argument("--write-registration", action="store_true")
    args = parser.parse_args(argv)
    profile = canary._profile()
    tokenizer = canary._tokenizer(args.tokenizer_path)
    generated = build_registration(
        args.source_root, args.r16_task, profile=profile, tokenizer=tokenizer
    )
    if args.write_registration:
        REGISTRATION.write_text(json.dumps(generated, indent=2, sort_keys=True) + "\n")
    frozen = cast(dict[str, object], json.loads(REGISTRATION.read_text()))
    result = run_offline(
        args.source_root,
        args.r16_task,
        tokenizer=tokenizer,
        profile=profile,
        registration=frozen,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "target_calls": result["target_calls"],
                "registration_sha256": _sha(REGISTRATION.read_bytes()),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
