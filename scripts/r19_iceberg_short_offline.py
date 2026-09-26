#!/usr/bin/env python3
"""Freeze two Iceberg S2-only rule probes without a model request."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import audit_r18_iceberg_geometry as geometry_source  # noqa: E402
import r15_exact_profile_canary as canary  # noqa: E402

from rsicontext.analysis.chat_geometry import (  # noqa: E402
    ChatTokenizer,
    measure_chat_geometry,
)
from rsicontext.experiment.api import APIProfile  # noqa: E402
from rsicontext.lifecycle.material_iceberg_row_scan import (  # noqa: E402
    SOURCE_REVISION,
    SOURCE_SHA256,
    build_iceberg_row_scan_sessions,
)

REGISTRATION = ROOT / "configs/r19_iceberg_short_registration_v1.json"
R18_GEOMETRY = ROOT / "docs/reviews/r18-iceberg-geometry.json"
R18_GEOMETRY_SHA256 = "aec96c97e921163431f306728c5469ce8e9673186a73f19b0de46f90afa35448"
REGISTRY_SHA256 = "7ac3a92dcbf9128c2b39ef16978bb9d08854612a85126b98165f62ecd8a9c1a0"
RULES = {
    "data-counter": "counter=data; bound=strict; partition=same-or-global; row=all-equality-ids",
    "file-counter": "counter=file; bound=strict; partition=same-or-global; row=all-equality-ids",
}
CASE_ORDER = tuple(RULES)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _request_payload(profile: APIProfile, prompt: str) -> dict[str, object]:
    if not profile.system_prompt:
        raise ValueError("Iceberg short probe lacks frozen system prompt")
    return {
        "chat_template_kwargs": {"enable_thinking": False},
        "max_tokens": profile.max_output_tokens,
        "messages": [
            {"role": "system", "content": profile.system_prompt},
            {"role": "user", "content": prompt},
        ],
        "model": profile.model,
        "seed": profile.seed,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": 0.0,
    }


def build_registration(
    source_root: Path, tokenizer_root: Path, *, profile: APIProfile, tokenizer: ChatTokenizer
) -> dict[str, object]:
    """Bind source facts and exact API requests; do not expose source to the model."""

    if _sha((ROOT / "configs/registry.json").read_bytes()) != REGISTRY_SHA256:
        raise ValueError("R19 registry differs from preregistered bytes")
    if _sha(R18_GEOMETRY.read_bytes()) != R18_GEOMETRY_SHA256:
        raise ValueError("R18 geometry differs from reviewed bytes")
    prior = json.loads(R18_GEOMETRY.read_bytes())
    if not isinstance(prior, dict):
        raise ValueError("R18 geometry is invalid")
    if geometry_source._source_git_identity(source_root) != prior["source_git"]:
        raise ValueError("Iceberg source Git identity differs from R18")
    if prior["source"]["source_sha256"] != SOURCE_SHA256:
        raise ValueError("Iceberg source bytes differ from R18")
    if (
        prior["profile_sha256"] != profile.profile_hash
        or profile.profile_hash != canary.PROFILE_SHA256
    ):
        raise ValueError("Iceberg short profile differs from R18")
    for name, expected in prior["tokenizer_files_sha256"].items():
        if _sha((tokenizer_root / name).read_bytes()) != expected:
            raise ValueError(f"Iceberg tokenizer file drifted: {name}")
    if prior["tokenizer_root_resolved"] != str(tokenizer_root.resolve()):
        raise ValueError("Iceberg tokenizer root differs from R18")
    request = build_iceberg_row_scan_sessions(source_root, case="authentic-pack")[1]
    request_text = request.stages[1].documents[0].text
    if _sha(request_text.encode()) != prior["fixed_later_request_utf8_sha256"]:
        raise ValueError("Iceberg constructed S2 request differs from R18")
    requests: list[dict[str, object]] = []
    prompts: dict[str, str] = {}
    for case in CASE_ORDER:
        rule = RULES[case]
        prompt = geometry_source.decision_user(request_text, rule)
        prompts[case] = prompt
        payload = _request_payload(profile, prompt)
        messages = cast(list[dict[str, str]], payload["messages"])
        measured = measure_chat_geometry(
            tokenizer,
            messages,
            enable_thinking=False,
            evidence=f"Retained source rule: {rule}.",
            query=geometry_source._DECISION_QUERY,
        )
        old = prior["session_2_by_retained_rule"][rule]
        measured_count = measured["rendered_input_tokens"]
        if (
            type(measured_count) is not int
            or measured_count != old["input_tokens"]
            or measured["evidence_span_tokens"] != old["evidence_span_tokens"]
            or measured["query_span_tokens"] != old["query_span_tokens"]
            or measured["span_status"] != "unique_later_query"
            or _sha(_canonical(messages)) != old["messages_sha256"]
            or measured_count + profile.max_output_tokens > 32768
        ):
            raise ValueError("Iceberg S2 chat geometry differs from R18")
        requests.append(
            {
                "case": case,
                "prompt_sha256": _sha(prompt.encode()),
                "request_sha256": _sha(_canonical(payload)),
                "local_template_geometry": measured,
            }
        )
    # The frozen request and every other rule clause must remain identical.
    if prompts["data-counter"].replace("counter=data", "counter=<counter>") != prompts[
        "file-counter"
    ].replace("counter=file", "counter=<counter>"):
        raise ValueError("Iceberg short prompts differ outside the rule counter")
    total_input = sum(
        cast(int, cast(dict[str, object], item["local_template_geometry"])["rendered_input_tokens"])
        for item in requests
    )
    return {
        "schema_version": 1,
        "scope": "r19-iceberg-s2-only-feasibility",
        "interpretation": "short rule application only; no long-source or parent qualification",
        "source_revision": SOURCE_REVISION,
        "source_sha256": SOURCE_SHA256,
        "registry_sha256": REGISTRY_SHA256,
        "r18_geometry_sha256": R18_GEOMETRY_SHA256,
        "fixed_request_sha256": _sha(request_text.encode()),
        "profile_sha256": profile.profile_hash,
        "tokenizer_manifest_sha256": canary.TOKENIZER_MANIFEST_SHA256,
        "case_order": list(CASE_ORDER),
        "target_call_cap": 2,
        "auxiliary_call_cap": 0,
        "local_input_tokens": total_input,
        "requested_output_tokens": 2 * profile.max_output_tokens,
        "local_input_plus_requested_ceiling": total_input + 2 * profile.max_output_tokens,
        "requests": requests,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--tokenizer-path", type=Path, required=True)
    parser.add_argument("--write-registration", action="store_true")
    args = parser.parse_args()
    profile = canary._profile()
    tokenizer = canary._tokenizer(args.tokenizer_path)
    generated = build_registration(
        args.source_root, args.tokenizer_path, profile=profile, tokenizer=tokenizer
    )
    if args.write_registration:
        REGISTRATION.write_text(json.dumps(generated, indent=2, sort_keys=True) + "\n")
    if json.loads(REGISTRATION.read_bytes()) != generated:
        raise ValueError("R19 short registration differs from generated material")
    print(
        json.dumps(
            {"status": "registered", "registration_sha256": _sha(REGISTRATION.read_bytes())}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
