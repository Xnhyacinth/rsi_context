"""Construction and causality checks for the OTel development parent."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_otel_parent import build_otel_database_migration_parent
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle
from rsicontext.lifecycle.spec import DocumentRef, LifecycleInstance

_UPSTREAM = Path("/volume/pt-dev/qjiu/rsi_context_external/data/otel-semconv-v1.43.0")
_EXPECTED_SHA = {
    "docs/db/database-spans.md": "1f94aa548e00736bcf7e580318f868eeac36acfdb3e1cb9919da7e02f90e4c91",
    "docs/db/sql.md": "e451e533f90fbcc01ecc23f6d60aaa49d249dad79227f79ddeef548288eb32ea",
}


class _TextFollowingReference:
    """Minimal construction witness using only StageView material and carry."""

    def __init__(self) -> None:
        self.source_text = ""
        self.plan = "unknown"
        self.query_status = "unknown"

    def on_stage(self, stage: StageView) -> StageResponse:
        if stage.kind == "survey":
            self.source_text = "\n".join(doc.text for doc in stage.documents)
            return StageResponse(" ".join(doc.text.splitlines()[0] for doc in stage.documents))
        if stage.kind == "constraint_injection":
            # Derive the option from the source proposition plus the local
            # constraint. The absent-source intervention leaves it unknown.
            local = " ".join(doc.text for doc in stage.documents)
            if "`database/dup` - emit both" in self.source_text and "BOTH the legacy" in local:
                self.plan = "database/dup"
            return StageResponse(f"selected={self.plan}")
        if stage.kind == "act_verify":
            if self.plan == "unknown":
                return StageResponse("No supported migration choice")
            return StageResponse(
                f"commit {self.plan}",
                (
                    Action(
                        kind="request_verification",
                        record_id="otel-dual-receipt",
                        fields={"check": "dual-emission", "subject": self.plan},
                    ),
                    Action(
                        kind="create_record",
                        record_id="otel-candidate",
                        fields={"plan": self.plan, "domain": "telemetry"},
                    ),
                    Action(
                        kind="create_record",
                        record_id="migration_commit",
                        fields={"plan": self.plan},
                    ),
                    Action(
                        kind="finalize",
                        record_id="migration_commit",
                        fields={"plan": self.plan, "status": "final"},
                        provenance=("otel-dual-receipt", "otel-candidate"),
                    ),
                ),
            )
        if stage.kind == "follow_up":
            proposal = " ".join(doc.text for doc in stage.documents)
            if (
                "Non-parameterized query text SHOULD NOT be collected by default"
                in self.source_text
                and "no sanitizer" in proposal
            ):
                self.query_status = "hold"
            if self.query_status == "unknown":
                return StageResponse("Source insufficient for query text decision")
            return StageResponse(
                f"query text status={self.query_status}",
                (
                    Action(
                        kind="create_record",
                        record_id="query_text_decision",
                        fields={"status": self.query_status},
                    ),
                ),
            )
        return StageResponse("No write")


def _run(world: LifecycleInstance) -> tuple[bool, str, str, tuple[str, ...]]:
    reference = _TextFollowingReference()
    record = run_lifecycle(world, reference, ProjectState())
    return (
        record.final_check.passed,
        reference.plan,
        reference.query_status,
        record.final_check.failures,
    )


def _without_survey_doc(world: LifecycleInstance, doc_id: str) -> LifecycleInstance:
    stages = list(world.stages)
    survey = stages[0]
    stages[0] = replace(
        survey,
        documents=tuple(doc for doc in survey.documents if doc.doc_id != doc_id),
        gold_evidence_ids=tuple(eid for eid in survey.gold_evidence_ids if eid != doc_id),
    )
    return replace(world, stages=tuple(stages))


def test_reference_path_uses_both_source_propositions() -> None:
    world = build_otel_database_migration_parent()
    passed, plan, query_status, failures = _run(world)
    assert (passed, plan, query_status, failures) == (True, "database/dup", "hold", ())
    assert [stage.kind for stage in world.stages] == [
        "survey",
        "constraint_injection",
        "delegation",
        "rule_change",
        "act_verify",
        "follow_up",
    ]


@pytest.mark.parametrize(
    ("doc_id", "expected_plan", "expected_query"),
    [
        ("otel-db-modes", "unknown", "hold"),
        ("otel-sql-query-text", "database/dup", "unknown"),
    ],
)
def test_removing_a_decisive_source_breaks_its_downstream_decision(
    doc_id: str, expected_plan: str, expected_query: str
) -> None:
    result = _run(_without_survey_doc(build_otel_database_migration_parent(), doc_id))
    assert result[0] is False
    assert result[1:3] == (expected_plan, expected_query)


def test_removing_environment_validation_breaks_commit_gate() -> None:
    world = build_otel_database_migration_parent()
    stages = list(world.stages)
    award = stages[4]
    stages[4] = replace(award, verification_oracle={"dual-emission": {"database/dup": False}})
    passed, plan, status, failures = _run(replace(world, stages=tuple(stages)))
    assert (passed, plan, status) == (False, "database/dup", "hold")
    assert any("verification" in failure for failure in failures)


def test_irrelevant_perturbation_keeps_reference_decisions() -> None:
    world = build_otel_database_migration_parent()
    stages = list(world.stages)
    survey = stages[0]
    index = DocumentRef(
        doc_id="local-page-index",
        title="Constructed page index",
        text="Page numbering and stylesheet only; no migration or query text rule.",
        source_url="benchmark:constructed/irrelevant-index",
    )
    stages[0] = replace(survey, documents=(*survey.documents, index))
    assert _run(replace(world, stages=tuple(stages))) == _run(world)


def test_pinned_source_hashes_and_exact_excerpt_spans() -> None:
    if not _UPSTREAM.exists():
        pytest.skip("pinned external source checkout unavailable")
    world = build_otel_database_migration_parent()
    source_docs = {doc.doc_id: doc for doc in world.stages[0].documents}
    for path, expected in _EXPECTED_SHA.items():
        source = _UPSTREAM / path
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
    migration = (_UPSTREAM / "docs/db/database-spans.md").read_text()
    query = (_UPSTREAM / "docs/db/sql.md").read_text()
    assert source_docs["otel-db-modes"].text.split("\n", 1)[1] in migration
    assert source_docs["otel-sql-query-text"].text.split("\n", 1)[1] in query


def test_builder_is_deterministic_and_evaluator_fields_stay_out_of_stage_view() -> None:
    first = build_otel_database_migration_parent()
    second = build_otel_database_migration_parent()
    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(
        second.to_dict(), sort_keys=True
    )

    class _BoundaryWitness(_TextFollowingReference):
        def on_stage(self, stage: StageView) -> StageResponse:
            assert not hasattr(stage, "gold_evidence_ids")
            assert not hasattr(stage, "expected_state_delta")
            assert not hasattr(stage, "commit_precondition")
            assert not hasattr(stage, "verification_oracle")
            return super().on_stage(stage)

    assert run_lifecycle(first, _BoundaryWitness(), ProjectState()).final_check.passed
