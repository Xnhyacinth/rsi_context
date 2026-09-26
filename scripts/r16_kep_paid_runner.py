#!/usr/bin/env python3
"""Guarded R16 KEP fixed-reader development screen; no implicit paid launch."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess  # nosec B404
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import r15_exact_profile_canary as canary  # noqa: E402
import r15_k8s_reader_screen as offline  # noqa: E402
import r15_pep_paid_runner as journal_tools  # noqa: E402

from rsicontext.analysis.chat_geometry import ChatTokenizer, measure_chat_geometry  # noqa: E402
from rsicontext.analysis.k8s_fixed_reader_r16 import (  # noqa: E402
    _COUNTERFACTUAL_REPLACEMENTS,
    CASE_ORDER,
    MAX_WORKER_ATTEMPTS,
    WORLD_SHA256,
    _run_screen_unverified,
    case_materials,
    enumerate_allowed_prompt_geometry,
    neutralize_both_order_rules,
    transplant_conservative_rule,
)
from rsicontext.eval.openai_compatible import Transport, _urlopen_transport  # noqa: E402
from rsicontext.experiment.api import ResolvedAPIEndpoint, resolve_api_endpoint  # noqa: E402
from rsicontext.experiment.offline_provenance import (  # noqa: E402
    producer_attestation,
    require_clean_producer,
    require_stable_attestation,
)
from rsicontext.lifecycle.k8s_model_fixed_r16 import (  # noqa: E402
    k8s_model_fixed_r16_policy_text,
)
from rsicontext.lifecycle.material_k8s_r14 import (  # noqa: E402
    SOURCE_FILES,
    SOURCE_REVISION,
    build_k8s_resource_order_sessions,
)
from rsicontext.lifecycle.spec import LifecycleInstance, canonical_instance_json  # noqa: E402

_GEOMETRY_REL = "configs/r16_kep_geometry_v1.json"
_LAUNCH_REL = "configs/r16_kep_paid_launch_v1.json"
_GEOMETRY_PATH = ROOT / _GEOMETRY_REL
_LAUNCH_PATH = ROOT / _LAUNCH_REL
_BOUND_FILES = (
    "scripts/r16_kep_paid_runner.py",
    "scripts/r15_exact_profile_canary.py",
    "scripts/r15_pep_paid_runner.py",
    "scripts/r15_k8s_reader_screen.py",
    "src/rsicontext/analysis/k8s_fixed_reader_r16.py",
    "src/rsicontext/analysis/chat_geometry.py",
    "src/rsicontext/analysis/otel_siflow_pilot.py",
    "src/rsicontext/eval/openai_compatible.py",
    "src/rsicontext/experiment/api.py",
    "src/rsicontext/experiment/offline_provenance.py",
    "src/rsicontext/lifecycle/k8s_model_fixed_r16.py",
    "src/rsicontext/lifecycle/material_k8s_r14.py",
    "src/rsicontext/lifecycle/env.py",
    "src/rsicontext/lifecycle/policy.py",
    "src/rsicontext/lifecycle/runner.py",
    "src/rsicontext/lifecycle/session_sequence.py",
    "src/rsicontext/lifecycle/spec.py",
    "src/rsicontext/lifecycle/tools.py",
    "src/rsicontext/registry/tokenizer.py",
    "configs/r15_siflow_fixed_reader_profile_v1.json",
    "configs/registry.json",
    "uv.lock",
)
_PRODUCER_FILES = tuple(Path(value) for value in (*_BOUND_FILES, _GEOMETRY_REL, _LAUNCH_REL))
_STAGES = ("source-survey", "resource-request-stage", "resource-order-change")
_SURVEY_PREFIX = (
    "Read the supplied reference before seeing the project request. "
    "Classify the effective CPU-request calculation for a regular init "
    "container when a native sidecar also runs. Return exactly "
    "formula=prefix if only earlier sidecars are added, "
    "formula=conservative if every sidecar is added regardless of "
    "order, or formula=unknown if the supplied material does not "
    "resolve this. Do not answer a scheduling decision.\n\n"
)
_BLOCK_LINES = ((774, 778), (780, 794), (835, 848))


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _committed_bytes(relative: str) -> bytes:
    return subprocess.run(  # nosec B603, B607
        ["git", "-C", str(ROOT), "show", f"HEAD:{relative}"],
        check=True,
        capture_output=True,
        timeout=10,
    ).stdout


def _task_input_cap(registry: list[dict[str, object]]) -> int:
    """Sum the largest registered prompt at each stage for each case."""

    if len(registry) != 14 or len({str(item.get("prompt_sha256")) for item in registry}) != 14:
        raise ValueError("R16 KEP geometry must register fourteen distinct prompts")
    total = 0
    for case in CASE_ORDER:
        for stage in _STAGES:
            candidates = []
            for item in registry:
                local = item.get("local_template_geometry")
                owners = item.get("cases")
                if item.get("stage") != stage or not isinstance(owners, list) or case not in owners:
                    continue
                if (
                    not isinstance(local, dict)
                    or type(local.get("rendered_input_tokens")) is not int
                ):
                    raise ValueError("KEP prompt has no exact local input count")
                candidates.append(local["rendered_input_tokens"])
            if not candidates:
                raise ValueError(f"KEP geometry misses {case}/{stage}")
            total += max(candidates)
    return total


def _exact_token_interval(
    tokenizer: ChatTokenizer,
    messages: list[dict[str, str]],
    prompt: str,
    start: int,
    end: int,
) -> list[int]:
    """Map one known prompt occurrence, even when its replacement text repeats."""

    rendered = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )
    tokenized = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, enable_thinking=False
    )
    if not isinstance(rendered, str):
        raise TypeError("KEP chat template did not render text")
    ids = tokenized.get("input_ids") if isinstance(tokenized, Mapping) else tokenized
    encoded = tokenizer(rendered, add_special_tokens=False, return_offsets_mapping=True)
    offsets = encoded["offset_mapping"]
    if not isinstance(ids, list) or list(encoded["input_ids"]) != ids or len(offsets) != len(ids):
        raise ValueError("KEP tokenizer offsets differ from rendered chat")
    trimmed = prompt.rstrip()
    if rendered.count(trimmed) != 1 or not (0 <= start < end <= len(trimmed)):
        raise ValueError("KEP rule occurrence is not unique in rendered chat")
    shift = rendered.index(trimmed)
    selected = [
        index
        for index, item in enumerate(offsets)
        if isinstance(item, Sequence)
        and len(item) == 2
        and isinstance(item[0], int)
        and isinstance(item[1], int)
        and item[1] > item[0]
        and item[0] < shift + end
        and item[1] > shift + start
    ]
    if not selected:
        raise ValueError("KEP rule occurrence has no final-chat token interval")
    return [selected[0], selected[-1] + 1]


def _rule_geometry(
    tokenizer: ChatTokenizer,
    profile_prompt: str,
    cases: tuple[tuple[str, tuple[LifecycleInstance, LifecycleInstance]], ...],
    registry: list[dict[str, object]],
    intervention: dict[str, object],
    counterfactual_intervention: dict[str, object],
    original_source: str,
) -> list[dict[str, object]]:
    """Locate three registered rule spans in each exact survey chat."""

    source_raw = original_source.split("\n", 1)[1].encode()
    source_lines = source_raw.splitlines(keepends=True)
    original_blocks = [b"".join(source_lines[start - 1 : end]) for start, end in _BLOCK_LINES]
    output: list[dict[str, object]] = []
    for name, pair in cases:
        source = pair[0].stages[0].documents[0].text
        prompt = _SURVEY_PREFIX + source
        matching = [
            entry
            for entry in registry
            if entry["stage"] == "source-survey"
            and entry["prompt_sha256"] == _sha(prompt.encode())
            and entry["cases"] == [name]
        ]
        if len(matching) != 1:
            raise ValueError("KEP survey prompt differs from registered policy prompt")
        registered_local = matching[0].get("local_template_geometry")
        if not isinstance(registered_local, dict):
            raise ValueError("KEP survey request lacks local token geometry")
        messages = [
            {"role": "system", "content": profile_prompt},
            {"role": "user", "content": prompt},
        ]
        blocks: list[dict[str, object]] = []
        cursor = 0
        for index, original in enumerate(original_blocks):
            if name == "full-source" or (name == "both-order-rules-neutralized" and index == 0):
                status = "intact"
                evidence = original.decode()
            elif name == "both-order-rules-neutralized":
                status = "explicit-rule-removed"
                evidence = (
                    "[Ordered-prefix calculation withheld for this diagnostic arm.]\n"
                    + "\n" * (original.count(b"\n") - 1)
                )
            elif name == "same-identity-conservative-rule":
                status = "constructed-conservative-replacement"
                evidence = _COUNTERFACTUAL_REPLACEMENTS[index]
            else:
                status = "source-withheld" if name == "source-free" else "identity-only"
                evidence = None
            interval = None
            if evidence is not None:
                occurrence = source.find(evidence, cursor)
                if occurrence < 0:
                    raise ValueError("KEP visible rule or replacement differs from material")
                cursor = occurrence + len(evidence)
                interval = _exact_token_interval(
                    tokenizer,
                    messages,
                    prompt,
                    len(_SURVEY_PREFIX) + occurrence,
                    len(_SURVEY_PREFIX) + cursor,
                )
                measured = measure_chat_geometry(tokenizer, messages, enable_thinking=False)
                if measured["rendered_input_tokens"] != registered_local["rendered_input_tokens"]:
                    raise ValueError("KEP decisive rule has no exact final-chat token span")
            blocks.append(
                {
                    "line_start": _BLOCK_LINES[index][0],
                    "line_end": _BLOCK_LINES[index][1],
                    "original_sha256": _sha(original),
                    "status": status,
                    "visible_span_sha256": _sha(evidence.encode())
                    if evidence is not None
                    else None,
                    "final_chat_token_interval": interval,
                }
            )
        output.append(
            {
                "case": name,
                "survey_prompt_sha256": matching[0]["prompt_sha256"],
                "survey_input_tokens": registered_local["rendered_input_tokens"],
                "blocks": blocks,
                "later_question_relation": (
                    "separate model call; no within-chat source-to-question distance"
                ),
            }
        )
    spans = intervention.get("spans")
    if not isinstance(spans, list) or [item["original_sha256"] for item in spans] != [
        _sha(block) for block in original_blocks[1:]
    ]:
        raise ValueError("KEP source block hashes differ from intervention ledger")
    counterfactual_spans = counterfactual_intervention.get("spans")
    if not isinstance(counterfactual_spans, list) or [
        item["original_sha256"] for item in counterfactual_spans
    ] != [_sha(block) for block in original_blocks]:
        raise ValueError("KEP counterfactual block hashes differ from source")
    return output


def _build_geometry(source_root: Path, tokenizer: ChatTokenizer) -> dict[str, object]:
    profile = canary._profile()
    source_identity = offline._source_identity(source_root)
    if source_identity != {"revision": SOURCE_REVISION, "checkout": "detached-clean"}:
        raise ValueError("KEP source identity differs from pin")
    sessions = build_k8s_resource_order_sessions(source_root)
    base_world = [_sha(canonical_instance_json(world).encode()) for world in sessions]
    if tuple(base_world) != WORLD_SHA256:
        raise ValueError("KEP private world differs from pin")
    cases = case_materials(sessions)
    case_records = [
        {
            "case": name,
            "source_material_sha256": _sha(pair[0].stages[0].documents[0].text.encode()),
            "world_sha256": [_sha(canonical_instance_json(world).encode()) for world in pair],
        }
        for name, pair in cases
    ]
    registry = enumerate_allowed_prompt_geometry(source_root, profile=profile, tokenizer=tokenizer)
    source_text = cases[0][1][0].stages[0].documents[0].text
    _changed, intervention = neutralize_both_order_rules(source_text)
    _counterfactual, counterfactual_intervention = transplant_conservative_rule(source_text)
    if profile.system_prompt is None:
        raise ValueError("KEP profile lacks system prompt")
    rule_geometry = _rule_geometry(
        tokenizer,
        profile.system_prompt,
        cases,
        registry,
        intervention,
        counterfactual_intervention,
        source_text,
    )
    input_cap = _task_input_cap(registry)
    return {
        "schema_version": 1,
        "scope": "r16-kep-fixed-reader-development",
        "source_identity": source_identity,
        "source_file_sha256": SOURCE_FILES["keps/sig-node/753-sidecar-containers/README.md"],
        "base_world_sha256": base_world,
        "case_materials": case_records,
        "source_intervention": intervention,
        "counterfactual_intervention": counterfactual_intervention,
        "source_rule_geometry": rule_geometry,
        "later_prompt_geometry": [
            {
                "stage": item["stage"],
                "prompt_sha256": item["prompt_sha256"],
                "retained_formula_span_tokens": cast(
                    dict[str, object], item["local_template_geometry"]
                )["evidence_span_tokens"],
                "query_span_tokens": cast(dict[str, object], item["local_template_geometry"])[
                    "query_span_tokens"
                ],
                "retained_formula_to_query_tokens": cast(
                    dict[str, object], item["local_template_geometry"]
                )["evidence_to_query_tokens"],
                "evidence_kind": "model-retained formula, not original source text",
            }
            for item in registry
            if item["stage"] != "source-survey"
        ],
        "policy_sha256": _sha(k8s_model_fixed_r16_policy_text().encode()),
        "profile_sha256": profile.profile_hash,
        "profile_file_sha256": _sha(canary.PROFILE_PATH.read_bytes()),
        "tokenizer_manifest_sha256": canary.TOKENIZER_MANIFEST_SHA256,
        "tokenizer_runtime": {"transformers": "5.15.0", "tokenizers": "0.22.2", "jinja2": "3.1.6"},
        "registered_requests": registry,
        "task_call_cap": MAX_WORKER_ATTEMPTS,
        "task_local_worst_case_input_tokens": input_cap,
        "task_requested_output_ceiling": MAX_WORKER_ATTEMPTS * profile.max_output_tokens,
        "task_local_plus_requested_ceiling": input_cap
        + MAX_WORKER_ATTEMPTS * profile.max_output_tokens,
    }


def _read_launch() -> tuple[dict[str, object], str]:
    raw = _LAUNCH_PATH.read_bytes()
    if raw != _committed_bytes(_LAUNCH_REL):
        raise ValueError("KEP launch differs from committed HEAD")
    value = json.loads(raw)
    required = {
        "schema_version",
        "scope",
        "geometry_sha256",
        "bound_file_sha256",
        "canary_registration_sha256",
        "endpoint_sha256",
        "profile_sha256",
        "task_call_cap",
        "task_local_plus_requested_ceiling",
        "canary_call_cap",
        "canary_local_input_tokens",
        "canary_requested_output_tokens",
        "global_call_cap",
        "global_local_plus_requested_ceiling",
        "auxiliary_call_cap",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("KEP launch schema differs from frozen contract")
    if value["schema_version"] != 1 or value["scope"] != "r16-kep-paid-development":
        raise ValueError("KEP launch scope differs")
    geometry_bytes = _GEOMETRY_PATH.read_bytes()
    if geometry_bytes != _committed_bytes(_GEOMETRY_REL) or value["geometry_sha256"] != _sha(
        geometry_bytes
    ):
        raise ValueError("KEP geometry differs from committed launch")
    bound = value["bound_file_sha256"]
    if not isinstance(bound, dict) or set(bound) != set(_BOUND_FILES):
        raise ValueError("KEP bound code list differs")
    for relative in _BOUND_FILES:
        current = (ROOT / relative).read_bytes()
        if current != _committed_bytes(relative) or bound[relative] != _sha(current):
            raise ValueError(f"KEP producer differs from committed launch: {relative}")
    if (
        value["canary_registration_sha256"] != canary.registration_sha256()
        or value["endpoint_sha256"] != _sha(canary.ENDPOINT.encode())
        or value["profile_sha256"] != canary.PROFILE_SHA256
        or value["task_call_cap"] != MAX_WORKER_ATTEMPTS
        or value["canary_call_cap"] != 2
        or value["canary_local_input_tokens"] != canary.EXPECTED_INPUT_TOKENS
        or value["canary_requested_output_tokens"] != 2048
        or value["global_call_cap"] != MAX_WORKER_ATTEMPTS + 2
        or value["auxiliary_call_cap"] != 0
    ):
        raise ValueError("KEP launch identity or call caps differ")
    task_cap = value["task_local_plus_requested_ceiling"]
    global_cap = value["global_local_plus_requested_ceiling"]
    if (
        type(task_cap) is not int
        or type(global_cap) is not int
        or task_cap <= 0
        or global_cap != task_cap + 2 * (canary.EXPECTED_INPUT_TOKENS + 2048)
    ):
        raise ValueError("KEP launch requested-token ceiling differs")
    return value, _sha(raw)


def run_guarded(
    *,
    source_root: Path,
    tokenizer_path: Path,
    run_dir: Path,
    transport_override: Transport | None = None,
) -> dict[str, object]:
    """Reserve private evidence before admission, credential lookup or transport."""

    journal_tools._private_dir(run_dir)
    journal_tools._write_json(
        run_dir / "reservation.json", {"schema_version": 1, "status": "reserved"}
    )
    journal_tools._reserve_journal(run_dir / "attempts.jsonl")
    synthetic = transport_override is not None
    result: dict[str, object] = {
        "schema_version": 1,
        "scope": "r16-kep-paid-development",
        "mode": "injected-test" if synthetic else "live-siflow",
        "status": "refused",
        "live_ready": False,
        "provider_block_valid": False,
        "qualified_parent": False,
        "task_provider_usage_total": None,
        "pre_canary_provider_usage": None,
        "post_canary_provider_usage": None,
    }
    journal: journal_tools._JournalTransport | None = None
    try:
        launch, launch_sha = _read_launch()
        profile = canary._profile()
        tokenizer = canary._tokenizer(tokenizer_path)
        geometry = json.loads(_GEOMETRY_PATH.read_text())
        if not isinstance(geometry, dict) or geometry != _build_geometry(source_root, tokenizer):
            raise ValueError("KEP source, world, tokenizer or prompt geometry differs from pin")
        if (
            geometry["task_local_plus_requested_ceiling"]
            != launch["task_local_plus_requested_ceiling"]
        ):
            raise ValueError("KEP task requested-token ceiling differs from geometry")
        before = producer_attestation(
            ROOT, _PRODUCER_FILES, package_names=("transformers", "tokenizers", "jinja2")
        )
        require_clean_producer(before)
        configured = os.environ.get(profile.endpoint_env)
        if configured is not None and configured != canary.ENDPOINT:
            raise ValueError("configured endpoint differs from pin")
        endpoint = (
            ResolvedAPIEndpoint(endpoint=canary.ENDPOINT, api_key="synthetic-test-key")
            if synthetic
            else resolve_api_endpoint(profile, endpoint=canary.ENDPOINT)
        )
        if endpoint.endpoint != canary.ENDPOINT:
            raise ValueError("resolved endpoint differs from pin")
        journal_tools._write_json(
            run_dir / "identity.json",
            {
                "launch_manifest_sha256": launch_sha,
                "geometry_sha256": _sha(_GEOMETRY_PATH.read_bytes()),
                "canary_registration_sha256": canary.registration_sha256(),
                "source_revision": SOURCE_REVISION,
                "tokenizer_manifest_sha256": canary.TOKENIZER_MANIFEST_SHA256,
                "profile_sha256": profile.profile_hash,
                "endpoint_sha256": launch["endpoint_sha256"],
                "producer_attestation": before,
                "task_call_cap": MAX_WORKER_ATTEMPTS,
                "global_call_cap": launch["global_call_cap"],
                "global_local_plus_requested_ceiling": launch[
                    "global_local_plus_requested_ceiling"
                ],
                "auxiliary_call_cap": 0,
            },
        )
        journal_tools._sync_directory(run_dir)
        registry = cast(list[dict[str, object]], geometry["registered_requests"])
        journal_geometry: dict[str, object] = {
            "registered_requests": {str(item["prompt_sha256"]): item for item in registry}
        }
        base = transport_override if transport_override is not None else _urlopen_transport
        journal = journal_tools._JournalTransport(
            base=base,
            journal_path=run_dir / "attempts.jsonl",
            geometry=journal_geometry,
            manifest=launch,
        )
        pre = canary.run_canary(
            profile=profile,
            endpoint=endpoint,
            tokenizer=tokenizer,
            transport=journal,
            synthetic=synthetic,
        )
        journal_tools._write_json(run_dir / "pre_canary.json", pre)
        result["pre_canary_provider_usage"] = None if synthetic else pre.get("provider_usage_total")
        if pre.get("status") != "passed":
            result["status"] = "pre-canary-failed"
        else:
            journal.phase = "task"
            before_usage = journal.usage_summary()
            task = _run_screen_unverified(
                source_root,
                profile=profile,
                endpoint=endpoint,
                tokenizer=tokenizer,
                transport=journal,
                geometry_registry=registry,
                synthetic=synthetic,
            )
            journal_tools._write_json(run_dir / "task.json", task)
            result["task_status"] = task["status"]
            observed = {
                key: journal.usage_summary()[key] - before_usage[key]
                for key in ("input_tokens", "output_tokens", "unknown_usage_attempts")
            }
            if (
                task["worker_attempt_count"] != journal.task_attempts
                or (task["synthetic_usage_total"] if synthetic else task["provider_usage_total"])
                != observed
            ):
                raise RuntimeError("KEP worker attempts or usage differ from transport journal")
            result["task_provider_usage_total"] = None if synthetic else observed
            if task["status"] == "stopped-on-worker-failure":
                result["status"] = "task-worker-failed"
            elif journal.unknown_usage_attempts:
                result["status"] = "usage-unverified"
            elif task["status"] != (
                "completed-offline-screen" if synthetic else "completed-development-screen"
            ):
                result["status"] = "stopped-on-full-task-failure"
            else:
                journal.phase = "post-canary"
                post = canary.run_canary(
                    profile=profile,
                    endpoint=endpoint,
                    tokenizer=tokenizer,
                    transport=journal,
                    synthetic=synthetic,
                )
                journal_tools._write_json(run_dir / "post_canary.json", post)
                result["post_canary_provider_usage"] = (
                    None if synthetic else post.get("provider_usage_total")
                )
                result["status"] = (
                    ("completed-synthetic-screen" if synthetic else "completed-development-screen")
                    if post.get("status") == "passed"
                    else "post-canary-failed"
                )
                if result["status"] in {
                    "completed-synthetic-screen",
                    "completed-development-screen",
                }:
                    if journal.task_attempts != MAX_WORKER_ATTEMPTS or journal.canary_attempts != 2:
                        raise RuntimeError("KEP completed block lacks registered calls")
                    _read_launch()
                    if geometry != _build_geometry(source_root, tokenizer):
                        raise RuntimeError("KEP materials changed during task block")
                    after = producer_attestation(
                        ROOT,
                        _PRODUCER_FILES,
                        package_names=("transformers", "tokenizers", "jinja2"),
                    )
                    require_stable_attestation(before, after)
        result["provider_block_valid"] = (
            result["status"] == "completed-development-screen" and not synthetic
        )
    except Exception as exc:
        result["status"] = "refused-or-interrupted"
        result["failure_type"] = type(exc).__name__
    finally:
        if journal is not None:
            result["attempted_http_calls"] = journal.attempts
            result["task_http_calls"] = journal.task_attempts
            result["canary_http_calls"] = journal.canary_attempts
            result["local_plus_requested_tokens"] = journal.planned_tokens
            result["all_provider_usage"] = None if synthetic else journal.usage_summary()
            result["synthetic_usage"] = journal.usage_summary() if synthetic else None
        journal_tools._write_json(run_dir / "final.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--tokenizer-path", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_guarded(
        source_root=args.source_root, tokenizer_path=args.tokenizer_path, run_dir=args.run_dir
    )
    print(json.dumps({"status": result["status"], "run_dir": str(args.run_dir)}, sort_keys=True))
    return 0 if result["status"] == "completed-development-screen" else 2


if __name__ == "__main__":
    raise SystemExit(main())
