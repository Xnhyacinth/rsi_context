#!/usr/bin/env python3
"""B/C Gate 1 offline admission; live execution is gated on process isolation.

The scripted responder probes wiring and call demand. It is not a researcher
sample, a model difficulty measurement, or an effectiveness comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import r3_compare
from r2a_compare import _offline_responder, _policy_loadable
from r3_compare import (
    GroupSpec,
    _b_worlds,
    _c_worlds,
    _canonical_sha256,
    _dev_experience,
    _git_identity,
    _run_arm_on_group,
    _source_sha256,
)
from r3_researcher_pilot import _audit_candidate
from verify_r3_gate1_preflight import EXPECTED_PILOT, verify_inputs

from rsicontext.lifecycle.group_baselines import (
    group_b_basline_policy_text,
    group_c_baseline_policy_text,
)
from rsicontext.lifecycle.recuris_memory_policy import recuris_memory_policy_text
from rsicontext.lifecycle.session_sequence import SequenceRecord
from rsicontext.participant.recuris_real_arm import package_to_state

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PREFLIGHT = ROOT / "configs/r3_gate1_offline_preflight_v3.json"
DEFAULT_OUTPUT = ROOT / "artifacts/rsi-core-v1/r3-bc-gate1-offline-admission-v3-20260925.json"
EXPECTED_BASE = "7052c06494c37bed22fe14bdf929c20b3c9c6e29"
GROUPS = ("B", "C")
PROBE_CARD_ID = "gate1-delivery-probe"
REQUIRED_TRACKED_HASHES = (
    "uv.lock",
    "configs/api_profiles.json",
    "configs/budget_v1.json",
    "configs/registry.json",
    "seeds/open_s_v1/seed.py",
)
PILOT_CONTRACT = EXPECTED_PILOT


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _specs() -> dict[str, GroupSpec]:
    b_dev, b_eval = _b_worlds()
    c_dev, c_eval = _c_worlds()
    return {
        "B": GroupSpec(
            "B",
            b_dev,
            b_eval,
            shape="sequence",
            turns=2,
            baseline_policy=group_b_basline_policy_text(),
            dev_experience_stages=[
                "survey + award (session 1)",
                "resume + rule change + follow-ups (session 2)",
                "new project (session 3)",
            ],
        ),
        "C": GroupSpec(
            "C",
            c_dev,
            c_eval,
            shape="sequence",
            turns=3,
            baseline_policy=group_c_baseline_policy_text(),
            dev_experience_stages=[
                "survey + probe + fail receipt + switch (session 1)",
                "mutation + re-verify + re-award (session 2)",
            ],
        ),
    }


def _preflight(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    manifest = cast(dict[str, Any], json.loads(raw))
    if manifest.get("schema_version") != 3 or manifest.get("status") != "offline_preflight_only":
        raise ValueError("Gate 1 requires a version-3 offline-only preflight manifest")
    if manifest.get("baseline_commit") != EXPECTED_BASE:
        raise ValueError("unexpected Gate 1 baseline commit")
    if manifest.get("live_gate", {}).get("enabled") is not False:
        raise ValueError("Gate 1 live gate must remain disabled")
    candidate = manifest.get("candidate_pilot", {})
    if candidate != PILOT_CONTRACT:
        raise ValueError("Gate 1 pilot setting mismatch")
    hashes = manifest.get("tracked_sha256", {})
    if not set(REQUIRED_TRACKED_HASHES) <= set(hashes):
        raise ValueError("Gate 1 preflight omits required tracked hashes")
    for name, expected in hashes.items():
        actual = _sha256((ROOT / name).read_bytes())
        if actual != expected:
            raise ValueError(f"preflight resource hash mismatch: {name}")
    return manifest, _sha256(raw)


def _material_hashes(specs: dict[str, GroupSpec]) -> dict[str, str]:
    return {
        f"{group_id}_{phase}": _canonical_sha256([world.to_dict() for world in worlds])
        for group_id, spec in specs.items()
        for phase, worlds in (("dev", spec.dev_worlds), ("eval", spec.eval_worlds))
    }


def _identity(
    specs: dict[str, GroupSpec], manifest: dict[str, Any], preflight_sha256: str
) -> dict[str, object]:
    materials = {
        group_id: {
            phase: [
                {"instance_id": world.instance_id, "sha256": _canonical_sha256(world.to_dict())}
                for world in worlds
            ]
            for phase, worlds in (("dev", spec.dev_worlds), ("eval", spec.eval_worlds))
        }
        for group_id, spec in specs.items()
    }
    identity: dict[str, object] = {
        "schema_version": 1,
        "mode": "offline_admission",
        "git": _git_identity(),
        "source_sha256": _source_sha256(),
        "preflight_sha256": preflight_sha256,
        "preflight_baseline_commit": manifest["baseline_commit"],
        "execution_parameters": manifest["candidate_pilot"],
        "configuration_sha256": {
            name: _sha256((ROOT / "configs" / name).read_bytes())
            for name in ("budget_v1.json", "api_profiles.json", "registry.json")
        },
        "uv_lock_sha256": _sha256((ROOT / "uv.lock").read_bytes()),
        "materials": materials,
        "baseline_policy_sha256": {
            group_id: _sha256(spec.baseline_policy.encode()) for group_id, spec in specs.items()
        },
    }
    identity["identity_sha256"] = _canonical_sha256(identity)
    return identity


def _save_and_admit(policy: str, directory: Path) -> dict[str, object]:
    """Audit the exact Python-only directory before any load_policy call."""

    directory.mkdir(parents=True, exist_ok=False)
    path = directory / "policy.py"
    with path.open("x", encoding="utf-8") as handle:
        handle.write(policy)
    audit = _audit_candidate(str(directory), policy)
    loadable = audit["safe"] is True and _policy_loadable(policy)
    return {
        "candidate_dir": str(directory),
        "policy_path": str(path),
        "policy_sha256": _sha256(path.read_bytes()),
        "audit": audit,
        "loadable": loadable,
    }


def _probe_package(group_id: str) -> dict[str, object]:
    package = json.loads(json.dumps(r3_compare._R3_GROUP_SEEDS[group_id]))
    package["entries"] = [
        {
            "id": PROBE_CARD_ID,
            "body": "offline delivery probe; no answer content",
            "stage": "act_verify",
            "requires_field": None,
        }
    ]
    return cast(dict[str, object], package)


def _delivery_evidence(record: SequenceRecord) -> dict[str, object]:
    sessions: list[dict[str, object]] = []
    for session in record.sessions:
        delivered = any(
            isinstance(event, dict)
            and event.get("stage_kind") == "act_verify"
            and PROBE_CARD_ID in event.get("card_ids", [])
            for event in session.final_memory_delivered
        )
        metered_prompt = any(
            call.get("stage_kind") == "act_verify"
            and f"[{PROBE_CARD_ID}]" in str(call.get("prompt_head", ""))
            for call in session.model_transcript
        )
        excluded_survey = all(
            f"[{PROBE_CARD_ID}]" not in str(call.get("prompt_head", ""))
            for call in session.model_transcript
            if call.get("stage_kind") == "survey"
        )
        sessions.append(
            {
                "instance_id": session.instance_id,
                "model_calls": session.model_calls,
                "act_verify_memory_delivered": delivered,
                "act_verify_prompt_contains_card": metered_prompt,
                "survey_prompt_excludes_card": excluded_survey,
            }
        )
    return {
        "card_id": PROBE_CARD_ID,
        "sessions": sessions,
        "passed": bool(sessions)
        and all(
            item["act_verify_memory_delivered"]
            and item["act_verify_prompt_contains_card"]
            and item["survey_prompt_excludes_card"]
            for item in sessions
        ),
    }


def _profile_conflict() -> dict[str, object]:
    profiles = json.loads((ROOT / "configs/api_profiles.json").read_text())["profiles"]
    worker = next(p for p in profiles if p["id"] == "siflow-qwen3.6-27b-t2")
    budget = json.loads((ROOT / "configs/budget_v1.json").read_text())
    profile_cap = worker["max_output_tokens"]
    effective_cap = budget["worker_reader"]["max_output_tokens"]
    return {
        "worker_api_profile_id": worker["id"],
        "profile_max_output_tokens": profile_cap,
        "declared_effective_max_output_tokens": effective_cap,
        "unreconciled": profile_cap != effective_cap,
    }


def run_offline_admission(
    output: Path, preflight_path: Path, resource_root: Path
) -> dict[str, object]:
    if output.exists() or output.with_suffix("").exists():
        raise FileExistsError(f"refusing to overwrite admission artifact: {output}")
    manifest, manifest_sha256 = _preflight(preflight_path)
    specs = _specs()
    world_hashes = _material_hashes(specs)
    preflight_verification = verify_inputs(
        manifest, repo_root=ROOT, resource_root=resource_root, world_hashes=world_hashes
    )
    identity = _identity(specs, manifest, manifest_sha256)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix("").mkdir(exist_ok=False)
    result: dict[str, object] = {
        "status": "running",
        "purpose": "Gate 1 B/C offline wiring and capacity admission only; no model API",
        "started_at_utc": _utc_now(),
        "run_identity": identity,
        "preflight_path": str(preflight_path),
        "preflight_sha256": manifest_sha256,
        "preflight_verification": preflight_verification,
        "planned_attempts": {group_id: 2 for group_id in GROUPS},
        "actual_researcher_attempts": {group_id: 0 for group_id in GROUPS},
        "researcher_provider_usage_calls": [],
        "worker_provider_usage_calls": [],
        "provider_usage_status": "not_applicable_offline",
        "model_api_calls": 0,
        "profile_conflict": _profile_conflict(),
        "groups": {},
    }
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")

    original_sequence = cast(
        Callable[..., SequenceRecord], r3_compare.__dict__["run_session_sequence"]
    )
    captures: list[SequenceRecord] = []
    env_relations: list[dict[str, object]] = []

    def capture_sequence(*args: Any, **kwargs: Any) -> SequenceRecord:
        envs = cast(list[object], kwargs["envs"])
        env_relations.append(
            {
                "first_two_share_project": len(envs) >= 2 and envs[0] is envs[1],
                "last_is_new_project": len(envs) >= 3 and envs[-1] is not envs[0],
            }
        )
        record = original_sequence(*args, **kwargs)
        captures.append(record)
        return record

    sequence_patch = patch.object(r3_compare, "run_session_sequence", capture_sequence)
    sequence_patch.start()
    try:
        for group_id, spec in specs.items():
            started = time.monotonic()
            baseline = _run_arm_on_group(spec, spec.baseline_policy, _offline_responder)
            baseline_seq = captures[-1]
            project_relation = env_relations[-1]
            empty_worker = _run_arm_on_group(spec, spec.baseline_policy, lambda _prompt: "")
            failure_feedback = _dev_experience(spec, empty_worker)
            candidate_policy = spec.baseline_policy.replace("BATCH_DOCS = 6", "BATCH_DOCS = 4", 1)
            if candidate_policy == spec.baseline_policy:
                raise RuntimeError(f"{group_id} synthetic candidate did not change the policy")
            candidate = _save_and_admit(
                candidate_policy, output.with_suffix("") / group_id / "synthetic-candidate"
            )
            if candidate["loadable"] is not True:
                raise RuntimeError(f"{group_id} synthetic candidate failed admission")
            candidate_run = _run_arm_on_group(spec, candidate_policy, _offline_responder)
            candidate_seq = captures[-1]
            package = _probe_package(group_id)
            _run_arm_on_group(
                spec,
                recuris_memory_policy_text(),
                _offline_responder,
                initial_state=package_to_state(package),
            )
            delivery = _delivery_evidence(captures[-1])
            if delivery["passed"] is not True:
                raise RuntimeError(f"{group_id} Recuris card delivery probe failed")
            expected_continuity = project_relation["first_two_share_project"] is True and (
                group_id != "B" or project_relation["last_is_new_project"] is True
            )
            if not expected_continuity:
                raise RuntimeError(f"{group_id} project continuity probe failed")
            failures = cast(list[str], failure_feedback["failures"])
            if not failures:
                raise RuntimeError(f"{group_id} failed-run feedback contains no failure")
            cap = manifest["candidate_pilot"]["worker_request_cap_per_draw"]
            group_result: dict[str, object] = {
                "dev_world_ids": [world.instance_id for world in spec.dev_worlds],
                "dev_world_sha256": [
                    _canonical_sha256(world.to_dict()) for world in spec.dev_worlds
                ],
                "eval_worlds_hashed_not_run": True,
                "project_continuity": project_relation,
                "baseline_scripted": {
                    "passed": baseline["passed"],
                    "decisions": baseline["decisions"],
                    "worker_calls": baseline["model_calls"],
                    "worker_calls_by_session": [s.model_calls for s in baseline_seq.sessions],
                    "provider_tokens": None,
                },
                "synthetic_failure_probe": {
                    "worker_kind": "empty_scripted_response",
                    "passed": empty_worker["passed"],
                    "decisions": empty_worker["decisions"],
                    "failure_detail": empty_worker["failure_detail"],
                    "dev_feedback_sha256": _canonical_sha256(failure_feedback),
                    "dev_feedback": failure_feedback,
                },
                "synthetic_candidate": {
                    **candidate,
                    "worker_calls": candidate_run["model_calls"],
                    "worker_calls_by_session": [s.model_calls for s in candidate_seq.sessions],
                    "provider_tokens": None,
                },
                "recuris_delivery": delivery,
                "frozen_worker_request_cap_per_draw": cap,
                "baseline_fits_cap": cast(int, baseline["model_calls"]) <= cap,
                "candidate_fits_cap": cast(int, candidate_run["model_calls"]) <= cap,
                "wall_seconds": round(time.monotonic() - started, 3),
            }
            cast(dict[str, object], result["groups"])[group_id] = group_result
            output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    finally:
        sequence_patch.stop()
    end_manifest_sha256 = _sha256(preflight_path.read_bytes())
    end_identity = _identity(specs, manifest, end_manifest_sha256)
    result["run_identity_end"] = {
        "identity_sha256": end_identity["identity_sha256"],
        "matches_start": end_identity["identity_sha256"] == identity["identity_sha256"],
    }
    result["completed_at_utc"] = _utc_now()
    identity_end = cast(dict[str, object], result["run_identity_end"])
    result["status"] = "complete" if identity_end["matches_start"] else "identity_drift"
    result["live_gate"] = {
        "enabled": False,
        "reason": "No isolated candidate executor; host policy load executes model-authored Python",
        "frozen_v1_worker_cap_feasible": all(
            group["baseline_fits_cap"] and group["candidate_fits_cap"]
            for group in cast(dict[str, dict[str, object]], result["groups"]).values()
        ),
        "worker_profile_reconciled": not cast(dict[str, object], result["profile_conflict"])[
            "unreconciled"
        ],
    }
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", type=Path, default=DEFAULT_PREFLIGHT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--resource-root", type=Path)
    parser.add_argument(
        "--live", action="store_true", help="reserved until an isolated executor exists"
    )
    args = parser.parse_args()
    if args.live:
        parser.error(
            "live B/C pilot is unavailable: candidate process isolation is not implemented"
        )
    if args.resource_root is None:
        parser.error("offline admission requires --resource-root for visible resource verification")
    committed = subprocess.run(
        ["git", "show", "HEAD:configs/r3_gate1_offline_preflight_v3.json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    if args.preflight.read_bytes() != committed:
        parser.error("preflight manifest differs from committed HEAD bytes")
    result = run_offline_admission(args.output, args.preflight, args.resource_root)
    print(
        json.dumps(
            {
                "artifact": str(args.output),
                "status": result["status"],
                "live_gate": result["live_gate"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
