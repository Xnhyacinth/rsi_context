#!/usr/bin/env python3
"""Offline Gate 2 inventory and executable counterfactual probes.

This is an evaluator-side tool. Its public JSON contains hashes, booleans and
reason codes, never source text, oracles, legal plans, or item-level labels.
The scripted M2 worker proves harness reachability, not model difficulty.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess  # nosec B404
import sys
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from m2_validity_panel import (
    _c_decision_rules,
    _c_responder,
    _run_a_world,
    _run_b_world,
    _run_c_world,
    build_worlds,
)

from rsicontext.lifecycle.env import Action, ObjectiveChecker, ProjectState
from rsicontext.lifecycle.group_baselines import group_c_baseline_policy_text
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import _commit_gate_failures
from rsicontext.lifecycle.session_sequence import SequenceRecord, run_session_sequence
from rsicontext.lifecycle.spec import DocumentRef, LifecycleInstance, StageSpec
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

World = LifecycleInstance | list[LifecycleInstance]
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

_IDENTITY_FILES = (
    "scripts/qualify_r3_parent_projects.py",
    "scripts/m2_validity_panel.py",
    "src/rsicontext/lifecycle/dossier_variants.py",
    "src/rsicontext/lifecycle/material_v4_dossier.py",
    "src/rsicontext/lifecycle/material_b_group.py",
    "src/rsicontext/lifecycle/material_c_group.py",
    "src/rsicontext/lifecycle/material_m2_parents.py",
    "src/rsicontext/lifecycle/group_baselines.py",
    "src/rsicontext/lifecycle/env.py",
    "src/rsicontext/lifecycle/runner.py",
    "src/rsicontext/lifecycle/session_sequence.py",
    "src/rsicontext/lifecycle/spec.py",
    "src/rsicontext/lifecycle/tools.py",
    "uv.lock",
    "configs/budget_v1.json",
    "configs/registry.json",
)
_EXECUTION_PARAMETERS: dict[str, object] = {
    "mode": "offline-scripted-reference",
    "world_registry": "m2_validity_panel.build_worlds",
    "reference_max_turns_per_stage": {"A": 2, "B": 2, "C": 4},
    "interventions": [
        "first-award-named-card-removal",
        "first-award-winning-verification-fail",
        "combined-card-and-verification-removal",
        "first-nonempty-rule-scope-swap",
        "administrative-index-addition",
        "c-first-session-no-action",
        "c-later-gate-without-prior-record",
    ],
    "model_calls": 0,
    "gpu_calls": 0,
}

# Every present case descends from the synthetic supplier dossier. Changes in
# check count, stage graph, and answer do not create disjoint source projects.
_LINEAGE = {
    "a-mother": "supplier-dossier-v4",
    "a-mirror": "supplier-dossier-v4",
    "a-aurora-swap": "supplier-dossier-v4",
    "a-vector": "supplier-dossier-v4",
    "b-b1": "supplier-dossier-v4",
    "b-b1-reverse": "supplier-dossier-v4",
    "b-b2": "supplier-dossier-v4",
    "c-c1": "supplier-dossier-v4",
    "c-c1-mirror": "supplier-dossier-v4",
    "c-c2": "supplier-dossier-v4",
}


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _file_sha256(relative_path: str) -> str:
    return hashlib.sha256((_PROJECT_ROOT / relative_path).read_bytes()).hexdigest()


def _git_identity() -> dict[str, object]:
    """Identify checkout state without publishing patch contents."""

    def git(*args: str) -> bytes:
        # Git is called with fixed argument lists and no shell.
        return subprocess.run(  # nosec B603, B607
            ["git", *args], cwd=_PROJECT_ROOT, check=True, capture_output=True
        ).stdout

    try:
        head = git("rev-parse", "HEAD").decode("ascii").strip()
        patch = git("diff", "HEAD", "--binary")
        untracked = git(
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            "src",
            "scripts",
            "tests",
            "configs",
            "docs/reviews",
        ).split(b"\0")
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Gate 2 run identity requires a readable Git checkout") from exc
    untracked_hashes = [
        [
            path.decode("utf-8", errors="surrogateescape"),
            hashlib.sha256(
                (_PROJECT_ROOT / path.decode("utf-8", errors="surrogateescape")).read_bytes()
            ).hexdigest(),
        ]
        for path in sorted(x for x in untracked if x)
    ]
    return {
        "head": head,
        "dirty": bool(patch or untracked_hashes),
        "tracked_patch_sha256": hashlib.sha256(patch).hexdigest(),
        "untracked_relevant_sha256": _digest(untracked_hashes),
    }


def _source_tree_sha256() -> str:
    paths = sorted(
        path
        for directory in ("src", "scripts")
        for path in (_PROJECT_ROOT / directory).rglob("*.py")
        if path.is_file()
    )
    return _digest(
        [
            [str(path.relative_to(_PROJECT_ROOT)), hashlib.sha256(path.read_bytes()).hexdigest()]
            for path in paths
        ]
    )


def _world_hashes() -> dict[str, dict[str, str]]:
    """Hash current builder outputs, including evaluator fields only by digest."""

    hashes: dict[str, dict[str, str]] = {}
    for entries in build_worlds().values():
        for entry in entries:
            world: World = entry["build"]()
            sessions = _sessions(world)
            documents = [
                doc.to_dict()
                for inst in sessions
                for stage in inst.stages
                for doc in stage.documents
            ]
            hashes[str(entry["world_id"])] = {
                "material_sha256": _digest(documents),
                "evaluator_world_sha256": _digest([inst.to_dict() for inst in sessions]),
            }
    return hashes


def _run_identity(world_hashes: dict[str, dict[str, str]]) -> dict[str, object]:
    identity: dict[str, object] = {
        "schema_version": 1,
        "git": _git_identity(),
        "source_tree_sha256": _source_tree_sha256(),
        "file_sha256": {name: _file_sha256(name) for name in _IDENTITY_FILES},
        "world_hashes": world_hashes,
        "execution_parameters": _EXECUTION_PARAMETERS,
    }
    identity["sha256"] = _digest(identity)
    return identity


def _sessions(world: World) -> list[LifecycleInstance]:
    return [world] if isinstance(world, LifecycleInstance) else world


def _run(group: str, world: World) -> dict[str, Any]:
    if group == "A":
        if not isinstance(world, LifecycleInstance):
            raise TypeError("A world must be a lifecycle instance")
        return _run_a_world(world)
    if not isinstance(world, list):
        raise TypeError("B/C world must be a session list")
    return _run_b_world(world) if group == "B" else _run_c_world(world)


def _replace_stage(world: World, session_index: int, stage_index: int, stage: StageSpec) -> World:
    instances = _sessions(world).copy()
    old = instances[session_index]
    stages = list(old.stages)
    stages[stage_index] = stage
    instances[session_index] = replace(old, stages=tuple(stages))
    return instances[0] if isinstance(world, LifecycleInstance) else instances


def _first_award(world: World) -> tuple[int, int, StageSpec, str, tuple[str, ...]] | None:
    for si, inst in enumerate(_sessions(world)):
        for ti, stage in enumerate(inst.stages):
            pre = stage.commit_precondition
            if stage.kind != "act_verify" or pre is None:
                continue
            legal = pre.get("legal_plans")
            if (
                not isinstance(legal, list)
                or not legal
                or not all(isinstance(x, str) for x in legal)
            ):
                return None
            requirements = pre.get("plan_requirements")
            oracle = stage.verification_oracle
            if not isinstance(requirements, Mapping) or oracle is None:
                return None
            passing: list[str] = []
            for candidate in legal:
                candidate_rule = requirements.get(candidate)
                required = (
                    candidate_rule.get("requires_check")
                    if isinstance(candidate_rule, Mapping)
                    else None
                )
                candidate_checks = (required,) if isinstance(required, str) else required
                if (
                    isinstance(candidate_checks, (list, tuple))
                    and candidate_checks
                    and all(
                        isinstance(check, str) and oracle.get(check, {}).get(candidate) is True
                        for check in candidate_checks
                    )
                ):
                    passing.append(candidate)
            if len(passing) != 1:
                return None
            plan = passing[0]
            rule = requirements.get(plan) if isinstance(requirements, Mapping) else None
            required = rule.get("requires_check") if isinstance(rule, Mapping) else None
            if isinstance(required, str):
                checks = (required,)
            elif isinstance(required, (list, tuple)) and all(isinstance(x, str) for x in required):
                checks = tuple(required)
            else:
                return None
            return si, ti, stage, plan, checks
    return None


def _survey_source(
    world: World, plan: str, before_session: int
) -> tuple[int, int, DocumentRef] | None:
    for si, inst in enumerate(_sessions(world)):
        if si > before_session:
            break
        for ti, stage in enumerate(inst.stages):
            if stage.kind != "survey":
                continue
            for doc in stage.documents:
                header = doc.text.split("\n", 1)[0]
                if f"Supplier card: {plan}" in header:
                    return si, ti, doc
    return None


def _without_source(world: World, source: tuple[int, int, DocumentRef]) -> World:
    si, ti, doc = source
    stage = _sessions(world)[si].stages[ti]
    return _replace_stage(
        world,
        si,
        ti,
        replace(
            stage,
            documents=tuple(d for d in stage.documents if d.doc_id != doc.doc_id),
            gold_evidence_ids=tuple(x for x in stage.gold_evidence_ids if x != doc.doc_id),
        ),
    )


def _without_verification(
    world: World, award: tuple[int, int, StageSpec, str, tuple[str, ...]]
) -> World | None:
    si, ti, stage, plan, checks = award
    oracle = stage.verification_oracle
    if oracle is None or not checks or not all(oracle.get(c, {}).get(plan) is True for c in checks):
        return None
    changed = {check: dict(subjects) for check, subjects in oracle.items()}
    for check in checks:
        changed[check][plan] = False
    return _replace_stage(world, si, ti, replace(stage, verification_oracle=changed))


def _irrelevant_perturbation(world: World) -> World | None:
    for si, inst in enumerate(_sessions(world)):
        for ti, stage in enumerate(inst.stages):
            if stage.kind == "survey":
                doc = DocumentRef(
                    doc_id="gate2-irrelevant-index",
                    title="Administrative index",
                    text="Administrative index: page numbering and typography only.",
                    source_url="gate2:controlled-perturbation",
                    retrieved_date="2026-09-25",
                )
                return _replace_stage(
                    world, si, ti, replace(stage, documents=(*stage.documents, doc))
                )
    return None


def _changed_rule_scope(world: World) -> World | None:
    for si, inst in enumerate(_sessions(world)):
        for ti, stage in enumerate(inst.stages):
            if stage.kind == "rule_change" and stage.rule_change_scope:
                changed = (
                    ("cold-chain-integrity",)
                    if stage.rule_change_scope != ("cold-chain-integrity",)
                    else ("customs-preclearance",)
                )
                return _replace_stage(world, si, ti, replace(stage, rule_change_scope=changed))
    return None


def _c_trace(
    sessions: list[LifecycleInstance], *, no_first_action: bool = False
) -> tuple[SequenceRecord, ProjectState]:
    """C reference or no-first-action intervention, with one project env."""

    env = ProjectState()
    budget = ToolBudget()
    registry = DocumentRegistry()
    calls = 0

    def hook_factory(state: dict[str, object]) -> PolicyHook:
        nonlocal calls
        policy = (
            "def on_turn(turn):\n    return {'pack_text': 'no action'}\n"
            if no_first_action and calls == 0
            else group_c_baseline_policy_text()
        )
        calls += 1
        return PolicyHook(
            state, policy, tool_budget=budget, responder=_c_responder, registry=registry
        )

    record = run_session_sequence(
        sessions,
        hook_factory,
        envs=[env] * len(sessions),
        budget=budget,
        registry=registry,
        max_turns_per_stage=4,
        decision_rules=_c_decision_rules,
    )
    return record, env


def _later_c_gate_without_prior_commit(sessions: list[LifecycleInstance]) -> bool:
    """Check the second gate on a fresh env with no first-session records."""

    if len(sessions) != 2:
        return False
    env = ProjectState()
    for stage in sessions[1].stages:
        if stage.kind == "rule_change" and stage.rule_change_effect is not None:
            env.apply_protocol_revision(stage.rule_change_effect, stage.rule_change_scope)
        if stage.kind != "act_verify" or stage.commit_precondition is None:
            continue
        pre = stage.commit_precondition
        oracle = stage.verification_oracle
        legal = pre.get("legal_plans")
        record_id = pre.get("record_id")
        if (
            oracle is None
            or not isinstance(legal, list)
            or len(legal) != 1
            or not isinstance(legal[0], str)
            or not isinstance(record_id, str)
            or stage.expected_state_delta is None
        ):
            return False
        plan = legal[0]
        requirements = pre.get("plan_requirements")
        rule = requirements.get(plan) if isinstance(requirements, Mapping) else None
        required = rule.get("requires_check") if isinstance(rule, Mapping) else None
        if not isinstance(required, str):
            return False
        env.begin_instance(oracle)
        receipt = env.submit(
            Action("request_verification", "gate2-v", {"check": required, "subject": plan})
        )
        if not receipt.applied or receipt.verdict != "pass":
            return False
        env.submit(Action("create_record", record_id, {"plan": plan}))
        env.submit(
            Action(
                "finalize",
                record_id,
                {"plan": plan, "status": "final"},
                provenance=("gate2-v",),
            )
        )
        return (
            not _commit_gate_failures(pre, env.snapshot(), env)
            and ObjectiveChecker().check(env, stage.expected_state_delta).passed
        )
    return False


def _check(ok: bool, reason: str) -> dict[str, object]:
    return {"ok": ok, "reason": "passed" if ok else reason}


def _later_decisions_changed(full: dict[str, Any], changed: dict[str, Any]) -> bool:
    original = list(full["decisions"].values())
    counterfactual = list(changed["decisions"].values())
    return len(original) > 1 and original[1:] != counterfactual[1:]


def _decision_ledger(world: World) -> list[dict[str, object]]:
    """Hash-only structural links; a human must still review each proposition."""

    award = _first_award(world)
    first_source = _survey_source(world, award[3], award[0]) if award is not None else None
    rows: list[dict[str, object]] = []
    for si, inst in enumerate(_sessions(world)):
        for ti, stage in enumerate(inst.stages):
            if stage.commit_precondition is None and stage.expected_state_delta is None:
                continue
            source = (
                first_source[2]
                if award is not None and first_source is not None and (si, ti) == award[:2]
                else None
            )
            rows.append(
                {
                    "decision_index": len(rows),
                    "stage_kind": stage.kind,
                    "proposition_sha256": _digest(
                        stage.commit_precondition or stage.expected_state_delta
                    ),
                    "source_document_sha256": _digest(source.to_dict()) if source else None,
                    "verification_sha256": _digest(stage.verification_oracle)
                    if stage.verification_oracle
                    else None,
                    "legal_action_sha256": _digest(stage.commit_precondition)
                    if stage.commit_precondition
                    else None,
                    "later_state_sha256": _digest(stage.expected_state_delta)
                    if stage.expected_state_delta
                    else None,
                    "source_link_reviewed": False,
                }
            )
    return rows


def _qualify(group: str, world: World) -> dict[str, dict[str, object]]:
    full = _run(group, world)
    checks: dict[str, dict[str, object]] = {
        "reference_legal_path": _check(bool(full["passed"]), "reference_path_failed")
    }
    award = _first_award(world)
    if award is None:
        for key in (
            "decisive_text_removal",
            "verification_removal",
            "combined_removal",
            "early_action_dependency",
        ):
            checks[key] = _check(False, "single_plan_award_not_identified")
    else:
        source = _survey_source(world, award[3], award[0])
        no_text = _without_source(world, source) if source is not None else None
        no_verification = _without_verification(world, award)
        no_verification_run = _run(group, no_verification) if no_verification is not None else None
        checks["decisive_text_removal"] = _check(
            source is not None and _survey_source(no_text, award[3], award[0]) is None
            if no_text is not None
            else False,
            "decisive_source_not_unique_or_missing",
        )
        checks["verification_removal"] = _check(
            no_verification_run is not None and not bool(no_verification_run["passed"]),
            "verification_removal_did_not_break_reference",
        )
        if source is not None and no_text is not None and no_verification is not None:
            both = _without_source(no_verification, source)
            checks["combined_removal"] = _check(
                not bool(_run(group, both)["passed"]), "combined_removal_did_not_break_reference"
            )
        else:
            checks["combined_removal"] = _check(False, "combined_intervention_unavailable")
        if group == "A":
            checks["early_action_dependency"] = {"ok": None, "reason": "group_a_not_cross_session"}
        elif no_verification_run is None:
            checks["early_action_dependency"] = _check(False, "early_intervention_unavailable")
        else:
            checks["early_action_dependency"] = _check(
                _later_decisions_changed(full, no_verification_run),
                "later_decisions_unchanged_after_early_intervention",
            )
    changed_scope = _changed_rule_scope(world)
    checks["rule_scope_intervention"] = _check(
        changed_scope is not None and _run(group, changed_scope)["decisions"] != full["decisions"],
        "scope_change_did_not_change_reference_decisions",
    )
    irrelevant = _irrelevant_perturbation(world)
    irrelevant_run = _run(group, irrelevant) if irrelevant is not None else None
    checks["irrelevant_perturbation"] = _check(
        irrelevant_run is not None
        and irrelevant_run["decisions"] == full["decisions"]
        and bool(irrelevant_run["passed"]) == bool(full["passed"]),
        "irrelevant_text_changed_reference_outcome",
    )
    if group in ("B", "C"):
        # A changed pass/fail flag does not establish that the *legal answer*
        # changed. That needs a state-conditioned oracle derivation, archived
        # for each later decision. Keep the gate closed until it exists.
        checks["later_legal_answer_change"] = _check(
            False, "state_conditioned_later_answer_not_demonstrated"
        )
    if group == "C":
        if not isinstance(world, list):
            raise TypeError("C world must be a session list")
        no_first, env = _c_trace(world, no_first_action=True)
        first_award = _first_award(world)
        first_record = (
            first_award[2].commit_precondition.get("record_id")
            if first_award is not None and first_award[2].commit_precondition is not None
            else None
        )
        absent = isinstance(first_record, str) and first_record not in env.records
        checks["first_commit_removed"] = _check(absent, "no_action_intervention_left_a_commit")
        checks["later_result_changes_without_first_commit"] = _check(
            absent and no_first.decisions.get("session_2_passed") is False,
            "later_session_passed_without_first_commit",
        )
        independent_later_gate = _later_c_gate_without_prior_commit(world)
        checks["later_gate_requires_prior_commit"] = _check(
            not independent_later_gate,
            "later_gate_accepts_legal_commit_without_prior_record",
        )
    return checks


def inventory() -> dict[str, Any]:
    groups: dict[str, list[dict[str, object]]] = {}
    for group, entries in build_worlds().items():
        rows: list[dict[str, object]] = []
        for entry in entries:
            world_id = str(entry["world_id"])
            world: World = entry["build"]()
            sessions = _sessions(world)
            documents = [
                doc.to_dict() for inst in sessions for st in inst.stages for doc in st.documents
            ]
            sources = {str(doc["source_url"]) for doc in documents}
            checks = _qualify(group, world)
            rows.append(
                {
                    "world_id": world_id,
                    "parent_id": _LINEAGE[world_id],
                    "lineage_role": "root" if world_id == "a-mother" else "derived",
                    "material_sha256": _digest(documents),
                    "evaluator_world_sha256": _digest([inst.to_dict() for inst in sessions]),
                    "source_count": len(sources),
                    "synthetic_source_count": sum(
                        not src.startswith(("https://", "http://")) for src in sources
                    ),
                    "author_review": "not_recorded",
                    "structural_ledger": _decision_ledger(world),
                    "checks": checks,
                    "qualified": False,
                    "qualification_blockers": [
                        "shared_parent_lineage",
                        "disjoint_source_material_not_demonstrated",
                        "author_review_missing",
                        "proposition_links_not_author_reviewed",
                        *[key for key, check in checks.items() if check["ok"] is False],
                    ],
                }
            )
        groups[group] = rows
    return {
        "schema": "r3-gate2-parent-qualification-v2",
        "groups": groups,
        "summary": {
            "worlds": sum(map(len, groups.values())),
            "distinct_parent_lineages": len(set(_LINEAGE.values())),
            "qualified_independent_parents": 0,
            "qualified_worlds": 0,
            "qualified_groups": [],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/rsi-core-v1/r3-gate2-parent-qualification-v3-20260925.json"),
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Gate 2 output already exists: {args.output}")
    started_at = datetime.now(UTC).isoformat()
    start_identity = _run_identity(_world_hashes())
    result = inventory()
    result_hashes = {
        str(row["world_id"]): {
            "material_sha256": str(row["material_sha256"]),
            "evaluator_world_sha256": str(row["evaluator_world_sha256"]),
        }
        for rows in result["groups"].values()
        for row in rows
    }
    if result_hashes != start_identity["world_hashes"]:
        raise RuntimeError("world material changed between identity and qualification")
    end_identity = _run_identity(_world_hashes())
    if start_identity != end_identity:
        raise RuntimeError("checkout or material changed during Gate 2 qualification")
    result["run"] = {
        "started_at_utc": started_at,
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "start_identity": start_identity,
        "end_identity": end_identity,
        "identity_match": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(json.dumps(result["summary"], indent=2))
    print(f"artifact: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
