"""Offline matched-source contrast and source-identity checks."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import fields, replace
from pathlib import Path
from typing import Any, cast

import pytest

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_postgresql_source_contrast import (
    SOURCE_REVISIONS,
    SOURCE_SHA256,
    build_postgresql_source_contrast_sessions,
)
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import StageView, _build_stage_view
from rsicontext.lifecycle.session_sequence import SequenceRecord, run_session_sequence
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

ROOT = Path(__file__).resolve().parent.parent
SOURCE_ENV = {
    "16": "RSICONTEXT_POSTGRESQL16_SOURCE_ROOT",
    "17": "RSICONTEXT_POSTGRESQL_SOURCE_ROOT",
}

_POLICY = """
import re

def on_turn(turn):
    stage = turn.view.stage_id
    state = turn.state
    if stage == "source-survey":
        if SOURCE_AWARE:
            source = turn.view.documents[0].text
            # Parse SGML parameter terms, rather than looking for a prose phrase.
            terms = re.findall(r"<term><literal>([a-z_]+)</literal> \\(<type>", source)
            supported = "failover" in terms
        else:
            supported = SOURCE_FREE_NATIVE
        state["carry"] = {"native_supported": supported}
        return {"pack_text": "[[doc:upstream-create-subscription]] reviewed parameter catalog"}
    if stage == "review-source":
        phase = state.get("review_phase", 0)
        if phase == 0:
            state["review_phase"] = 1
            return {"pack_text": "request review", "actions": (
                turn.actions.request_verification("review-receipt", "review-complete", "reviewed"),
            )}
        if phase == 1 and not SKIP_FIRST:
            state["review_phase"] = 2
            return {"pack_text": "commit review", "actions": (
                turn.actions.create_record("source_review", {"plan": "reviewed"}),
                turn.actions.finalize("source_review", {"plan": "reviewed", "status": "final"},
                                      ("review-receipt",)),
            )}
    if stage == "decide-capability":
        supported = state.get("carry", {}).get("native_supported", False)
        plan = "configure-native" if supported else "defer-native"
        phase = state.get("decision_phase", 0)
        if phase == 0:
            state["decision_phase"] = 1
            return {"pack_text": "request decision review", "actions": (
                turn.actions.request_verification("decision-receipt", "decision-reviewed", plan),
            )}
        if phase == 1:
            state["decision_phase"] = 2
            return {"pack_text": "commit decision", "actions": (
                turn.actions.create_record("native_capability_decision", {"plan": plan}),
                turn.actions.finalize("native_capability_decision",
                                      {"plan": plan, "status": "final"},
                                      ("decision-receipt",)),
            )}
    return {"pack_text": "observed"}
