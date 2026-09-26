#!/usr/bin/env python3
"""Freeze four Iceberg S2-only rule probes without a model request."""

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

import r15_exact_profile_canary as canary  # noqa: E402
import r19_iceberg_short_offline as r19  # noqa: E402

from rsicontext.analysis.chat_geometry import (  # noqa: E402
    ChatTokenizer,
    measure_chat_geometry,
)
from rsicontext.experiment.api import APIProfile  # noqa: E402
from rsicontext.lifecycle.material_iceberg_row_scan import (  # noqa: E402
    SOURCE_REVISION,
    SOURCE_SHA256,
)

REGISTRATION = ROOT / "configs/r20_iceberg_short_registration_v1.json"
R18_GEOMETRY_SHA256 = "aec96c97e921163431f306728c5469ce8e9673186a73f19b0de46f90afa35448"
REGISTRY_SHA256 = "7ac3a92dcbf9128c2b39ef16978bb9d08854612a85126b98165f62ecd8a9c1a0"
RULES = {
    "data-counter-match": (
        "counter=data; bound=strict; partition=same-or-global; row=all-equality-ids"
    ),
    "file-counter-match": (
        "counter=file; bound=strict; partition=same-or-global; row=all-equality-ids"
    ),
    "data-counter-mismatch": (
        "counter=data; bound=strict; partition=same-or-global; row=all-equality-ids"
    ),
    "unknown-diagnostic": "counter=unknown; bound=unknown; partition=unknown; row=unknown",
}
CASE_ORDER = tuple(RULES)
DECISION_QUERY = "Return exactly plan=emit-row or plan=suppress-row."


def request_text(delete_value: int) -> str:
    """Construct a single-delete contrast with only the delete value changing."""

    if delete_value not in (42, 99):
        raise ValueError("unregistered Iceberg delete value")
    return (
        "A format-version 2 table scan reads one existing data file with a row "
        "whose field id 1 has value 42. The data file's data sequence number is 7 "
        "and its file sequence number is 12. Exactly one equality delete file "
        "passes query and metrics filters. It has data sequence number 8, an "
        "unpartitioned partition spec, equality_ids=[1], and delete value "
        f"{delete_value}. There are no other delete files or deletion vectors. "
        "Decide whether that row is emitted or suppressed under the retained rule."
    )


def decision_user(case: str) -> str:
    if case not in RULES:
        raise ValueError("unregistered Iceberg short case")
    value = 99 if case == "data-counter-mismatch" else 42
    return f"Retained source rule: {RULES[case]}.\n\n{request_text(value)}\n\n{DECISION_QUERY}"


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

    # R19 already checks the detached official source, full source bytes,
    # registry, exact Qwen profile, and tokenizer-file identity.
    r19.build_registration(source_root, tokenizer_root, profile=profile, tokenizer=tokenizer)
    requests: list[dict[str, object]] = []
    prompts: dict[str, str] = {}
    for case in CASE_ORDER:
        rule = RULES[case]
        prompt = decision_user(case)
        prompts[case] = prompt
        payload = _request_payload(profile, prompt)
        messages = cast(list[dict[str, str]], payload["messages"])
        measured = measure_chat_geometry(
            tokenizer,
            messages,
            enable_thinking=False,
            evidence=f"Retained source rule: {rule}.",
            query=DECISION_QUERY,
        )
        measured_count = measured["rendered_input_tokens"]
        if (
            type(measured_count) is not int
            or measured["span_status"] != "unique_later_query"
            or measured_count + profile.max_output_tokens > 32768
        ):
            raise ValueError("R20 Iceberg S2 chat geometry invalid")
        requests.append(
            {
                "case": case,
                "prompt_sha256": _sha(prompt.encode()),
                "request_sha256": _sha(_canonical(payload)),
                "local_template_geometry": measured,
            }
        )
    if prompts["data-counter-match"].replace("counter=data", "counter=<counter>") != prompts[
        "file-counter-match"
    ].replace("counter=file", "counter=<counter>"):
        raise ValueError("A/B prompts differ outside the rule counter")
    if prompts["data-counter-match"].replace("delete value 42", "delete value <value>") != prompts[
        "data-counter-mismatch"
    ].replace("delete value 99", "delete value <value>"):
        raise ValueError("A/C prompts differ outside the delete value")
    if prompts["data-counter-match"].replace(RULES["data-counter-match"], "<rule>") != prompts[
        "unknown-diagnostic"
    ].replace(RULES["unknown-diagnostic"], "<rule>"):
        raise ValueError("A/D prompts differ outside the retained rule")
    total_input = sum(
        cast(int, cast(dict[str, object], item["local_template_geometry"])["rendered_input_tokens"])
        for item in requests
    )
    return {
        "schema_version": 1,
        "scope": "r20-iceberg-s2-only-feasibility",
        "interpretation": "short rule application only; no long-source or parent qualification",
        "source_revision": SOURCE_REVISION,
        "source_sha256": SOURCE_SHA256,
        "registry_sha256": REGISTRY_SHA256,
        "r18_geometry_sha256": R18_GEOMETRY_SHA256,
        "fixed_request_sha256": _sha(request_text(42).encode()),
        "mismatch_request_sha256": _sha(request_text(99).encode()),
        "profile_sha256": profile.profile_hash,
        "tokenizer_manifest_sha256": canary.TOKENIZER_MANIFEST_SHA256,
        "case_order": list(CASE_ORDER),
        "target_call_cap": 4,
        "auxiliary_call_cap": 0,
        "local_input_tokens": total_input,
        "requested_output_tokens": 4 * profile.max_output_tokens,
        "local_input_plus_requested_ceiling": total_input + 4 * profile.max_output_tokens,
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
        raise ValueError("R20 short registration differs from generated material")
    print(
        json.dumps(
            {"status": "registered", "registration_sha256": _sha(REGISTRATION.read_bytes())}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
