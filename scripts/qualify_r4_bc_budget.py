#!/usr/bin/env python3
"""Qualify a versioned B/C development capacity plan without model calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from rsicontext.experiment.api import APIProfile, load_api_profiles

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "configs/r4_bc_dev_budget_v2.json"
WORKER_PROFILES = ROOT / "configs/r4_siflow_qwen_worker_profile_v1.json"
RESEARCHER_PROFILES = ROOT / "configs/r4_siflow_researcher_profile_v1.json"
GROUPS = ("B", "C")


def _sha256(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"expected a regular file: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _observed_calls(source: dict[str, Any]) -> dict[str, dict[str, int]]:
    if source.get("status") != "complete" or source.get("model_api_calls") != 0:
        raise ValueError("source must be a completed zero-API offline admission")
    end = source.get("run_identity_end")
    if not isinstance(end, dict) or end.get("matches_start") is not True:
        raise ValueError("source admission identity did not match at end")
    groups = source.get("groups")
    if not isinstance(groups, dict) or set(groups) != set(GROUPS):
        raise ValueError("source admission groups differ from B/C")
    calls: dict[str, dict[str, int]] = {}
    for group in GROUPS:
        row = groups[group]
        if not isinstance(row, dict):
            raise ValueError("source admission group must be an object")
        baseline = row.get("baseline_scripted")
        candidate = row.get("synthetic_candidate")
        if not isinstance(baseline, dict) or not isinstance(candidate, dict):
            raise ValueError("source admission has no full-run call counts")
        baseline_calls = baseline.get("worker_calls")
        candidate_calls = candidate.get("worker_calls")
        if (
            type(baseline_calls) is not int
            or type(candidate_calls) is not int
            or baseline_calls < 1
            or candidate_calls < 1
        ):
            raise ValueError("source admission worker calls must be positive integers")
        calls[group] = {"baseline": baseline_calls, "candidate": candidate_calls}
    return calls


def qualify_contract(
    contract: dict[str, Any],
    source: dict[str, Any],
    *,
    source_sha256: str,
    worker_profile: APIProfile,
    researcher_profile: APIProfile,
    worker_profile_sha256: str,
    researcher_profile_sha256: str,
) -> dict[str, object]:
    """Validate matched opportunity against the prior scripted lower bound."""

    if (
        contract.get("schema_version") != 2
        or contract.get("status") != "offline_capacity_qualification_only"
    ):
        raise ValueError("expected the R4 offline capacity contract")
    if contract.get("source_admission_sha256") != source_sha256:
        raise ValueError("source admission SHA256 differs from contract")
    if contract.get("source_preflight_sha256") != source.get("preflight_sha256"):
        raise ValueError("source preflight SHA256 differs from contract")
    if (
        source.get("mode") != "portable_projection_of_offline_admission"
        or source.get("original_admission_sha256")
        != "a5bc9cb17802f74021babda70432f196e4cb41361888ddd04fb16da16a155ecb"
    ):
        raise ValueError("source admission projection lacks original evidence binding")
    if contract.get("groups") != list(GROUPS):
        raise ValueError("R4 groups must be B and C")
    calls = _observed_calls(source)
    if contract.get("scripted_calls_per_full_dev_run") != calls:
        raise ValueError("scripted full-run calls differ from contract")
    worker = contract.get("worker")
    researcher = contract.get("researcher")
    if not isinstance(worker, dict) or not isinstance(researcher, dict):
        raise ValueError("worker and researcher budgets must be objects")
    if worker.get("profile_path") != "configs/r4_siflow_qwen_worker_profile_v1.json":
        raise ValueError("unexpected R4 worker profile path")
    if worker.get("profile_sha256") != worker_profile_sha256:
        raise ValueError("R4 worker profile SHA256 differs from contract")
    if (
        worker.get("profile_id") != worker_profile.id
        or worker.get("model") != worker_profile.model
        or worker.get("max_output_tokens_per_request") != worker_profile.max_output_tokens
        or worker_profile.model != "Qwen/Qwen3.6-27B"
        or worker_profile.provider != "Siflow"
        or worker_profile.allowed_host != "api.siflow.cn"
        or worker_profile.max_output_tokens != 2048
        or worker_profile.seed != 42
        or worker_profile.temperature != 0.0
        or worker.get("thinking_enabled") is not False
        or worker_profile.chat_template_enable_thinking is not False
    ):
        raise ValueError("R4 worker profile and output settings differ")
    if researcher.get("profile_path") != "configs/r4_siflow_researcher_profile_v1.json":
        raise ValueError("unexpected R4 researcher profile path")
    if researcher.get("profile_sha256") != researcher_profile_sha256:
        raise ValueError("R4 researcher profile SHA256 differs from contract")
    if (
        researcher.get("profile_id") != researcher_profile.id
        or researcher.get("model") != researcher_profile.model
        or researcher_profile.model != "deepseek-ai/deepseek-v4.1-flash"
        or researcher_profile.provider != "Siflow"
        or researcher_profile.allowed_host != "api.siflow.cn"
        or researcher.get("max_output_tokens_per_request") != 8192
        or researcher_profile.max_output_tokens != 8192
        or researcher_profile.chat_template_enable_thinking is not False
        or researcher_profile.seed != 42
        or researcher_profile.temperature != 0.0
    ):
        raise ValueError("R4 researcher profile and output settings differ")
    draws = researcher.get("planned_draws_per_group")
    attempts = researcher.get("http_attempts_per_draw")
    cap = worker.get("request_cap_per_full_dev_run")
    headroom = worker.get("headroom_above_max_observed_candidate_calls")
    if any(type(value) is not int or value < 1 for value in (draws, attempts, cap, headroom)):
        raise ValueError("R4 call and draw limits must be positive integers")
    if draws != 2 or attempts != 1:
        raise ValueError("R4 researcher opportunity differs from the planned two draws")
    cap = cast(int, cap)
    headroom = cast(int, headroom)
    max_candidate = max(row["candidate"] for row in calls.values())
    if cap != max_candidate + headroom or headroom != 5:
        raise ValueError("R4 worker cap must equal observed maximum plus five calls")
    if any(max(row.values()) > cap for row in calls.values()):
        raise ValueError("R4 worker cap does not fit each scripted full dev run")
    total_worker_cap = len(GROUPS) * (1 + draws) * cap
    if worker.get("max_total_worker_requests_including_fixed_baselines") != total_worker_cap:
        raise ValueError("R4 total worker cap is inconsistent")
    if researcher.get("max_total_researcher_requests") != len(GROUPS) * draws * attempts:
        raise ValueError("R4 total researcher cap is inconsistent")
    if (
        contract.get("selection") != "none_in_capacity_qualification"
        or contract.get("live_enabled") is not False
    ):
        raise ValueError("R4 capacity qualification cannot select or enable live candidates")
    if contract.get("requires") != [
        "jailed_candidate_executor",
        "worker_profile_provider_canary",
        "qualified_independent_parent_manifest",
    ]:
        raise ValueError("R4 live admission requirements changed")
    return {
        "status": "scripted_capacity_admitted",
        "groups": {
            group: {
                "baseline_calls": calls[group]["baseline"],
                "candidate_calls": calls[group]["candidate"],
                "baseline_fits": calls[group]["baseline"] <= cap,
                "candidate_fits": calls[group]["candidate"] <= cap,
            }
            for group in GROUPS
        },
        "worker_request_cap_per_full_dev_run": cap,
        "max_total_worker_requests_including_fixed_baselines": total_worker_cap,
        "max_total_researcher_requests": len(GROUPS) * draws * attempts,
        "worker_profile_hash": worker_profile.profile_hash,
        "researcher_profile_hash": researcher_profile.profile_hash,
        "provider_revision_observable": worker_profile.version_pinned,
        "live_ready": False,
        "model_api_calls": 0,
    }


def _committed_bytes(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "show", f"HEAD:{relative}"], cwd=ROOT, check=True, capture_output=True
    ).stdout


def _identity(source_path: Path) -> dict[str, str]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if dirty:
        raise ValueError("commit tracked worktree changes before R4 qualification")
    for path in (CONTRACT, WORKER_PROFILES, RESEARCHER_PROFILES):
        if path.read_bytes() != _committed_bytes(path):
            raise ValueError(f"R4 input differs from committed HEAD: {path.name}")
    return {
        "git_head": head,
        "contract_sha256": _sha256(CONTRACT),
        "worker_profile_sha256": _sha256(WORKER_PROFILES),
        "researcher_profile_sha256": _sha256(RESEARCHER_PROFILES),
        "source_admission_sha256": _sha256(source_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-admission", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"R4 qualification output already exists: {args.output}")
    started_at = datetime.now(UTC).isoformat()
    start = _identity(args.source_admission)
    contract = json.loads(CONTRACT.read_text())
    source = json.loads(args.source_admission.read_text())
    worker_profile = load_api_profiles(WORKER_PROFILES).get(str(contract["worker"]["profile_id"]))
    researcher_profile = load_api_profiles(RESEARCHER_PROFILES).get(
        str(contract["researcher"]["profile_id"])
    )
    result = qualify_contract(
        contract,
        source,
        source_sha256=start["source_admission_sha256"],
        worker_profile=worker_profile,
        researcher_profile=researcher_profile,
        worker_profile_sha256=start["worker_profile_sha256"],
        researcher_profile_sha256=start["researcher_profile_sha256"],
    )
    end = _identity(args.source_admission)
    if end != start:
        raise RuntimeError("R4 qualification inputs changed during execution")
    result["run"] = {
        "started_at_utc": started_at,
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "start_identity": start,
        "end_identity": end,
        "identity_match": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"artifact": str(args.output), "status": result["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
