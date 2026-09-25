#!/usr/bin/env python3
"""Verify the frozen inputs for the R3 Gate-1 offline preflight."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = PROJECT_ROOT / "configs/r3_gate1_offline_preflight_v3.json"
MANIFEST_GIT_PATH = "configs/r3_gate1_offline_preflight_v3.json"
BASELINE_COMMIT = "7052c06494c37bed22fe14bdf929c20b3c9c6e29"
TRACKED_INPUTS = frozenset(
    {
        "uv.lock",
        "configs/api_profiles.json",
        "configs/budget_v1.json",
        "configs/registry.json",
        "seeds/open_s_v1/seed.py",
    }
)
VISIBLE_INPUTS = frozenset({"a-dev-feedback.json"})
WORLD_PHASES = frozenset({"B_dev", "B_eval", "C_dev", "C_eval"})
EXPECTED_PILOT: dict[str, object] = {
    "groups": ["B", "C"],
    "planned_researcher_draws_per_group": 2,
    "researcher_model": "deepseek-ai/deepseek-v4.1-flash",
    "researcher_thinking": "disabled",
    "researcher_max_output_tokens_per_draw": 8192,
    "researcher_http_attempts_per_draw": 1,
    "worker_model": "Qwen/Qwen3.6-27B",
    "worker_thinking": "disabled",
    "worker_max_output_tokens_per_request": 2048,
    "worker_request_cap_per_draw": 16,
    "worker_request_cap_per_group": 32,
    "observed_scripted_baseline_worker_calls_per_dev_run": {"B": 31, "C": 18},
    "observed_scripted_candidate_worker_calls_per_dev_run": {"B": 35, "C": 20},
    "worker_call_cap_feasible_for_full_bc_dev_run": False,
    "temperature": 0.0,
    "seed": 42,
    "evaluation_selection": "none",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_file(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(part in {".", ".."} for part in path.parts):
        raise ValueError(f"unsafe manifest path: {relative!r}")
    target = root / path
    if (
        target.is_symlink()
        or not target.is_file()
        or not target.resolve().is_relative_to(root.resolve())
    ):
        raise ValueError(f"missing or non-regular manifest input: {target}")
    return target


def _digest_map(value: object, name: str) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{name} must be a nonempty object")
    result: dict[str, str] = {}
    for path, digest in value.items():
        if not isinstance(path, str) or not isinstance(digest, str):
            raise ValueError(f"{name} entries must be strings")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"invalid SHA256 for {path!r}")
        result[path] = digest
    return result


def _world_material_hashes() -> dict[str, str]:
    """Hash built worlds internally; never print evaluator-only material."""

    from r3_compare import _b_worlds, _c_worlds, _canonical_sha256

    return {
        f"{group}_{phase}": _canonical_sha256([world.to_dict() for world in worlds])
        for group, pair in (("B", _b_worlds()), ("C", _c_worlds()))
        for phase, worlds in (("dev", pair[0]), ("eval", pair[1]))
    }


def verify_inputs(
    manifest: dict[str, Any], *, repo_root: Path, resource_root: Path, world_hashes: dict[str, str]
) -> dict[str, object]:
    """Check bytes and planned budget without loading policy code or using APIs."""

    if manifest.get("schema_version") != 3 or manifest.get("status") != "offline_preflight_only":
        raise ValueError("expected the version-3 offline preflight manifest")
    if manifest.get("baseline_commit") != BASELINE_COMMIT:
        raise ValueError("baseline commit differs from Gate-1 v3")
    tracked = _digest_map(manifest.get("tracked_sha256"), "tracked_sha256")
    visible = _digest_map(manifest.get("visible_resource_sha256"), "visible_resource_sha256")
    worlds = _digest_map(manifest.get("world_material_sha256"), "world_material_sha256")
    if tracked.keys() != TRACKED_INPUTS or visible.keys() != VISIBLE_INPUTS:
        raise ValueError("manifest input file set differs from Gate-1 v3")
    if worlds.keys() != WORLD_PHASES or worlds != world_hashes:
        raise ValueError("built world material hashes differ from Gate-1 v3")
    checked: dict[str, str] = {}
    for prefix, root, entries in (
        ("tracked", repo_root, tracked),
        ("visible", resource_root, visible),
    ):
        for relative, expected in entries.items():
            actual = _sha256(_safe_file(root, relative))
            if actual != expected:
                raise ValueError(f"{prefix} input hash mismatch: {relative}")
            checked[f"{prefix}:{relative}"] = actual
    pilot = manifest.get("candidate_pilot")
    live_gate = manifest.get("live_gate")
    if pilot != EXPECTED_PILOT:
        raise ValueError("candidate_pilot differs from Gate-1 v3 settings")
    if not isinstance(live_gate, dict) or live_gate.get("enabled") is not False:
        raise ValueError("this manifest cannot authorize live execution")
    if live_gate.get("requires_actual_isolated_executor") is not True:
        raise ValueError("isolated executor requirement is missing")
    if (
        live_gate.get("requires_reader_profile_reconciliation") is not True
        or live_gate.get("requires_qualified_parent_manifest") is not True
        or live_gate.get("requires_versioned_bc_worker_cap") is not True
    ):
        raise ValueError("Gate-1 live blockers are incomplete")
    return {
        "status": "offline_inputs_verified",
        "checked_sha256": checked,
        "world_material_sha256": worlds,
        "worker_call_cap_feasible": False,
        "live_ready": False,
    }


def _git_identity(repo_root: Path, baseline: str, *, require_clean: bool) -> str:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, capture_output=True, text=True
    ).stdout.strip()
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", baseline, head],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    if require_clean:
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if dirty:
            raise ValueError("tracked worktree changes remain; commit before execution")
        untracked_runtime = subprocess.run(
            [
                "git",
                "ls-files",
                "--others",
                "--exclude-standard",
                "--",
                "src",
                "scripts",
                "configs",
                "policy",
            ],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if untracked_runtime:
            raise ValueError("untracked runtime source remains; commit before execution")
    return head


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource-root", type=Path, required=True)
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    try:
        manifest_bytes = DEFAULT_MANIFEST.read_bytes()
        committed_bytes = subprocess.run(
            ["git", "show", f"HEAD:{MANIFEST_GIT_PATH}"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
        ).stdout
        if manifest_bytes != committed_bytes:
            raise ValueError("preflight manifest differs from committed HEAD bytes")
        manifest = json.loads(manifest_bytes)
        result = verify_inputs(
            manifest,
            repo_root=PROJECT_ROOT,
            resource_root=args.resource_root,
            world_hashes=_world_material_hashes(),
        )
        baseline = manifest["baseline_commit"]
        if not isinstance(baseline, str) or len(baseline) != 40:
            raise ValueError("baseline_commit must be a full Git SHA")
        result["git_head"] = _git_identity(PROJECT_ROOT, baseline, require_clean=args.require_clean)
        result["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
        result["python_version"] = sys.version.split()[0]
        if result["python_version"] != manifest["python_version"]:
            raise ValueError("Python interpreter version differs from the manifest")
        if Path(sys.prefix).resolve() != (PROJECT_ROOT / ".venv").resolve():
            raise ValueError("the project-local .venv interpreter is required")
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
