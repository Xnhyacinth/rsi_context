"""Bounded offline probes for the historical PEP license-format B card."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_pep_r14 import (
    SOURCE_FILES,
    SOURCE_REVISION,
    SourceVariant,
    build_pep_license_sessions,
)
from rsicontext.lifecycle.runner import StageResponse, StageView
from rsicontext.lifecycle.session_sequence import SequenceRecord, run_session_sequence
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

_PLANS = {"pep621": "license-table", "pep639": "license-string"}
_TABLE_RULE = "- Format: Table"
_STRING_RULE = "Add string value to ``license`` key"
_DEPRECATED_RULE = "Table values for the ``license`` key in the ``[project]`` table"
_SPANS = (
    (
        "peps/pep-0621.rst",
        235,
        260,
        9133,
        10374,
        "50eeabd958dc78bfe0142c0679f2b731d23d7b1b1b6c6cc52c270d0148c2bee4",
    ),
    (
        "peps/pep-0639.rst",
        485,
        514,
        17929,
        18744,
        "9217e8c78defae28334678df179bf1d8241e9695afb480cd91a0bbb72a6c2f9b",
    ),
    (
        "peps/pep-0639.rst",
        608,
        634,
        21545,
        22788,
        "02cf171fecd2872a6894d5202106fe25eefa74028cd89c7cb502e853ef70060a",
    ),
)


@pytest.fixture(scope="module")
def source_root() -> Path:
    configured = os.environ.get("RSICONTEXT_PEP_SOURCE_ROOT")
    if configured is None:
        pytest.skip("set RSICONTEXT_PEP_SOURCE_ROOT to the pinned detached checkout")
    root = Path(configured)
    if not root.is_dir():
        pytest.fail(f"configured PEP checkout is missing: {root}")
    return root


def _source_plan(text: str) -> str | None:
    if _STRING_RULE in text and _DEPRECATED_RULE in text:
        return "license-string"
    if _TABLE_RULE in text and _STRING_RULE not in text:
        return "license-table"
    return None


class _Witness:
    """A transparent scripted reader; no evaluator fields are consulted."""

    def __init__(
        self, state: dict[str, object], *, fixed_plan: str | None, identity_only: bool
    ) -> None:
        self.state = state
        self.fixed_plan = fixed_plan
        self.identity_only = identity_only
        self.initial_state = json.loads(json.dumps(state))
        self.views: list[StageView] = []

    def on_stage(self, stage: StageView) -> StageResponse:
        self.views.append(stage)
        if stage.stage_id == "source-survey":
            source = stage.documents[0]
            if self.identity_only:
                self.state["source_plan"] = next(
                    (
                        _PLANS[variant]
                        for variant, (relative, _hash) in SOURCE_FILES.items()
                        if source.source_url.endswith("/" + relative)
                    ),
                    None,
                )
            else:
                self.state["source_plan"] = _source_plan(source.text)
            return StageResponse("[[doc:historical-license-source]] Read historical source")
        if stage.stage_id == "source-review":
            if not any(receipt.record_id == "review-v" for receipt in stage.receipts):
                return StageResponse(
                    "Request source review",
                    (
                        Action(
                            "request_verification",
                            "review-v",
                            {"check": "review-complete", "subject": "reviewed"},
                        ),
                    ),
                )
            if not any(
                receipt.record_id == "review-v" and receipt.verdict == "pass"
                for receipt in stage.receipts
            ):
                return StageResponse("Source review did not pass")
            return StageResponse(
                "Finalize source review",
                (
                    Action("create_record", "source_review", {"plan": "reviewed"}),
                    Action("finalize", "source_review", {"status": "final"}, ("review-v",)),
                ),
            )
        if stage.stage_id == "pause-project":
            self.state["carry"] = {"source_plan": self.state.get("source_plan")}
        if stage.stage_id == "archive-request":
            self.state["request_seen"] = (
                len(stage.documents) == 1
                and "preferred, nondeprecated" in stage.documents[0].text
            )
        if stage.stage_id == "decide-license-format":
            carry = self.state.get("carry")
            plan = self.fixed_plan
            if plan is None and isinstance(carry, dict):
                candidate = carry.get("source_plan")
                plan = candidate if isinstance(candidate, str) else None
            if not self.state.get("request_seen") or plan is None:
                return StageResponse("No source-grounded format")
            if not any(receipt.record_id == "license-v" for receipt in stage.receipts):
                return StageResponse(
                    "Request license review",
                    (
                        Action(
                            "request_verification",
                            "license-v",
                            {"check": "license-review", "subject": plan},
                        ),
                    ),
                )
            if not any(
                receipt.record_id == "license-v" and receipt.verdict == "pass"
                for receipt in stage.receipts
            ):
                return StageResponse("License review did not pass")
            return StageResponse(
                "Finalize archival format",
                (
                    Action("create_record", "license_format_decision", {"plan": plan}),
                    Action(
                        "finalize",
                        "license_format_decision",
                        {"status": "final"},
                        ("license-v",),
                    ),
                ),
            )
        return StageResponse("Observed stage")


def _run(
    sessions: tuple[LifecycleInstance, LifecycleInstance],
    *,
    fixed_plan: str | None = None,
    identity_only: bool = False,
) -> tuple[SequenceRecord, ProjectState, list[_Witness]]:
    env = ProjectState()
    witnesses: list[_Witness] = []

    def factory(state: dict[str, object]) -> _Witness:
        witness = _Witness(state, fixed_plan=fixed_plan, identity_only=identity_only)
        witnesses.append(witness)
        return witness

    record = run_session_sequence(
        list(sessions),
        factory,
        envs=[env, env],
        budget=ToolBudget(max_calls=10),
        registry=DocumentRegistry(),
        max_turns_per_stage=3,
    )
    return record, env, witnesses


@pytest.mark.parametrize("variant", ("pep621", "pep639"))
def test_source_changes_complete_action_after_real_reset(
    source_root: Path, variant: SourceVariant
) -> None:
    sessions = build_pep_license_sessions(source_root, variant=variant)
    record, env, witnesses = _run(sessions)
    assert [session.passed for session in record.sessions] == [True, True], record.to_dict()
    assert env.records["license_format_decision"]["plan"] == _PLANS[variant]
    assert env.records["license-v"]["verdict"] == "pass"
    assert witnesses[0] is not witnesses[1]
    assert witnesses[1].initial_state == {"carry": {"source_plan": _PLANS[variant]}}
    assert witnesses[1].views[0].documents == ()
    assert all(
        not hasattr(view, "commit_precondition") for witness in witnesses for view in witness.views
    )


def test_matched_request_and_evaluator_private_opposite_oracles(source_root: Path) -> None:
    old = build_pep_license_sessions(source_root, variant="pep621")
    new = build_pep_license_sessions(source_root, variant="pep639")
    assert old[0].instance_id == new[0].instance_id
    assert old[1].instance_id == new[1].instance_id
    assert old[0].axes == new[0].axes
    assert old[1].axes == new[1].axes
    assert old[0].stages[1:] == new[0].stages[1:]
    assert old[1].stages[1].to_dict() == new[1].stages[1].to_dict()
    assert old[0].stages[0].documents[0].text != new[0].stages[0].documents[0].text
    old_oracle = old[1].stages[2].commit_precondition
    new_oracle = new[1].stages[2].commit_precondition
    assert old_oracle is not None and new_oracle is not None
    assert old_oracle != new_oracle
    assert old_oracle["legal_plans"] == ["license-table"]
    assert new_oracle["legal_plans"] == ["license-string"]


@pytest.mark.parametrize("fixed_plan", ("license-table", "license-string"))
def test_source_free_fixed_action_cannot_pass_both_versions(
    source_root: Path, fixed_plan: str
) -> None:
    outcomes = []
    for variant in ("pep621", "pep639"):
        first, second = build_pep_license_sessions(source_root, variant=variant)
        survey = first.stages[0]
        source = survey.documents[0]
        withheld = replace(
            source,
            title="Source withheld",
            text="[[doc:historical-license-source]] [source withheld]",
            source_url="benchmark:withheld",
        )
        first = replace(first, stages=(replace(survey, documents=(withheld,)), *first.stages[1:]))
        record, _env, _witnesses = _run((first, second), fixed_plan=fixed_plan)
        outcomes.append([session.passed for session in record.sessions])
    assert outcomes.count([True, True]) == 1
    assert outcomes.count([True, False]) == 1


@pytest.mark.parametrize("variant,pep_number", (("pep621", "621"), ("pep639", "639")))
def test_source_identity_alone_solves_both_versions(
    source_root: Path, variant: SourceVariant, pep_number: str
) -> None:
    first, second = build_pep_license_sessions(source_root, variant=variant)
    survey = first.stages[0]
    source = survey.documents[0]
    assert f"PEP: {pep_number}" in source.text
    assert source.source_url.endswith(f"/peps/pep-0{pep_number}.rst")
    identity_only = replace(
        source,
        text=(
            "[[doc:historical-license-source]] Pinned historical license metadata proposal\n"
            f"PEP: {pep_number}\n[all rule sections withheld]"
        ),
    )
    assert _source_plan(identity_only.text) is None
    first = replace(first, stages=(replace(survey, documents=(identity_only,)), *first.stages[1:]))
    record, env, witnesses = _run((first, second), identity_only=True)
    assert [session.passed for session in record.sessions] == [True, True], record.to_dict()
    assert env.records["license_format_decision"]["plan"] == _PLANS[variant]
    assert witnesses[1].initial_state == {"carry": {"source_plan": _PLANS[variant]}}


@pytest.mark.parametrize("variant", ("pep621", "pep639"))
def test_opposite_source_text_breaks_frozen_oracle(
    source_root: Path, variant: SourceVariant
) -> None:
    first, second = build_pep_license_sessions(source_root, variant=variant)
    other: SourceVariant = "pep639" if variant == "pep621" else "pep621"
    opposite_survey = build_pep_license_sessions(source_root, variant=other)[0].stages[0]
    opposite_source = opposite_survey.documents[0]
    survey = first.stages[0]
    changed = replace(
        first, stages=(replace(survey, documents=(opposite_source,)), *first.stages[1:])
    )
    record, env, _witnesses = _run((changed, second))
    assert [session.passed for session in record.sessions] == [True, False]
    assert env.records["license_format_decision"]["plan"] == _PLANS[other]
    assert env.records["license-v"]["verdict"] == "pass"


def test_pinned_bytes_manifest_and_drift_rejection(source_root: Path, tmp_path: Path) -> None:
    manifest = json.loads(
        (
            Path(__file__).resolve().parent.parent / "configs/r7_pep_source_manifest_v1.json"
        ).read_text()
    )
    assert manifest["source_revision"] == SOURCE_REVISION
    for variant, (relative, expected_hash) in SOURCE_FILES.items():
        raw = (source_root / relative).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected_hash
        assert manifest["selected_files"][relative]["sha256"] == expected_hash
        source = build_pep_license_sessions(source_root, variant=variant)[0].stages[0].documents[0]
        assert source.text.split("\n", 1)[1].encode() == raw
        assert SOURCE_REVISION in source.source_url
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"changed source")
        with pytest.raises(ValueError, match="pinned PEP source mismatch"):
            build_pep_license_sessions(tmp_path, variant=variant)


@pytest.mark.parametrize("relative,start_line,end_line,start_byte,end_byte,span_hash", _SPANS)
def test_documented_source_spans_match_exact_bytes(
    source_root: Path,
    relative: str,
    start_line: int,
    end_line: int,
    start_byte: int,
    end_byte: int,
    span_hash: str,
) -> None:
    raw = (source_root / relative).read_bytes()
    lines = raw.splitlines(keepends=True)
    actual_start = sum(len(line) for line in lines[: start_line - 1])
    actual_end = sum(len(line) for line in lines[:end_line])
    assert (actual_start, actual_end) == (start_byte, end_byte)
    assert hashlib.sha256(raw[start_byte:end_byte]).hexdigest() == span_hash


def test_unknown_variant_is_rejected(source_root: Path) -> None:
    with pytest.raises(ValueError, match="unsupported historical PEP source variant"):
        build_pep_license_sessions(source_root, variant="unknown")  # type: ignore[arg-type]
