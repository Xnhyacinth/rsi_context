#!/usr/bin/env python3
"""Freeze R18 KEP short-input calibration and exercise its local fake chain."""

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
import r17_kep_diagnostic_offline as r17_fake  # noqa: E402

from rsicontext.analysis.chat_geometry import ChatTokenizer  # noqa: E402
from rsicontext.analysis.k8s_calibration_r18 import (  # noqa: E402
    CASE_ORDER,
    build_registration,
    interpret_reply,
    projected_rule,
    prompts,
)
from rsicontext.analysis.k8s_diagnostic_r17 import amendment_text  # noqa: E402
from rsicontext.analysis.otel_siflow_pilot import _Worker  # noqa: E402
from rsicontext.experiment.api import APIProfile, ResolvedAPIEndpoint  # noqa: E402

REGISTRATION = ROOT / "configs/r18_kep_short_calibration_v1.json"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def run_offline(
    source_root: Path,
    r16_task: Path,
    r17_task: Path,
    *,
    profile: APIProfile,
    tokenizer: ChatTokenizer,
    registration: dict[str, object],
    answers: dict[str, str] | None = None,
) -> dict[str, object]:
    """Run only four registered local SSE responses; no credential resolution."""

    generated = build_registration(
        source_root, r16_task, r17_task, profile=profile, tokenizer=tokenizer
    )
    if registration != generated:
        raise ValueError("R18 source, observation or prompt registration drifted")
    requests = registration.get("requests")
    if not isinstance(requests, list) or len(requests) != len(CASE_ORDER):
        raise ValueError("R18 request count differs from frozen cap")
    by_hash: dict[str, dict[str, object]] = {}
    expected: dict[str, str] = {}
    for case, item in zip(CASE_ORDER, requests, strict=True):
        if not isinstance(item, dict) or item.get("case") != case:
            raise ValueError("R18 registered case order drifted")
        digest = item.get("prompt_sha256")
        if not isinstance(digest, str) or digest in by_hash:
            raise ValueError("R18 registered prompt hash is invalid")
        by_hash[digest] = item
        expected[digest] = case
    answer_map = answers if answers is not None else {
        "coarse-membership": "a_sidecar_m=300\nb_sidecar_m=0",
        "coarse-numeric": "effective_cpu_m=1200\nplan=hold-at-1000m",
        "explicit-membership": "a_sidecar_m=0\nb_sidecar_m=300",
        "explicit-numeric": "effective_cpu_m=800\nplan=admit-at-1000m",
    }
    if set(answer_map) != set(CASE_ORDER):
        raise ValueError("R18 fake answers differ from registered cases")

    def preflight(prompt: str) -> dict[str, object]:
        item = by_hash.get(_sha(prompt.encode()))
        if item is None:
            raise ValueError("R18 worker prompt is unregistered")
        return {
            "stage": item["case"],
            "prompt_sha256": item["prompt_sha256"],
            "request_sha256": item["request_sha256"],
            "local_template_geometry": item["local_template_geometry"],
        }

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        return r17_fake._fake_sse(
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
    rule, _ledger = projected_rule(source_root)
    rendered = prompts(amendment_text(source_root), rule)
    cases: list[dict[str, object]] = []
    for case in CASE_ORDER:
        reply = worker(rendered[case])
        cases.append({"case": case, "reply": reply, **interpret_reply(case, reply)})
    if worker.failed or len(worker.attempts) != len(CASE_ORDER):
        raise ValueError("R18 fake target calls differ from registered cap")
    return {
        "scope": registration["scope"],
        "status": "completed-synthetic-calibration",
        "provider_evidence": False,
        "target_calls": len(worker.attempts),
        "auxiliary_calls": 0,
        "cases": cases,
        "attempts": worker.attempts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--r16-task", type=Path, required=True)
    parser.add_argument("--r17-task", type=Path, required=True)
    parser.add_argument("--tokenizer-path", type=Path, required=True)
    parser.add_argument("--write-registration", action="store_true")
    args = parser.parse_args(argv)
    profile = canary._profile()
    tokenizer = canary._tokenizer(args.tokenizer_path)
    generated = build_registration(
        args.source_root, args.r16_task, args.r17_task, profile=profile, tokenizer=tokenizer
    )
    if args.write_registration:
        REGISTRATION.write_text(json.dumps(generated, indent=2, sort_keys=True) + "\n")
    frozen = cast(dict[str, object], json.loads(REGISTRATION.read_text()))
    result = run_offline(
        args.source_root,
        args.r16_task,
        args.r17_task,
        profile=profile,
        tokenizer=tokenizer,
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