"""


def _source_root(revision: str) -> Path:
    configured = os.environ.get(SOURCE_ENV[revision])
    if not configured:
        pytest.skip(f"set {SOURCE_ENV[revision]} to the detached pinned checkout")
    return Path(configured)


def _sessions(revision: str) -> tuple[LifecycleInstance, LifecycleInstance]:
    return build_postgresql_source_contrast_sessions(_source_root(revision), revision=revision)


def _policy(
    *, source_aware: bool, source_free_native: bool = True, skip_first: bool = False
) -> str:
    return (
        f"SOURCE_AWARE = {source_aware!r}\n"
        f"SOURCE_FREE_NATIVE = {source_free_native!r}\n"
        f"SKIP_FIRST = {skip_first!r}\n" + _POLICY
    )


def _decisions(record: SequenceRecord, _sessions: list[LifecycleInstance]) -> None:
    record.decisions["prior"] = record.sessions[0].passed
    record.decisions["later"] = record.sessions[1].passed


def _run(
    sessions: tuple[LifecycleInstance, LifecycleInstance], policy_text: str
) -> tuple[SequenceRecord, ProjectState]:
    env = ProjectState()
    budget = ToolBudget(max_calls=20)
    registry = DocumentRegistry()

    def factory(state: dict[str, object]) -> PolicyHook:
        return PolicyHook(state, policy_text, tool_budget=budget, registry=registry)

    record = run_session_sequence(
        list(sessions),
        factory,
        envs=[env, env],
        budget=budget,
        registry=registry,
        max_turns_per_stage=3,
        decision_rules=_decisions,
    )
    return record, env


def _visible_without_source_text(view: StageView) -> dict[str, object]:
    projection = {field.name: getattr(view, field.name) for field in fields(StageView)}
    projection["documents"] = tuple(
        replace(doc, text="<pinned source bytes>") if doc.doc_id.startswith("upstream-") else doc
        for doc in view.documents
    )
    return projection


def test_source_pair_matches_every_non_source_initial_stage_view() -> None:
    older, newer = _sessions("16"), _sessions("17")
    assert [inst.instance_id for inst in older] == [inst.instance_id for inst in newer]
    for left, right in zip(older, newer, strict=True):
        for index, (left_stage, right_stage) in enumerate(
            zip(left.stages, right.stages, strict=True)
        ):
            left_view = _build_stage_view(left_stage, left.axes, remaining=len(left.stages) - index)
            right_view = _build_stage_view(
                right_stage, right.axes, remaining=len(right.stages) - index
            )
            assert _visible_without_source_text(left_view) == _visible_without_source_text(
                right_view
            )
    assert older[1].stages[2].commit_precondition != newer[1].stages[2].commit_precondition
    assert older[1].stages[2].verification_oracle == newer[1].stages[2].verification_oracle


def test_one_frozen_source_aware_policy_passes_both_and_flips_later_action() -> None:
    policy = _policy(source_aware=True)
    observed = []
    for revision in ("16", "17"):
        record, env = _run(_sessions(revision), policy)
        observed.append((record.decisions, env.records["native_capability_decision"]["plan"]))
        assert not any(session.policy_errors for session in record.sessions)
    assert observed == [
        ({"prior": True, "later": True}, "defer-native"),
        ({"prior": True, "later": True}, "configure-native"),
    ]


@pytest.mark.parametrize("fixed_native,expected", [(True, [False, True]), (False, [True, False])])
def test_one_frozen_source_free_policy_cannot_pass_both(
    fixed_native: bool, expected: list[bool]
) -> None:
    policy = _policy(source_aware=False, source_free_native=fixed_native)
    outcomes = []
    receipts = []
    transcripts = []
    for revision in ("16", "17"):
        record, env = _run(_sessions(revision), policy)
        assert record.sessions[0].passed
        outcomes.append(record.sessions[1].passed)
        receipts.append((env.records["review-receipt"], env.records["decision-receipt"]))
        transcripts.append(env.transcript)
    assert outcomes == expected
    assert receipts[0] == receipts[1]
    assert transcripts[0] == transcripts[1]


def test_source_removed_breaks_the_cross_version_source_aware_vector() -> None:
    policy = _policy(source_aware=True)
    outcomes = []
    for revision in ("16", "17"):
        first, second = _sessions(revision)
        survey = first.stages[0]
        withheld = replace(
            survey.documents[0], text="[[doc:upstream-create-subscription]] withheld"
        )
        first = replace(
            first,
            stages=(replace(survey, documents=(withheld, survey.documents[1])), *first.stages[1:]),
        )
        record, _ = _run((first, second), policy)
        outcomes.append(record.sessions[1].passed)
    assert outcomes == [True, False]


def test_missing_prior_verified_finalize_rejects_later_even_with_correct_source() -> None:
    record, _ = _run(_sessions("17"), _policy(source_aware=True, skip_first=True))
    assert record.decisions == {"prior": False, "later": False}
    assert any("prior finalized record" in failure for failure in record.sessions[1].failures)


def test_builder_refuses_unregistered_revision_and_modified_source(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported PostgreSQL source revision"):
        build_postgresql_source_contrast_sessions(_source_root("16"), revision="18")
    source = _source_root("16")
    destination = tmp_path / "doc/src/sgml/ref"
    destination.mkdir(parents=True)
    (tmp_path / "COPYRIGHT").write_bytes((source / "COPYRIGHT").read_bytes())
    original = (source / "doc/src/sgml/ref/create_subscription.sgml").read_bytes()
    (destination / "create_subscription.sgml").write_bytes(original + b"\nchanged")
    with pytest.raises(ValueError, match="pinned PostgreSQL source mismatch"):
        build_postgresql_source_contrast_sessions(tmp_path, revision="16")


def test_manifest_and_checkout_identity() -> None:
    manifest = cast(
        dict[str, Any],
        json.loads(
            (ROOT / "configs/r9_postgresql16_source_manifest_v1.json").read_text(encoding="utf-8")
        ),
    )
    registry = json.loads((ROOT / "configs/registry.json").read_text(encoding="utf-8"))
    entry = next(row for row in registry["entries"] if row["id"] == "postgresql-rel-16-0")
    assert manifest["source_revision"] == entry["revision"] == SOURCE_REVISIONS["16"]
    assert entry["checksum"]["value"] == SOURCE_REVISIONS["16"]
    assert "/volume/" not in json.dumps(manifest)
    assert {
        key: value["sha256"] for key, value in manifest["selected_files"].items()
    } == SOURCE_SHA256["16"]
    root = _source_root("16")
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    status = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True)
    assert head == SOURCE_REVISIONS["16"] and not status
    for relative, identity in manifest["selected_files"].items():
        raw = (root / relative).read_bytes()
        assert len(raw) == identity["size_bytes"]
        assert hashlib.sha256(raw).hexdigest() == identity["sha256"]
        blob = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", f"HEAD:{relative}"], text=True
        ).strip()
        assert blob == identity["git_blob"]
        lines = raw.splitlines(keepends=True)
        for span in identity["spans"].values():
            offset = sum(len(line) for line in lines[: span["start_line"] - 1])
            excerpt = b"".join(lines[span["start_line"] - 1 : span["end_line"]])
            assert (offset, offset + len(excerpt)) == (span["start_byte"], span["end_byte"])
            assert hashlib.sha256(excerpt).hexdigest() == span["sha256"]
