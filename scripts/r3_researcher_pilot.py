#!/usr/bin/env python3
"""Fixed A-dev usability pilot for the R3 unassisted researcher channel.

This is an engineering pilot, not a scored efficacy comparison. Both draws
receive identical development feedback; neither is selected by its score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from r2a_compare import (
    READER_ENDPOINT,
    READER_MODEL,
    RESEARCHER_MODEL,
    _live_responder_factory,
    _policy_loadable,
    _researcher_unassisted_round,
    _run_arm,
)
from r3_compare import _api_profile, _canonical_sha256, _git_identity, _source_sha256

from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier
from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text
from rsicontext.security.audit import PolicyAuditor
from rsicontext.security.isolated_policy import require_isolated_policy_executor

PLANNED_ATTEMPTS = 2
RESEARCHER_MAX_OUTPUT_TOKENS = 8192
WORKER_MAX_OUTPUT_TOKENS = 2048
WORKER_REQUEST_CAP = 32
WORKER_REQUEST_CAP_PER_DRAW = 16
DEV_SOURCE = Path("artifacts/rsi-core-v1/r3-live.json")
DEFAULT_OUTPUT = Path("artifacts/rsi-core-v1/r3-researcher-pilot-v4-20260924.json")
MODELS_ENDPOINT = "https://api.siflow.cn/model-api/models"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dev_feedback(source: dict[str, Any]) -> dict[str, object]:
    dev = source["groups"]["A"]["arms"]["baseline"]["dev"]
    if dev["instance_id"] != build_research_v4_dossier().instance_id:
        raise ValueError("A-dev source instance does not match the pilot world")
    return {
        "stages": [
            "survey",
            "constraint_injection",
            "act_verify",
            "follow_up",
            "rule_change",
            "follow_up",
        ],
        "decisions": dev["decisions"],
        "failures": dev["failures"],
        "receipt_causes_sample": [
            "environment verification verdicts (pass/fail)",
            "protocol revision notices",
        ],
        "run_result": "passed" if dev["passed"] else "failed",
    }


def _available_models() -> set[str]:
    request = urllib.request.Request(
        MODELS_ENDPOINT,
        headers={"Authorization": f"Bearer {os.environ['SIFLOW_API_KEY']}"},
    )
    # MODELS_ENDPOINT is a code-owned HTTPS constant.
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
        raw = json.load(response)
    return {
        entry["id"]
        for entry in raw["data"]
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }


class WorkerRequestCap:
    """Reject requests above the configured cap before issuing HTTP."""

    def __init__(self, responder: Any, limit: int = WORKER_REQUEST_CAP) -> None:
        self.responder = responder
        self.limit = limit
        self.calls = 0
        self.usage_state = responder.usage_state
        self.channel_state = responder.channel_state

    def __call__(self, prompt: str) -> str:
        if self.calls >= self.limit:
            raise RuntimeError(f"pilot worker request cap {self.limit} reached")
        self.calls += 1
        return cast(str, self.responder(prompt))


def _researcher_readiness(record: dict[str, object]) -> str | None:
    if record.get("finish_reason") == "length":
        return "truncated"
    if record.get("finish_reason") != "stop":
        return "unverified_finish"
    if record.get("model_echo") != RESEARCHER_MODEL:
        return "researcher-model-mismatch"
    if record.get("usage_status") != "reported" or any(
        isinstance((value := record.get(field)), bool) or not isinstance(value, int) or value < 0
        for field in ("input_tokens", "output_tokens", "total_tokens")
    ):
        return "researcher-usage-unverified"
    return None


def _classify(
    policy: str, baseline: str, record: dict[str, object], run: dict[str, object] | None
) -> str:
    readiness = _researcher_readiness(record)
    if readiness is not None:
        return readiness
    candidate_audit = record.get("candidate_audit")
    if not isinstance(candidate_audit, dict) or candidate_audit.get("safe") is not True:
        return "audit-rejected"
    if record.get("candidate_loadable") is not True:
        return "invalid"
    if policy == baseline:
        return "loadable-unchanged"
    if record.get("worker_error_type"):
        return "worker-run-failed"
    if run is not None and run.get("policy_errors"):
        return "runtime-failed"
    if run is not None:
        transcript = cast(list[dict[str, object]], run.get("model_transcript", []))
        if any("request cap" in str(call.get("cause", "")) for call in transcript):
            return "budget-exhausted"
        provider_calls = cast(list[dict[str, object]], run.get("provider_usage_calls", []))
        if any(call.get("outcome") != "ok" for call in provider_calls) or any(
            call.get("ok") is False for call in transcript
        ):
            return "worker-call-failed"
        if any(call.get("model_echo") != READER_MODEL for call in provider_calls):
            return "worker-model-mismatch"
        if any(
            call.get("usage_status") != "reported"
            or any(
                isinstance((value := call.get(field)), bool)
                or not isinstance(value, int)
                or value < 0
                for field in ("prompt_tokens", "completion_tokens", "total_tokens")
            )
            for call in provider_calls
        ):
            return "worker-usage-unverified"
        if any(call.get("finish_reason") == "length" for call in provider_calls):
            return "worker-truncated"
        if any(call.get("finish_reason") != "stop" for call in provider_calls):
            return "unverified_finish"
        if run.get("model_calls") and provider_calls:
            return "changed-and-exercised"
    return "loadable-changed-unexercised"


def _worker_summary(run: dict[str, object] | None) -> dict[str, object] | None:
    if run is None:
        return None
    transcript = cast(list[dict[str, object]], run["model_transcript"])
    return {
        "instance_id": run["instance_id"],
        "passed": run["passed"],
        "decisions": run["decisions"],
        "failures": run["failures"],
        "policy_errors": run["policy_errors"],
        "model_calls": run["model_calls"],
        "model_tokens_source": run["model_tokens_source"],
        "provider_usage_calls": run["provider_usage_calls"],
        "provider_usage_totals": run["provider_usage_totals"],
        "tool_ledger": run["tool_ledger"],
        "wall_seconds": run["wall_seconds"],
        "worker_prompt_sha256": [call.get("prompt_sha256", "missing") for call in transcript],
        "worker_call_stage_ids": [call.get("stage_id", "missing") for call in transcript],
    }


def _persist_candidate(output: Path, draw_id: int, policy: str) -> dict[str, object]:
    """Save exact researcher bytes in an ignored, Python-only candidate directory."""

    if not policy:
        return {
            "policy_sha256": None,
            "policy_path": None,
            "candidate_dir": None,
            "policy_chars": 0,
        }
    candidate_dir = output.with_suffix("") / f"draw-{draw_id}"
    candidate_dir.mkdir(exist_ok=False)
    candidate_path = candidate_dir / "policy.py"
    with candidate_path.open("x", encoding="utf-8") as handle:
        handle.write(policy)
    return {
        "policy_sha256": _sha256(candidate_path.read_bytes()),
        "policy_path": str(candidate_path),
        "candidate_dir": str(candidate_dir),
        "policy_chars": len(policy),
    }


def _audit_candidate(candidate_dir: object, policy: str) -> dict[str, object]:
    if not isinstance(candidate_dir, str):
        return {
            "safe": False,
            "status": "missing-candidate",
            "memory_sha256": _sha256(policy.encode()),
            "disk_sha256": None,
            "hashes_match": False,
            "violations": [],
        }
    candidate_path = Path(candidate_dir) / "policy.py"
    auditor = PolicyAuditor()
    memory_report = auditor.audit_source(policy, filename=str(candidate_path))
    tree_report = auditor.audit_tree(candidate_dir)
    memory_sha256 = _sha256(policy.encode())
    try:
        disk_sha256 = _sha256(candidate_path.read_bytes())
    except OSError:
        disk_sha256 = None
    hashes_match = memory_sha256 == disk_sha256
    safe = memory_report.safe and tree_report.safe and hashes_match
    return {
        "safe": safe,
        "status": "passed" if safe else "rejected",
        "memory_sha256": memory_sha256,
        "disk_sha256": disk_sha256,
        "hashes_match": hashes_match,
        "files": list(tree_report.files),
        "violations": [
            {"source": source, "code": v.code, "filename": v.filename, "line": v.line}
            for source, report in (("memory", memory_report), ("tree", tree_report))
            for v in report.violations
        ],
    }


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _run_identity(baseline: str, feedback: dict[str, object]) -> dict[str, object]:
    """Freeze code, budget, models, and full A-dev material by digest."""

    identity: dict[str, object] = {
        "schema_version": 1,
        "git": _git_identity(),
        "source_sha256": _source_sha256(),
        "source_files_sha256": {
            name: _sha256((PROJECT_ROOT / name).read_bytes())
            for name in (
                "scripts/r3_researcher_pilot.py",
                "scripts/r2a_compare.py",
                "src/rsicontext/lifecycle/policy.py",
                "src/rsicontext/lifecycle/strong_model_fixed.py",
            )
        },
        "uv_lock_sha256": _sha256((PROJECT_ROOT / "uv.lock").read_bytes()),
        "configuration_sha256": {
            name: _sha256((PROJECT_ROOT / "configs" / name).read_bytes())
            for name in ("budget_v1.json", "api_profiles.json")
        },
        "models": {
            "researcher": _api_profile(RESEARCHER_MODEL),
            "worker": _api_profile(READER_MODEL),
        },
        "endpoint_sha256": _sha256(READER_ENDPOINT.encode()),
        "execution_parameters": {
            "attempts": PLANNED_ATTEMPTS,
            "researcher_max_output_tokens": RESEARCHER_MAX_OUTPUT_TOKENS,
            "researcher_max_http_attempts_per_draw": 1,
            "researcher_thinking": "disabled",
            "worker_max_output_tokens_per_request": WORKER_MAX_OUTPUT_TOKENS,
            "worker_request_cap_per_draw": WORKER_REQUEST_CAP_PER_DRAW,
            "worker_request_cap_total": WORKER_REQUEST_CAP,
            "worker_thinking": "disabled",
            "seed": 42,
            "temperature": 0.0,
            "eval_runs": 0,
        },
        "materials": {
            "a_dev_instance_id": build_research_v4_dossier().instance_id,
            "a_dev_full_sha256": _canonical_sha256(build_research_v4_dossier().to_dict()),
            "baseline_policy_sha256": _sha256(baseline.encode()),
            "feedback_sha256": _canonical_sha256(feedback),
        },
    }
    identity["identity_sha256"] = _canonical_sha256(identity)
    return identity


def _identity_still_frozen(identity: dict[str, object]) -> bool:
    return identity["git"] == _git_identity() and identity["source_sha256"] == _source_sha256()


def run(output: Path) -> dict[str, object]:
    # A researcher-authored candidate would otherwise reach load_policy and
    # PolicyHook in this credentialed evaluator process. Refuse before any
    # provider call, candidate load, or output artifact is created.
    require_isolated_policy_executor()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite pilot artifact: {output}")
    if not os.environ.get("SIFLOW_API_KEY"):
        raise RuntimeError("SIFLOW_API_KEY is required")
    available = _available_models()
    required = {READER_MODEL, RESEARCHER_MODEL}
    if not required <= available:
        raise RuntimeError(f"pilot models unavailable: {sorted(required - available)}")
    source_bytes = DEV_SOURCE.read_bytes()
    source = json.loads(source_bytes)
    feedback = _dev_feedback(source)
    baseline = strong_model_fixed_policy_text()
    run_identity = _run_identity(baseline, feedback)
    feedback_bytes = json.dumps(feedback, sort_keys=True, ensure_ascii=False).encode()
    manifest = {
        "purpose": "A-dev researcher usability only; no eval or score selection",
        "valid_update_definition": (
            "researcher stop with matching model echo and reported numeric usage; loadable, "
            "PolicyAuditor candidate directory passed, changed; at least one successful "
            "worker call with matching model echo and "
            "reported numeric usage; zero policy errors; no failed, truncated, or capped calls"
        ),
        "attempts": PLANNED_ATTEMPTS,
        "researcher_model": RESEARCHER_MODEL,
        "researcher_max_output_tokens": RESEARCHER_MAX_OUTPUT_TOKENS,
        "researcher_http_attempts_per_draw": 1,
        "researcher_thinking": "disabled",
        "worker_model": READER_MODEL,
        "worker_thinking": "disabled",
        "worker_max_output_tokens_per_request": WORKER_MAX_OUTPUT_TOKENS,
        "worker_request_cap_total": WORKER_REQUEST_CAP,
        "worker_request_cap_per_draw": WORKER_REQUEST_CAP_PER_DRAW,
        "temperature": 0.0,
        "seed": 42,
        "dev_source": str(DEV_SOURCE),
        "dev_source_sha256": _sha256(source_bytes),
        "baseline_sha256": _sha256(baseline.encode()),
        "feedback_sha256": _sha256(feedback_bytes),
    }
    responder = _live_responder_factory(enable_thinking=False)
    total_worker_requests = 0
    draws: list[dict[str, object]] = []
    result: dict[str, object] = {
        "status": "running",
        "started_at_utc": _utc_now(),
        "run_identity": run_identity,
        "manifest": manifest,
        "draws": draws,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix("").mkdir(exist_ok=False)
    output.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for draw_id in range(PLANNED_ATTEMPTS):
        if not _identity_still_frozen(run_identity):
            result["status"] = "identity-drift"
            break
        started = time.monotonic()
        try:
            policy, record = _researcher_unassisted_round(
                baseline,
                feedback,
                True,
                max_output_tokens=RESEARCHER_MAX_OUTPUT_TOKENS,
                max_attempts=1,
                backoff_seconds=0.0,
                thinking=False,
            )
        except Exception as exc:
            policy = ""
            record = {
                "round_outcome": "protocol-or-transport-error",
                "error_type": type(exc).__name__,
                "usage_status": "missing",
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "wall_seconds": round(time.monotonic() - started, 3),
            }
        candidate = _persist_candidate(output, draw_id, policy)
        candidate_audit = _audit_candidate(candidate["candidate_dir"], policy)
        record["candidate_audit"] = candidate_audit
        # Audit the exact saved bytes before load_policy can exec them. This
        # static gate is not a sandbox: live execution still needs an external
        # process/container boundary from secrets and evaluator-only data.
        loadable = candidate_audit["safe"] is True and _policy_loadable(policy)
        record["candidate_loadable"] = loadable
        changed = loadable and policy != baseline
        draw: dict[str, object] = {
            "draw_id": draw_id,
            "outcome": "worker-pending" if changed else _classify(policy, baseline, record, None),
            "loadable": loadable,
            "changed": changed,
            **candidate,
            "candidate_audit": candidate_audit,
            "researcher": record,
            "worker_run": None,
            "worker_requests_attempted": 0,
            "wall_seconds": round(time.monotonic() - started, 3),
        }
        draws.append(draw)
        output.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        if not _identity_still_frozen(run_identity):
            draw["outcome"] = "identity-drift"
            result["status"] = "identity-drift"
            output.write_text(
                json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            break
        worker_run = None
        if changed and _researcher_readiness(record) is None and candidate_audit["safe"] is True:
            draw_responder = WorkerRequestCap(responder, limit=WORKER_REQUEST_CAP_PER_DRAW)
            try:
                worker_run = _run_arm(policy, build_research_v4_dossier(), draw_responder)
            except Exception as exc:
                record["worker_error_type"] = type(exc).__name__
            total_worker_requests += draw_responder.calls
            draw["worker_requests_attempted"] = draw_responder.calls
        result["worker_requests_attempted"] = total_worker_requests
        result["worker_provider_usage_calls"] = responder.usage_state()
        output.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        draw["outcome"] = _classify(policy, baseline, record, worker_run)
        draw["worker_run"] = _worker_summary(worker_run)
        draw["wall_seconds"] = round(time.monotonic() - started, 3)
        result["worker_requests_attempted"] = total_worker_requests
        output.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if result["status"] != "identity-drift" and _identity_still_frozen(run_identity):
        result["valid_update_rate"] = {
            "numerator": sum(draw["outcome"] == "changed-and-exercised" for draw in draws),
            "denominator": PLANNED_ATTEMPTS,
        }
        result["status"] = "complete"
    else:
        result["valid_update_rate"] = None
        result["status"] = "identity-drift"
    result["worker_requests_attempted"] = total_worker_requests
    worker_calls = responder.usage_state()
    result["worker_response_reliability"] = {
        "requests": len(worker_calls),
        "finish_length": sum(call.get("finish_reason") == "length" for call in worker_calls),
        "finish_stop": sum(call.get("finish_reason") == "stop" for call in worker_calls),
        "request_or_protocol_errors": sum(call.get("outcome") != "ok" for call in worker_calls),
        "usage_missing": sum(call.get("usage_status") != "reported" for call in worker_calls),
    }
    result["completed_at_utc"] = _utc_now()
    result["git_at_end"] = _git_identity()
    result["source_sha256_at_end"] = _source_sha256()
    output.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(args.output)
    print(
        json.dumps(
            {
                "artifact": str(args.output),
                "valid_update_rate": result["valid_update_rate"],
                "worker_requests_attempted": result["worker_requests_attempted"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
