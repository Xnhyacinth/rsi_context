#!/usr/bin/env python3
"""Guarded Siflow screen for four short Iceberg S2 rule applications."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import r15_exact_profile_canary as canary  # noqa: E402
import r15_pep_paid_runner as journal_tools  # noqa: E402
import r20_iceberg_short_offline as short  # noqa: E402

from rsicontext.analysis.chat_geometry import ChatTokenizer  # noqa: E402
from rsicontext.analysis.iceberg_short_private_r20 import (  # noqa: E402
    ORACLE_SHA256,
    verified_oracle,
)
from rsicontext.analysis.otel_siflow_pilot import _Worker  # noqa: E402
from rsicontext.eval.openai_compatible import Transport, _urlopen_transport  # noqa: E402
from rsicontext.experiment.api import (  # noqa: E402
    APIProfile,
    ResolvedAPIEndpoint,
    resolve_api_endpoint,
)
from rsicontext.experiment.offline_provenance import (  # noqa: E402
    producer_attestation,
    require_clean_producer,
    require_stable_attestation,
)
from rsicontext.lifecycle.material_iceberg_row_scan import (  # noqa: E402
    SOURCE_REVISION,
    SOURCE_SHA256,
)

_LAUNCH_REL = "configs/r20_iceberg_short_paid_launch_v2.json"
_LAUNCH = ROOT / _LAUNCH_REL
_REGISTRATION_REL = "configs/r20_iceberg_short_registration_v1.json"
_BOUND_FILES = (
    "scripts/r20_iceberg_short_paid_runner.py",
    "scripts/r20_iceberg_short_offline.py",
    "scripts/r19_iceberg_short_offline.py",
    "scripts/audit_r18_iceberg_geometry.py",
    "scripts/r15_exact_profile_canary.py",
    "scripts/r15_pep_paid_runner.py",
    "src/rsicontext/analysis/chat_geometry.py",
    "src/rsicontext/analysis/iceberg_short_private_r20.py",
    "src/rsicontext/analysis/otel_siflow_pilot.py",
    "src/rsicontext/eval/openai_compatible.py",
    "src/rsicontext/experiment/api.py",
    "src/rsicontext/experiment/offline_provenance.py",
    "src/rsicontext/lifecycle/material_iceberg_row_scan.py",
    "src/rsicontext/registry/tokenizer.py",
    "configs/r15_siflow_fixed_reader_profile_v1.json",
    "configs/registry.json",
    "docs/reviews/r18-iceberg-geometry.json",
    "uv.lock",
)
_PRODUCER_FILES = tuple(Path(name) for name in (*_BOUND_FILES, _REGISTRATION_REL, _LAUNCH_REL))


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _committed_bytes(relative: str) -> bytes:
    return subprocess.run(  # nosec B603, B607
        ["git", "-C", str(ROOT), "show", f"HEAD:{relative}"],
        check=True,
        capture_output=True,
        timeout=10,
    ).stdout


def _read_launch() -> tuple[dict[str, object], str]:
    raw = _LAUNCH.read_bytes()
    if raw != _committed_bytes(_LAUNCH_REL):
        raise ValueError("R20 short launch differs from committed HEAD")
    value = json.loads(raw)
    required = {
        "schema_version", "scope", "live_enabled", "registration_sha256", "bound_file_sha256",
        "registry_sha256", "source_revision", "source_sha256", "r18_geometry_sha256",
        "private_oracle_sha256",
        "canary_registration_sha256", "endpoint_sha256", "profile_sha256",
        "tokenizer_manifest_sha256", "task_call_cap", "task_local_plus_requested_ceiling",
        "canary_call_cap", "canary_local_input_tokens", "canary_requested_output_tokens",
        "global_call_cap", "global_local_plus_requested_ceiling", "auxiliary_call_cap",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value["schema_version"] != 2
        or value["scope"] != "r20-iceberg-short-paid-feasibility-v2"
        or value["live_enabled"] is not True
    ):
        raise ValueError("R20 short launch schema or scope differs")
    registration_raw = short.REGISTRATION.read_bytes()
    registered = json.loads(registration_raw)
    if not isinstance(registered, dict):
        raise ValueError("R20 short registration is invalid")
    task_ceiling = registered.get("local_input_plus_requested_ceiling")
    if type(task_ceiling) is not int:
        raise ValueError("R20 short registration budget is invalid")
    if (
        registration_raw != _committed_bytes(_REGISTRATION_REL)
        or value["registration_sha256"] != _sha(registration_raw)
    ):
        raise ValueError("R20 short registration differs from committed launch")
    bound = value["bound_file_sha256"]
    if not isinstance(bound, dict) or set(bound) != set(_BOUND_FILES):
        raise ValueError("R20 short bound producer set differs")
    for relative in _BOUND_FILES:
        current = (ROOT / relative).read_bytes()
        if current != _committed_bytes(relative) or bound[relative] != _sha(current):
            raise ValueError(f"R20 short producer differs from launch: {relative}")
    if (
        value["registry_sha256"] != short.REGISTRY_SHA256
        or value["source_revision"] != SOURCE_REVISION
        or value["source_sha256"] != SOURCE_SHA256
        or value["r18_geometry_sha256"] != short.R18_GEOMETRY_SHA256
        or value["private_oracle_sha256"] != ORACLE_SHA256
        or value["canary_registration_sha256"] != canary.registration_sha256()
        or value["endpoint_sha256"] != _sha(canary.ENDPOINT.encode())
        or value["profile_sha256"] != canary.PROFILE_SHA256
        or value["tokenizer_manifest_sha256"] != canary.TOKENIZER_MANIFEST_SHA256
        or value["task_call_cap"] != 4
        or value["task_local_plus_requested_ceiling"] != task_ceiling
        or value["canary_call_cap"] != 2
        or value["canary_local_input_tokens"] != canary.EXPECTED_INPUT_TOKENS
        or value["canary_requested_output_tokens"] != 2048
        or value["global_call_cap"] != 6
        or value["global_local_plus_requested_ceiling"]
        != task_ceiling + 2 * (canary.EXPECTED_INPUT_TOKENS + 2048)
        or value["auxiliary_call_cap"] != 0
    ):
        raise ValueError("R20 short launch identity or budget differs")
    return value, _sha(raw)


def _task_block(
    *,
    source_root: Path,
    profile: APIProfile,
    endpoint: ResolvedAPIEndpoint,
    registration: dict[str, object],
    journal: journal_tools._JournalTransport,
    synthetic: bool,
) -> dict[str, object]:
    oracle = verified_oracle()
    requested = registration.get("requests")
    if not isinstance(requested, list) or len(requested) != len(short.CASE_ORDER):
        raise ValueError("R20 short registration lacks four requests")
    registered: dict[str, dict[str, object]] = {}
    for case, item in zip(short.CASE_ORDER, requested, strict=True):
        if not isinstance(item, dict) or item.get("case") != case:
            raise ValueError("R20 short task request order differs")
        digest = item.get("prompt_sha256")
        if not isinstance(digest, str) or digest in registered:
            raise ValueError("R20 short prompt registration is invalid")
        registered[digest] = item
    if (
        _sha(short.request_text(42).encode()) != registration["fixed_request_sha256"]
        or _sha(short.request_text(99).encode()) != registration["mismatch_request_sha256"]
    ):
        raise ValueError("R20 short S2 request changed before dispatch")
    active_case = ""

    def preflight(prompt: str) -> dict[str, object]:
        item = registered.get(_sha(prompt.encode()))
        if item is None or item["case"] != active_case:
            raise ValueError("R20 short worker prompt unregistered or out of order")
        return {
            "stage": active_case,
            "prompt_sha256": item["prompt_sha256"],
            "request_sha256": item["request_sha256"],
            "local_template_geometry": item["local_template_geometry"],
        }

    worker = _Worker(profile, endpoint, preflight, journal)
    before = journal.usage_summary()
    cases: list[dict[str, object]] = []
    failure_type: str | None = None
    wrong_seen = False
    for case in short.CASE_ORDER:
        active_case = case
        try:
            reply = worker(short.decision_user(case))
        except Exception as exc:
            failure_type = type(exc).__name__
            break
        normalized = reply.strip()
        valid_format = normalized in set(oracle.values())
        correct = normalized == oracle[case] if case in oracle else None
        cases.append(
            {
                "case": case,
                "reply": reply,
                "normalized_plan": normalized if valid_format else None,
                "valid_format": valid_format,
                "correct": correct,
            }
        )
        if not valid_format:
            failure_type = "InvalidReplyFormat"
            break
        if correct is False:
            wrong_seen = True
    usage = {
        key: journal.usage_summary()[key] - before[key]
        for key in ("input_tokens", "output_tokens", "unknown_usage_attempts")
    }
    completed = failure_type is None and not worker.failed and len(cases) == 4
    return {
        "schema_version": 1,
        "scope": "r20-iceberg-s2-only-feasibility",
        "status": "completed-panel" if completed else "stopped-on-task-failure",
        "task_feasible": completed and not wrong_seen,
        "cases": cases,
        "attempts": worker.attempts,
        "worker_attempt_count": len(worker.attempts),
        "provider_usage_total": None if synthetic else usage,
        "synthetic_usage_total": usage if synthetic else None,
        "failure_type": failure_type,
        "qualified_parent": False,
    }


def run_guarded(
    *,
    source_root: Path,
    tokenizer_path: Path,
    run_dir: Path,
    transport_override: Transport | None = None,
) -> dict[str, object]:
    """Reserve evidence, authenticate all inputs, then issue at most four requests."""

    journal_tools._private_dir(run_dir)
    journal_tools._write_json(
        run_dir / "reservation.json", {"schema_version": 1, "status": "reserved"}
    )
    journal_tools._reserve_journal(run_dir / "attempts.jsonl")
    synthetic = transport_override is not None
    result: dict[str, object] = {
        "schema_version": 1,
        "scope": "r20-iceberg-short-paid-feasibility-v2",
        "mode": "injected-test" if synthetic else "live-siflow",
        "status": "refused",
        "provider_block_valid": False,
        "task_feasible": None,
        "qualified_parent": False,
        "task_provider_usage_total": None,
        "pre_canary_provider_usage": None,
        "post_canary_provider_usage": None,
    }
    journal: journal_tools._JournalTransport | None = None
    try:
        launch, launch_sha = _read_launch()
        if not synthetic and not launch["live_enabled"]:
            raise ValueError("R20 live execution awaits independent review")
        profile = canary._profile()
        tokenizer: ChatTokenizer = canary._tokenizer(tokenizer_path)
        registration = json.loads(short.REGISTRATION.read_bytes())
        verified_oracle()
        if (
            not isinstance(registration, dict)
            or registration
            != short.build_registration(
                source_root, tokenizer_path, profile=profile, tokenizer=tokenizer
            )
            or registration["local_input_plus_requested_ceiling"]
            != launch["task_local_plus_requested_ceiling"]
        ):
            raise ValueError("R20 short material or API request registration drifted")
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
                "launch_sha256": launch_sha,
                "registration_sha256": _sha(short.REGISTRATION.read_bytes()),
                "registry_sha256": short.REGISTRY_SHA256,
                "source_revision": SOURCE_REVISION,
                "source_sha256": SOURCE_SHA256,
                "fixed_request_sha256": registration["fixed_request_sha256"],
                "r18_geometry_sha256": short.R18_GEOMETRY_SHA256,
                "private_oracle_sha256": ORACLE_SHA256,
                "tokenizer_manifest_sha256": canary.TOKENIZER_MANIFEST_SHA256,
                "profile_sha256": profile.profile_hash,
                "endpoint_sha256": launch["endpoint_sha256"],
                "producer_attestation": before,
                "target_call_cap": 4,
                "global_call_cap": 6,
                "global_local_plus_requested_ceiling": launch[
                    "global_local_plus_requested_ceiling"
                ],
                "auxiliary_call_cap": 0,
            },
        )
        journal_tools._sync_directory(run_dir)
        requests = cast(list[dict[str, object]], registration["requests"])
        base = transport_override if transport_override is not None else _urlopen_transport
        journal = journal_tools._JournalTransport(
            base=base,
            journal_path=run_dir / "attempts.jsonl",
            geometry={"registered_requests": {str(r["prompt_sha256"]): r for r in requests}},
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
            usage_before = journal.usage_summary()
            task = _task_block(
                source_root=source_root,
                profile=profile,
                endpoint=endpoint,
                registration=registration,
                journal=journal,
                synthetic=synthetic,
            )
            journal_tools._write_json(run_dir / "task.json", task)
            observed_usage = {
                key: journal.usage_summary()[key] - usage_before[key]
                for key in ("input_tokens", "output_tokens", "unknown_usage_attempts")
            }
            if (
                task["worker_attempt_count"] != journal.task_attempts
                or (task["synthetic_usage_total"] if synthetic else task["provider_usage_total"])
                != observed_usage
            ):
                raise RuntimeError("R20 short worker calls or usage differ from journal")
            result["task_provider_usage_total"] = None if synthetic else observed_usage
            result["task_feasible"] = task["task_feasible"]
            if observed_usage["unknown_usage_attempts"] != 0:
                result["status"] = "usage-unverified"
            elif task["status"] != "completed-panel":
                result["status"] = "task-failed"
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
                    "completed-synthetic-screen"
                    if synthetic else "completed-paid-screen"
                ) if post.get("status") == "passed" else "post-canary-failed"
                if result["status"] in {
                    "completed-synthetic-screen", "completed-paid-screen"
                }:
                    if (
                        journal.task_attempts != 4
                        or journal.canary_attempts != 2
                        or journal.attempts != 6
                        or journal.planned_tokens != launch["global_local_plus_requested_ceiling"]
                    ):
                        raise RuntimeError("R20 short completed block lacks registered attempts")
                    _read_launch()
                    if registration != short.build_registration(
                        source_root, tokenizer_path, profile=profile, tokenizer=tokenizer
                    ):
                        raise RuntimeError("R20 short source or request changed during block")
                    after = producer_attestation(
                        ROOT,
                        _PRODUCER_FILES,
                        package_names=("transformers", "tokenizers", "jinja2"),
                    )
                    require_stable_attestation(before, after)
        result["provider_block_valid"] = (
            result["status"] == "completed-paid-screen" and not synthetic
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
        source_root=args.source_root,
        tokenizer_path=args.tokenizer_path,
        run_dir=args.run_dir,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "provider_block_valid": result["provider_block_valid"],
                "task_feasible": result["task_feasible"],
                "run_dir": str(args.run_dir),
            },
            sort_keys=True,
        )
    )
    return 0 if result["provider_block_valid"] is True and result["task_feasible"] is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
