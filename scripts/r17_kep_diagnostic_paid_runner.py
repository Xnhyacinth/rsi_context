#!/usr/bin/env python3
"""Guarded R17 KEP mechanism diagnostic; explicit execution only."""

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
import r15_k8s_reader_screen as source_check  # noqa: E402
import r15_pep_paid_runner as journal_tools  # noqa: E402

from rsicontext.analysis.chat_geometry import ChatTokenizer  # noqa: E402
from rsicontext.analysis.k8s_diagnostic_r17 import (  # noqa: E402
    CASE_ORDER,
    R16_TASK_SHA256,
    amendment_text,
    build_registration,
    interpret_reply,
    prompts,
    require_r16_observation,
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
from rsicontext.lifecycle.material_k8s_r14 import SOURCE_FILES, SOURCE_REVISION  # noqa: E402

_REGISTRATION_REL = "configs/r17_kep_diagnostic_v1.json"
_LAUNCH_REL = "configs/r17_kep_diagnostic_paid_launch_v1.json"
_REGISTRATION_PATH = ROOT / _REGISTRATION_REL
_LAUNCH_PATH = ROOT / _LAUNCH_REL
_SOURCE_FILE = "keps/sig-node/753-sidecar-containers/README.md"
_BOUND_FILES = (
    "scripts/r17_kep_diagnostic_paid_runner.py",
    "scripts/r17_kep_diagnostic_offline.py",
    "scripts/r15_exact_profile_canary.py",
    "scripts/r15_k8s_reader_screen.py",
    "scripts/r15_pep_paid_runner.py",
    "src/rsicontext/analysis/k8s_diagnostic_r17.py",
    "src/rsicontext/analysis/k8s_fixed_reader_r16.py",
    "src/rsicontext/analysis/chat_geometry.py",
    "src/rsicontext/analysis/otel_siflow_pilot.py",
    "src/rsicontext/eval/openai_compatible.py",
    "src/rsicontext/experiment/api.py",
    "src/rsicontext/experiment/offline_provenance.py",
    "src/rsicontext/lifecycle/env.py",
    "src/rsicontext/lifecycle/k8s_model_fixed_r16.py",
    "src/rsicontext/lifecycle/material_k8s_r14.py",
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
_PRODUCER_FILES = tuple(Path(value) for value in (*_BOUND_FILES, _REGISTRATION_REL, _LAUNCH_REL))


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
    """Verify launch and every bound producer byte against committed HEAD."""

    raw = _LAUNCH_PATH.read_bytes()
    if raw != _committed_bytes(_LAUNCH_REL):
        raise ValueError("R17 launch differs from committed HEAD")
    value = json.loads(raw)
    required = {
        "schema_version",
        "scope",
        "registration_sha256",
        "bound_file_sha256",
        "r16_task_sha256",
        "source_revision",
        "source_file_sha256",
        "canary_registration_sha256",
        "endpoint_sha256",
        "profile_sha256",
        "tokenizer_manifest_sha256",
        "task_call_cap",
        "task_local_plus_requested_ceiling",
        "canary_call_cap",
        "canary_local_input_tokens",
        "canary_requested_output_tokens",
        "global_call_cap",
        "global_local_plus_requested_ceiling",
        "auxiliary_call_cap",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value["schema_version"] != 1
        or value["scope"] != "r17-kep-conditioned-paid-diagnostic"
    ):
        raise ValueError("R17 launch schema or scope differs")
    registration_bytes = _REGISTRATION_PATH.read_bytes()
    if (
        registration_bytes != _committed_bytes(_REGISTRATION_REL)
        or value["registration_sha256"] != _sha(registration_bytes)
    ):
        raise ValueError("R17 registration differs from committed launch")
    bound = value["bound_file_sha256"]
    if not isinstance(bound, dict) or set(bound) != set(_BOUND_FILES):
        raise ValueError("R17 bound code list differs")
    for relative in _BOUND_FILES:
        current = (ROOT / relative).read_bytes()
        if current != _committed_bytes(relative) or bound[relative] != _sha(current):
            raise ValueError(f"R17 producer differs from committed launch: {relative}")
    if (
        value["r16_task_sha256"] != R16_TASK_SHA256
        or value["source_revision"] != SOURCE_REVISION
        or value["source_file_sha256"] != SOURCE_FILES[_SOURCE_FILE]
        or value["canary_registration_sha256"] != canary.registration_sha256()
        or value["endpoint_sha256"] != _sha(canary.ENDPOINT.encode())
        or value["profile_sha256"] != canary.PROFILE_SHA256
        or value["tokenizer_manifest_sha256"] != canary.TOKENIZER_MANIFEST_SHA256
        or value["task_call_cap"] != len(CASE_ORDER)
        or value["canary_call_cap"] != 2
        or value["canary_local_input_tokens"] != canary.EXPECTED_INPUT_TOKENS
        or value["canary_requested_output_tokens"] != 2048
        or value["global_call_cap"] != len(CASE_ORDER) + 2
        or value["auxiliary_call_cap"] != 0
    ):
        raise ValueError("R17 launch identities or call caps differ")
    task_cap = value["task_local_plus_requested_ceiling"]
    global_cap = value["global_local_plus_requested_ceiling"]
    if (
        type(task_cap) is not int
        or type(global_cap) is not int
        or task_cap != 9398
        or global_cap != task_cap + 2 * (canary.EXPECTED_INPUT_TOKENS + 2048)
    ):
        raise ValueError("R17 launch token ceiling differs")
    return value, _sha(raw)


def _task_block(
    *,
    source_root: Path,
    tokenizer: ChatTokenizer,
    profile: APIProfile,
    endpoint: ResolvedAPIEndpoint,
    registration: dict[str, object],
    journal: journal_tools._JournalTransport,
    usage_before: dict[str, int],
    synthetic: bool,
) -> dict[str, object]:
    """Dispatch four registered target calls and preserve every observed result."""

    requested = registration.get("requests")
    if not isinstance(requested, list) or len(requested) != len(CASE_ORDER):
        raise ValueError("R17 registration lacks four target requests")
    expected: dict[str, dict[str, object]] = {}
    for case, item in zip(CASE_ORDER, requested, strict=True):
        if not isinstance(item, dict) or item.get("case") != case:
            raise ValueError("R17 task request order differs")
        digest = item.get("prompt_sha256")
        if not isinstance(digest, str) or digest in expected:
            raise ValueError("R17 task prompt registration is invalid")
        expected[digest] = item
    active_case = ""

    def preflight(prompt: str) -> dict[str, object]:
        item = expected.get(_sha(prompt.encode()))
        if item is None or item.get("case") != active_case:
            raise ValueError("R17 task worker prompt is unregistered or out of order")
        return {
            "stage": active_case,
            "prompt_sha256": item["prompt_sha256"],
            "request_sha256": item["request_sha256"],
            "local_template_geometry": item["local_template_geometry"],
        }

    worker = _Worker(profile, endpoint, preflight, journal)
    rendered = prompts(amendment_text(source_root))
    cases: list[dict[str, object]] = []
    failure_type: str | None = None
    for case in CASE_ORDER:
        active_case = case
        try:
            reply = worker(rendered[case])
        except Exception as exc:
            failure_type = type(exc).__name__
            break
        observed = interpret_reply(case, reply)
        cases.append({"case": case, "reply": reply, **observed})
        if observed["valid_format"] is not True:
            failure_type = "InvalidReplyFormat"
            break
    usage = {
        key: journal.usage_summary()[key] - usage_before[key]
        for key in ("input_tokens", "output_tokens", "unknown_usage_attempts")
    }
    return {
        "schema_version": 1,
        "scope": "r17-kep-conditioned-mechanism-diagnostic",
        "status": "completed-diagnostic"
        if not worker.failed and len(cases) == len(CASE_ORDER)
        else "stopped-on-task-failure",
        "registered_case_order": list(CASE_ORDER),
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
    r16_task: Path,
    tokenizer_path: Path,
    run_dir: Path,
    transport_override: Transport | None = None,
) -> dict[str, object]:
    """Reserve private evidence, authenticate inputs, then run one bounded block."""

    journal_tools._private_dir(run_dir)
    journal_tools._write_json(
        run_dir / "reservation.json", {"schema_version": 1, "status": "reserved"}
    )
    journal_tools._reserve_journal(run_dir / "attempts.jsonl")
    synthetic = transport_override is not None
    result: dict[str, object] = {
        "schema_version": 1,
        "scope": "r17-kep-conditioned-paid-diagnostic",
        "mode": "injected-test" if synthetic else "live-siflow",
        "status": "refused",
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
        if source_check._source_identity(source_root) != {
            "revision": SOURCE_REVISION,
            "checkout": "detached-clean",
        }:
            raise ValueError("R17 KEP source identity differs from registry pin")
        observation = require_r16_observation(r16_task)
        registration = json.loads(_REGISTRATION_PATH.read_text())
        if (
            not isinstance(registration, dict)
            or registration
            != build_registration(source_root, r16_task, profile=profile, tokenizer=tokenizer)
            or registration["local_input_plus_requested_ceiling"]
            != launch["task_local_plus_requested_ceiling"]
        ):
            raise ValueError("R17 material or prompt registration drifted")
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
                "registration_sha256": _sha(_REGISTRATION_PATH.read_bytes()),
                "r16_observation": observation,
                "source_revision": SOURCE_REVISION,
                "source_file_sha256": SOURCE_FILES[_SOURCE_FILE],
                "tokenizer_manifest_sha256": canary.TOKENIZER_MANIFEST_SHA256,
                "profile_sha256": profile.profile_hash,
                "endpoint_sha256": launch["endpoint_sha256"],
                "producer_attestation": before,
                "target_call_cap": len(CASE_ORDER),
                "global_call_cap": launch["global_call_cap"],
                "global_local_plus_requested_ceiling": launch[
                    "global_local_plus_requested_ceiling"
                ],
                "auxiliary_call_cap": 0,
            },
        )
        journal_tools._sync_directory(run_dir)
        requests = cast(list[dict[str, object]], registration["requests"])
        journal_registry: dict[str, object] = {
            "registered_requests": {str(item["prompt_sha256"]): item for item in requests}
        }
        base = transport_override if transport_override is not None else _urlopen_transport
        journal = journal_tools._JournalTransport(
            base=base,
            journal_path=run_dir / "attempts.jsonl",
            geometry=journal_registry,
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
            task = _task_block(
                source_root=source_root,
                tokenizer=tokenizer,
                profile=profile,
                endpoint=endpoint,
                registration=registration,
                journal=journal,
                usage_before=before_usage,
                synthetic=synthetic,
            )
            journal_tools._write_json(run_dir / "task.json", task)
            observed_task_usage = {
                key: journal.usage_summary()[key] - before_usage[key]
                for key in ("input_tokens", "output_tokens", "unknown_usage_attempts")
            }
            if (
                task["worker_attempt_count"] != journal.task_attempts
                or (
                    task["synthetic_usage_total"] if synthetic else task["provider_usage_total"]
                )
                != observed_task_usage
            ):
                raise RuntimeError("R17 worker attempts or usage differ from journal")
            result["task_provider_usage_total"] = None if synthetic else observed_task_usage
            if observed_task_usage["unknown_usage_attempts"] != 0:
                result["status"] = "usage-unverified"
            elif task["status"] != "completed-diagnostic":
                result["status"] = "task-worker-or-format-failed"
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
                    "completed-synthetic-diagnostic" if synthetic else "completed-paid-diagnostic"
                ) if post.get("status") == "passed" else "post-canary-failed"
                if result["status"] in {
                    "completed-synthetic-diagnostic",
                    "completed-paid-diagnostic",
                }:
                    if (
                        journal.task_attempts != len(CASE_ORDER)
                        or journal.canary_attempts != 2
                        or journal.attempts != launch["global_call_cap"]
                        or journal.planned_tokens != launch["global_local_plus_requested_ceiling"]
                    ):
                        raise RuntimeError("R17 completed block lacks registered attempts")
                    _read_launch()
                    if source_check._source_identity(source_root) != {
                        "revision": SOURCE_REVISION,
                        "checkout": "detached-clean",
                    } or registration != build_registration(
                        source_root, r16_task, profile=profile, tokenizer=tokenizer
                    ):
                        raise RuntimeError("R17 source or observation changed during block")
                    after = producer_attestation(
                        ROOT,
                        _PRODUCER_FILES,
                        package_names=("transformers", "tokenizers", "jinja2"),
                    )
                    require_stable_attestation(before, after)
        result["provider_block_valid"] = (
            result["status"] == "completed-paid-diagnostic" and not synthetic
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
    parser.add_argument("--r16-task", type=Path, required=True)
    parser.add_argument("--tokenizer-path", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_guarded(
        source_root=args.source_root,
        r16_task=args.r16_task,
        tokenizer_path=args.tokenizer_path,
        run_dir=args.run_dir,
    )
    print(json.dumps({"status": result["status"], "run_dir": str(args.run_dir)}, sort_keys=True))
    return 0 if result["status"] == "completed-paid-diagnostic" else 2


if __name__ == "__main__":
    raise SystemExit(main())
