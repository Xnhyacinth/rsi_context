"""Matched OpenTelemetry source variants and offline action/receipt controls."""

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
from rsicontext.lifecycle.material_otel_source_contrast import (
    LICENSE_SHA256,
    SOURCE_FILES,
    SOURCE_REVISIONS,
    SOURCE_SHA256,
    build_otel_source_contrast_sessions,
)
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import StageView, _build_stage_view
from rsicontext.lifecycle.session_sequence import SequenceRecord, run_session_sequence
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

ROOT = Path(__file__).resolve().parent.parent
SOURCE_ENV = {
    "1.24": "RSICONTEXT_OTEL124_SOURCE_ROOT",
    "1.43": "RSICONTEXT_OTEL_SOURCE_ROOT",
}

_POLICY = """
import re

def on_turn(turn):
    stage = turn.view.stage_id
    state = turn.state
    if stage == "source-survey":
        if SOURCE_AWARE:
            source = turn.view.documents[0].text
            rows = [line for line in source.splitlines() if line.startswith("|")]
            matches = []
            for field in ("db.statement", "db.query.text"):
                if any(re.search(r"\\[`" + re.escape(field) + r"`\\]", row)
                       and "Recommended" in row for row in rows):
                    matches.append(field)
            chosen = matches[0] if len(matches) == 1 else None
        else:
            chosen = SOURCE_FREE_CHOICE
        state["carry"] = {"chosen": chosen} if KEEP_CARRY else {}
        return {"pack_text": "[[doc:upstream-db]] reviewed convention table"}
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
                turn.actions.create_record("convention_review", {"plan": "reviewed"}),
                turn.actions.finalize("convention_review", {"plan": "reviewed", "status": "final"},
                                      ("review-receipt",)),
            )}
    if stage == "decide-attribute":
        plan = state.get("carry", {}).get("chosen")
        if plan is None:
            return {"pack_text": "no selected source attribute"}
        phase = state.get("decision_phase", 0)
        if phase == 0:
            state["decision_phase"] = 1
            return {"pack_text": "request plan review", "actions": (
                turn.actions.request_verification("decision-receipt", "plan-reviewed", plan),
            )}
        if phase == 1:
            state["decision_phase"] = 2
            return {"pack_text": "commit plan", "actions": (
                turn.actions.create_record("query_attribute_plan", {"plan": plan}),
                turn.actions.finalize("query_attribute_plan", {"plan": plan, "status": "final"},
                                      ("decision-receipt",)),
            )}
    return {"pack_text": "observed"}
"""


def _source_root(revision: str) -> Path:
    configured = os.environ.get(SOURCE_ENV[revision])
    if not configured:
        pytest.skip(f"set {SOURCE_ENV[revision]} to the pinned detached checkout")
    return Path(configured)


def _sessions(revision: str) -> tuple[LifecycleInstance, LifecycleInstance]:
    return build_otel_source_contrast_sessions(_source_root(revision), revision=revision)


def _policy(
    *,
    source_aware: bool,
    source_free_choice: str = "db.query.text",
    keep_carry: bool = True,
    skip_first: bool = False,
) -> str:
    return (
        f"SOURCE_AWARE = {source_aware!r}\n"
        f"SOURCE_FREE_CHOICE = {source_free_choice!r}\n"
        f"KEEP_CARRY = {keep_carry!r}\n"
        f"SKIP_FIRST = {skip_first!r}\n" + _POLICY
    )


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
    )
    return record, env


def _without_source_text(view: StageView) -> dict[str, object]:
    projection = {field.name: getattr(view, field.name) for field in fields(StageView)}
    projection["documents"] = tuple(
        replace(doc, text="<pinned source bytes>") if doc.doc_id.startswith("upstream-") else doc
        for doc in view.documents
    )
    return projection


def test_pair_has_byte_identical_non_source_initial_stage_views() -> None:
    older, newer = _sessions("1.24"), _sessions("1.43")
    assert [inst.instance_id for inst in older] == [inst.instance_id for inst in newer]
    for left, right in zip(older, newer, strict=True):
        for index, (left_stage, right_stage) in enumerate(
            zip(left.stages, right.stages, strict=True)
        ):
            left_view = _build_stage_view(left_stage, left.axes, remaining=len(left.stages) - index)
            right_view = _build_stage_view(
                right_stage, right.axes, remaining=len(right.stages) - index
            )
            assert _without_source_text(left_view) == _without_source_text(right_view)
    assert older[1].stages[2].commit_precondition != newer[1].stages[2].commit_precondition
    assert older[1].stages[2].verification_oracle == newer[1].stages[2].verification_oracle
    request = older[1].stages[1].documents[0].text
    assert "db.statement" not in request
    assert "db.query.text" not in request


