"""Behavioral development checks for the independent KEP-753 parent."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_k8s_parent import SOURCE_SHA256, build_k8s_sidecar_sessions
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle
from rsicontext.lifecycle.spec import DocumentRef


def _verify(record_id: str, check: str, subject: str) -> Action:
    return Action(
        kind="request_verification",
        record_id=record_id,
        fields={"check": check, "subject": subject},
    )


def _commit(record_id: str, plan: str, verification: str) -> tuple[Action, Action]:
    return (
        Action(kind="create_record", record_id=record_id, fields={"plan": plan}),
        Action(
            kind="finalize",
            record_id=record_id,
            fields={"status": "final"},
            provenance=(verification,),
        ),
    )


class ReferenceHook:
    """A test skeleton that chooses from visible source text and receipts."""

    def __init__(
        self, *, carry: dict[str, object] | None = None, stale_readiness: bool = False
    ) -> None:
        self.source_text: dict[str, str] = {}
        self.carry = dict(carry or {})
        self.amendment_text = ""
        self.first_step = 0
        self.stale_readiness = stale_readiness

    def on_stage(self, stage: StageView) -> StageResponse:
        self.source_text.update(
            (document.doc_id, document.text)
            for document in stage.documents
            if document.doc_id.startswith("kep753-")
        )
        if stage.stage_id == "kep753-readiness-change":
            self.amendment_text = "\n".join(document.text for document in stage.documents)
        if stage.stage_id == "kep753-s1-end":
            self.carry["probe_supported"] = (
                "readiness probes contribute to whole-Pod readiness"
                in self.source_text.get("kep753-readiness", "")
            )
        if stage.stage_id == "kep753-first-rollout":
            if self.first_step == 0:
                self.first_step = 1
                return StageResponse(
                    "probe ordinary helper",
                    (_verify("verify-regular", "job-completion", "regular-companion"),),
                )
            if self.first_step == 1:
                assert any(r.verdict == "fail" for r in stage.receipts)
                self.first_step = 2
                if (
                    "restartPolicy=Always" in self.source_text.get("kep753-native-semantics", "")
                    and "keep a Job pod" in self.source_text.get("kep753-job-problem", "")
                    and "do not block Pod completion"
                    in self.source_text.get("kep753-job-completion", "")
                ):
                    return StageResponse(
                        "switch after failure",
                        (_verify("verify-native", "job-completion", "native-sidecar"),),
                    )
                self.first_step = 3
                return StageResponse(
                    "source missing",
                    _commit("sidecar_rollout", "regular-companion", "verify-regular"),
                )
            if self.first_step == 2:
                passing = [r for r in stage.receipts if r.verdict == "pass"]
                assert passing
                self.first_step = 3
                self.carry["first_plan"] = passing[0].subject
                return StageResponse(
                    "commit passing plan",
                    _commit("sidecar_rollout", passing[0].subject, "verify-native"),
                )
        if stage.stage_id == "kep753-readiness-rollout":
            first_plan = self.carry.get("first_plan")
            plan = first_plan if isinstance(first_plan, str) else "unresolved-plan"
            if (
                self.carry.get("probe_supported")
                and "requires a readiness probe" in self.amendment_text
            ):
                plan += "-with-probe"
            if self.stale_readiness:
                return StageResponse(
                    "reuse old receipt",
                    _commit("readiness_rollout", plan, "verify-ready-old"),
                )
            return StageResponse(
                "verify current readiness",
                (
                    _verify("verify-ready-current", "readiness-contract", plan),
                    *_commit("readiness_rollout", plan, "verify-ready-current"),
                ),
            )
        return StageResponse(
            "read source " + " ".join(f"[[doc:{d.doc_id}]]" for d in stage.documents)
        )


def test_reference_recovery_and_later_rollout_pass() -> None:
    first, second = build_k8s_sidecar_sessions()
    env = ProjectState()
    first_hook = ReferenceHook()
    first_result = run_lifecycle(first, first_hook, env, max_turns_per_stage=4)
    assert first_hook.carry == {"first_plan": "native-sidecar", "probe_supported": True}
    second_result = run_lifecycle(second, ReferenceHook(carry=first_hook.carry), env)
    assert first_result.final_check.passed
    assert second_result.final_check.passed
    assert env.records["verify-regular"]["verdict"] == "fail"
    assert env.records["verify-native"]["verdict"] == "pass"
    assert env.records["verify-ready-current"]["protocol_revision"] == 2
    assert env.check_revisions == {"readiness-contract": 2}


def test_later_rollout_fails_without_prior_finalize_even_if_repaired_in_session() -> None:
    _, second = build_k8s_sidecar_sessions()
    env = ProjectState()
    # A participant-authored or same-session record cannot satisfy the
    # environment's entry snapshot of earlier finalizations.
    env.apply(Action(kind="create_record", record_id="sidecar_rollout", fields={"status": "final"}))
    result = run_lifecycle(second, ReferenceHook(), env)
    assert not result.final_check.passed
    assert any("absent at session start" in failure for failure in result.final_check.failures)

    class LateRepairHook(ReferenceHook):
        def on_stage(self, stage: StageView) -> StageResponse:
            if stage.kind == "session_start":
                return StageResponse(
                    "late repair",
                    (
                        Action(
                            kind="create_record",
                            record_id="sidecar_rollout",
                            fields={"plan": "native-sidecar"},
                        ),
                        Action(
                            kind="finalize",
                            record_id="sidecar_rollout",
                            fields={},
                            provenance=("late-note",),
                        ),
                    ),
                )
            return super().on_stage(stage)

    late_env = ProjectState()
    late_result = run_lifecycle(second, LateRepairHook(), late_env)
    assert "sidecar_rollout" in late_env.finalized_record_ids
    assert not late_result.final_check.passed
    assert any("absent at session start" in failure for failure in late_result.final_check.failures)


def test_readiness_evidence_must_be_current_after_scoped_change() -> None:
    first, second = build_k8s_sidecar_sessions()
    env = ProjectState()
    first_hook = ReferenceHook()
    assert run_lifecycle(first, first_hook, env, max_turns_per_stage=4).final_check.passed
    env.apply(_verify("verify-ready-old", "readiness-contract", "native-sidecar-with-probe"))
    assert env.records["verify-ready-old"]["protocol_revision"] == 1
    result = run_lifecycle(second, ReferenceHook(carry=first_hook.carry, stale_readiness=True), env)
    assert not result.final_check.passed
    assert any("stale" in failure for failure in result.final_check.failures)
    assert env.check_revisions == {"readiness-contract": 2}


def test_removing_load_bearing_source_breaks_reference_path() -> None:
    first, _ = build_k8s_sidecar_sessions()
    survey = first.stages[0]
    for removed in (
        "kep753-native-semantics",
        "kep753-job-problem",
        "kep753-job-completion",
    ):
        changed_survey = replace(
            survey,
            documents=tuple(doc for doc in survey.documents if doc.doc_id != removed),
            gold_evidence_ids=tuple(
                doc_id for doc_id in survey.gold_evidence_ids if doc_id != removed
            ),
        )
        changed = replace(first, stages=(changed_survey, *first.stages[1:]))
        result = run_lifecycle(changed, ReferenceHook(), ProjectState(), max_turns_per_stage=4)
        assert not result.final_check.passed
        assert any("passing verdict" in failure for failure in result.final_check.failures)


def test_missing_readiness_source_breaks_later_derived_plan() -> None:
    first, second = build_k8s_sidecar_sessions()
    assert "native-sidecar-with-probe" not in " ".join(stage.prompt_text for stage in second.stages)
    survey = first.stages[0]
    changed_survey = replace(
        survey,
        documents=tuple(doc for doc in survey.documents if doc.doc_id != "kep753-readiness"),
        gold_evidence_ids=tuple(
            doc_id for doc_id in survey.gold_evidence_ids if doc_id != "kep753-readiness"
        ),
    )
    changed = replace(first, stages=(changed_survey, *first.stages[1:]))
    env = ProjectState()
    first_hook = ReferenceHook()
    assert run_lifecycle(changed, first_hook, env, max_turns_per_stage=4).final_check.passed
    assert first_hook.carry["probe_supported"] is False
    later = run_lifecycle(second, ReferenceHook(carry=first_hook.carry), env)
    assert not later.final_check.passed
    assert any("not in the legal set" in failure for failure in later.final_check.failures)


def test_irrelevant_survey_note_preserves_reference_decisions() -> None:
    first, second = build_k8s_sidecar_sessions()
    survey = first.stages[0]
    extra = DocumentRef(
        doc_id="meeting-index",
        title="Administrative index",
        text="[[doc:meeting-index]] Meeting room and calendar contacts only.",
        source_url="benchmark:constructed-irrelevant-note",
    )
    perturbed = replace(
        first,
        stages=(replace(survey, documents=(*survey.documents, extra)), *first.stages[1:]),
    )
    original_env = ProjectState()
    changed_env = ProjectState()
    original_hook = ReferenceHook()
    changed_hook = ReferenceHook()
    original = run_lifecycle(first, original_hook, original_env, max_turns_per_stage=4)
    changed = run_lifecycle(perturbed, changed_hook, changed_env, max_turns_per_stage=4)
    original_followup = run_lifecycle(
        second, ReferenceHook(carry=original_hook.carry), original_env
    )
    changed_followup = run_lifecycle(second, ReferenceHook(carry=changed_hook.carry), changed_env)
    assert (original.final_check.passed, original_followup.final_check.passed) == (True, True)
    assert (changed.final_check.passed, changed_followup.final_check.passed) == (True, True)
    assert (
        original_env.records["sidecar_rollout"]["plan"]
        == changed_env.records["sidecar_rollout"]["plan"]
    )
    assert (
        original_env.records["readiness_rollout"]["plan"]
        == changed_env.records["readiness_rollout"]["plan"]
    )


def test_builder_is_deterministic_and_source_hash_is_pinned() -> None:
    worlds = build_k8s_sidecar_sessions()
    encoded = json.dumps(
        [world.to_dict() for world in worlds], sort_keys=True, separators=(",", ":")
    )
    assert hashlib.sha256(encoded.encode()).hexdigest() == (
        "9409175713220777bc7ec70683dd3270cead3ac00afd9b431e0cf98fd4b94de7"
    )
    source = Path(
        "/volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753/"
        "keps/sig-node/753-sidecar-containers/README.md"
    )
    if source.exists():
        assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA256
    assert len(SOURCE_SHA256) == 64
