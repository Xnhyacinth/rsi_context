#!/usr/bin/env python3
"""Hash and summary inventory of unqualified R4 development parent candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rsicontext.lifecycle.material_k8s_parent import build_k8s_sidecar_sessions
from rsicontext.lifecycle.material_otel_parent import build_otel_database_migration_parent
from rsicontext.lifecycle.spec import LifecycleInstance

ROOT = Path(__file__).resolve().parent.parent
SOURCE_MANIFEST = ROOT / "configs/r4_parent_source_manifest_v1.json"
IDENTITY_FILES = (
    "uv.lock",
    "configs/registry.json",
    "configs/r4_parent_source_manifest_v1.json",
    "src/rsicontext/lifecycle/material_otel_parent.py",
    "src/rsicontext/lifecycle/material_k8s_parent.py",
    "scripts/audit_r4_parent_candidates.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _sessions(
    world: LifecycleInstance | tuple[LifecycleInstance, ...],
) -> tuple[LifecycleInstance, ...]:
    return (world,) if isinstance(world, LifecycleInstance) else world


def _candidate(
    *,
    group: str,
    parent_lineage: str,
    source_id: str,
    world: LifecycleInstance | tuple[LifecycleInstance, ...],
    source_revision: str,
) -> dict[str, object]:
    sessions = _sessions(world)
    documents = [
        doc for instance in sessions for stage in instance.stages for doc in stage.documents
    ]
    source_docs = [doc for doc in documents if doc.source_url.startswith("https://github.com/")]
    prompts = [stage.prompt_text for instance in sessions for stage in instance.stages]
    serialized = (
        world.to_dict() if isinstance(world, LifecycleInstance) else [s.to_dict() for s in world]
    )
    return {
        "group": group,
        "parent_lineage": parent_lineage,
        "source_id": source_id,
        "source_revision": source_revision,
        "session_count": len(sessions),
        "stage_count": sum(len(instance.stages) for instance in sessions),
        "document_count": len(documents),
        "source_document_count": len(source_docs),
        "source_whitespace_words": sum(len(doc.text.split()) for doc in source_docs),
        "visible_whitespace_words": sum(len(doc.text.split()) for doc in documents)
        + sum(len(prompt.split()) for prompt in prompts),
        "material_sha256": _digest([doc.to_dict() for doc in documents]),
        "evaluator_world_sha256": _digest(serialized),
        "answer_literal_in_stage_prompt": any(
            instance.answer_norm.casefold() in stage.prompt_text.casefold()
            for instance in sessions
            for stage in instance.stages
        ),
        "long_context_qualified": False,
        "model_difficulty_measured": False,
        "qualified": False,
        "qualification_blockers": [
            "human_source_and_legal_ledger_review_not_frozen",
            "target_tokenized_long_context_difficulty_not_measured",
            "real_reader_difficulty_not_measured",
            "parent_split_not_frozen",
        ],
    }


def inventory() -> dict[str, Any]:
    manifest = json.loads(SOURCE_MANIFEST.read_text())
    if (
        manifest.get("schema_version") != 1
        or manifest.get("status") != "development_candidates_only"
    ):
        raise ValueError("expected committed R4 development source manifest")
    sources = {row["id"]: row for row in manifest["sources"]}
    if set(sources) != {"otel-semconv-v1.43.0", "kubernetes-enhancements-kep753"}:
        raise ValueError("R4 source manifest entries changed")
    candidates = [
        _candidate(
            group="A",
            parent_lineage="otel-db-migration",
            source_id="otel-semconv-v1.43.0",
            world=build_otel_database_migration_parent(),
            source_revision=str(sources["otel-semconv-v1.43.0"]["revision"]),
        ),
        _candidate(
            group="C",
            parent_lineage="k8s-sidecar-rollout",
            source_id="kubernetes-enhancements-kep753",
            world=build_k8s_sidecar_sessions(),
            source_revision=str(sources["kubernetes-enhancements-kep753"]["revision"]),
        ),
    ]
    return {
        "schema_version": 1,
        "status": "development_candidates_only",
        "candidates": candidates,
        "summary": {
            "new_candidate_parent_lineages": 2,
            "qualified_independent_parents": 0,
            "qualified_groups": [],
            "model_api_calls": 0,
        },
    }


def _identity() -> dict[str, object]:
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
        raise ValueError("commit tracked source changes before R4 inventory")
    for name in IDENTITY_FILES:
        committed = subprocess.run(
            ["git", "show", f"HEAD:{name}"], cwd=ROOT, check=True, capture_output=True
        ).stdout
        if (ROOT / name).read_bytes() != committed:
            raise ValueError(f"inventory input differs from committed HEAD: {name}")
    return {
        "git_head": head,
        "file_sha256": {name: _sha256(ROOT / name) for name in IDENTITY_FILES},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/rsi-core-v1/r4-parent-candidates-v1.json")
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"R4 parent inventory already exists: {args.output}")
    started_at = datetime.now(UTC).isoformat()
    start = _identity()
    result = inventory()
    end = _identity()
    if start != end:
        raise RuntimeError("R4 parent inventory inputs changed during execution")
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
    print(json.dumps({"artifact": str(args.output), "summary": result["summary"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