def test_frozen_source_aware_policy_passes_both_and_flips_action() -> None:
    outcomes = []
    for revision in ("1.24", "1.43"):
        record, env = _run(_sessions(revision), _policy(source_aware=True))
        outcomes.append(
            (
                [session.passed for session in record.sessions],
                env.records["query_attribute_plan"]["plan"],
            )
        )
        assert not any(session.policy_errors for session in record.sessions)
    assert outcomes == [([True, True], "db.statement"), ([True, True], "db.query.text")]


@pytest.mark.parametrize(
    "fixed,expected",
    [("db.query.text", [False, True]), ("db.statement", [True, False])],
)
def test_frozen_source_free_policy_cannot_pass_both(fixed: str, expected: list[bool]) -> None:
    outcomes = []
    receipts = []
    transcripts = []
    for revision in ("1.24", "1.43"):
        record, env = _run(
            _sessions(revision), _policy(source_aware=False, source_free_choice=fixed)
        )
        assert record.sessions[0].passed
        outcomes.append(record.sessions[1].passed)
        receipts.append((env.records["review-receipt"], env.records["decision-receipt"]))
        transcripts.append(env.transcript)
    assert outcomes == expected
    assert receipts[0] == receipts[1]
    assert transcripts[0] == transcripts[1]


def test_source_withheld_breaks_cross_variant_policy_vector() -> None:
    policy = _policy(source_aware=True)
    outcomes = []
    redacted_surveys = []
    for revision in ("1.24", "1.43"):
        first, second = _sessions(revision)
        survey = first.stages[0]
        withheld = tuple(
            replace(doc, text=f"[[doc:{doc.doc_id}]] withheld") for doc in survey.documents
        )
        redacted_surveys.append(withheld)
        first = replace(first, stages=(replace(survey, documents=withheld), *first.stages[1:]))
        record, _ = _run((first, second), policy)
        outcomes.append(record.sessions[1].passed)
    assert redacted_surveys[0] == redacted_surveys[1]
    assert outcomes == [False, False]


def test_swapping_only_source_text_flips_action_against_frozen_oracle() -> None:
    policy = _policy(source_aware=True)
    for reference, substitute in (("1.24", "1.43"), ("1.43", "1.24")):
        first, second = _sessions(reference)
        substitute_first, _ = _sessions(substitute)
        survey = first.stages[0]
        swapped_doc = replace(
            survey.documents[0], text=substitute_first.stages[0].documents[0].text
        )
        first = replace(
            first,
            stages=(
                replace(survey, documents=(swapped_doc, survey.documents[1])),
                *first.stages[1:],
            ),
        )
        record, _ = _run((first, second), policy)
        assert [session.passed for session in record.sessions] == [True, False]


def test_no_carry_no_reread_fails_later_action() -> None:
    for revision in ("1.24", "1.43"):
        record, _ = _run(_sessions(revision), _policy(source_aware=True, keep_carry=False))
        assert [session.passed for session in record.sessions] == [True, False]


def test_missing_prior_verified_finalize_fails_later_action() -> None:
    record, _ = _run(_sessions("1.43"), _policy(source_aware=True, skip_first=True))
    assert [session.passed for session in record.sessions] == [False, False]
    assert any("prior finalized record" in failure for failure in record.sessions[1].failures)


def test_builder_rejects_unknown_revision_and_source_drift(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported OpenTelemetry source revision"):
        build_otel_source_contrast_sessions(_source_root("1.24"), revision="1.35")
    source = _source_root("1.24")
    relative = SOURCE_FILES["1.24"]
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True)
    destination.write_bytes((source / relative).read_bytes() + b"\nchanged")
    (tmp_path / "LICENSE").write_bytes((source / "LICENSE").read_bytes())
    with pytest.raises(ValueError, match="pinned OpenTelemetry source mismatch"):
        build_otel_source_contrast_sessions(tmp_path, revision="1.24")


def test_manifest_registry_checkout_file_and_span_identity() -> None:
    manifest = cast(
        dict[str, Any],
        json.loads((ROOT / "configs/r10_otel_source_contrast_manifest_v1.json").read_text()),
    )
    registry = json.loads((ROOT / "configs/registry.json").read_text())
    assert "/volume/" not in json.dumps(manifest)
    for revision in ("1.24", "1.43"):
        variant = manifest["variants"][revision]
        entry = next(row for row in registry["entries"] if row["id"] == variant["registry_id"])
        assert (
            entry["revision"]
            == entry["checksum"]["value"]
            == variant["source_revision"]
            == SOURCE_REVISIONS[revision]
        )
        root = _source_root(revision)
        head = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        status = subprocess.check_output(
            ["git", "-C", str(root), "status", "--porcelain"], text=True
        )
        assert head == SOURCE_REVISIONS[revision] and not status
        files = variant["selected_files"]
        assert files[SOURCE_FILES[revision]]["sha256"] == SOURCE_SHA256[revision]
        assert files["LICENSE"]["sha256"] == LICENSE_SHA256
        for relative, identity in files.items():
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
