"""Two-session PEP 1 process task over one pinned historical source file.

The PEP text supplies status semantics. The review board, authorizations,
verification service, records, and later work request are constructed
benchmark material; this world does not assign a status to a real PEP.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from rsicontext.lifecycle.spec import DescriptionAxes, DocumentRef, LifecycleInstance, StageSpec

SOURCE_REVISION = "6822259db9c95f02da739b3e2830a4aa1ae35134"
SOURCE_SHA256 = "c2bc2ce666758fa82ee2592926218d710e6fdddc674d78314bd6b56c392c46f6"
SOURCE_RELATIVE = "peps/pep-0001.rst"
_SOURCE_URL = "https://github.com/python/peps/blob/" + SOURCE_REVISION + "/" + SOURCE_RELATIVE
_DATE = "2026-09-26"
_FIRST = "status_decision"
_SECOND = "next_step_plan"
_ACCEPTED = "accepted"
_PROVISIONAL = "provisional"
_IMPLEMENT = "complete-reference-implementation"
_FEEDBACK = "collect-interface-feedback"


def _constructed(doc_id: str, title: str, body: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\nBENCHMARK SANDBOX ONLY. {body}",
        source_url="benchmark:constructed/pep-process-b-v1",
        retrieved_date=_DATE,
    )


def build_pep_process_b_sessions(source_root: Path) -> tuple[LifecycleInstance, LifecycleInstance]:
    """Build one unqualified B development world from exact PEP 1 bytes."""

    raw = (source_root / SOURCE_RELATIVE).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != SOURCE_SHA256:
        raise ValueError(f"pinned PEP 1 source mismatch: {actual} != {SOURCE_SHA256}")
    source = DocumentRef(
        doc_id="pep1-process-full",
        title="PEP 1 process text at the pinned revision (complete file)",
        text="[[doc:pep1-process-full]] PEP 1 process text\n" + raw.decode("utf-8"),
        source_url=_SOURCE_URL,
        retrieved_date=_DATE,
    )
    charter = _constructed(
        "local-status-charter",
        "Mock board status charter",
        "The mock process board permits either of two simulated status paths "
        "for this single proposal: Accepted or Provisional. The choice is "
        "discretionary for this sandbox; neither path asserts a real PEP "
        "decision. Choose one, request status-clearance for that status, "
        "inspect its environment receipt, and finalize status_decision "
        "citing the passing receipt. Apply the pinned PEP 1 process text "
        "when a later task asks what this status entails.",
    )
    later_request = _constructed(
        "local-next-step-request",
        "Mock board next-step request",
        "The same proposal resumes after a session reset. A next-step plan "
        "must follow the earlier finalized status under the pinned PEP 1 "
        "process text. The sandbox's two action codes are "
        "complete-reference-implementation and collect-interface-feedback. "
        "Choose the one justified by the earlier status; request "
        "next-step-clearance for it and finalize next_step_plan with "
        "that environment-issued passing receipt as provenance.",
    )
    first = LifecycleInstance(
        instance_id="research-v5-pep-process-b-s1-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="pep-process-review",
                kind="survey",
                prompt_text=(
                    "Read the complete pinned historical PEP 1 process text. "
                    "Retain what Accepted and Provisional imply for later work."
                ),
                documents=(source,),
                gold_evidence_ids=(source.doc_id,),
            ),
            StageSpec(
                stage_id="mock-status-charter",
                kind="constraint_injection",
                prompt_text="Read the constructed mock board's choice and receipt rule.",
                documents=(charter,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="pep-status-decision",
                kind="act_verify",
                prompt_text=(
                    "Select either authorized simulated status. Request status-clearance, "
                    "inspect its receipt, then finalize status_decision with the chosen "
                    "status as plan and the passing environment receipt as provenance."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_FIRST: {"status": "final"}},
                commit_precondition={
                    "record_id": _FIRST,
                    "plan_field": "plan",
                    "legal_plans": [_ACCEPTED, _PROVISIONAL],
                    "plan_requirements": {
                        _ACCEPTED: {"requires_check": "status-clearance"},
                        _PROVISIONAL: {"requires_check": "status-clearance"},
                    },
                },
                verification_oracle={"status-clearance": {_ACCEPTED: True, _PROVISIONAL: True}},
            ),
            StageSpec(
                stage_id="pep-s1-end",
                kind="session_end",
                prompt_text="Session ends. Only the bounded carry subtree persists.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=len(source.text.split()) + len(charter.text.split()),
            dependency_distance_stages=4,
            persistence_span_resets=1,
            action_dependency="strong",
            environment_changes=0,
        ),
        answer_norm=_ACCEPTED,
        answer_aliases=(_ACCEPTED, _PROVISIONAL),
        sandbox_spec={
            "records": [_FIRST, _SECOND],
            "action_kinds": ["create_record", "finalize", "request_verification"],
        },
    )
    second = LifecycleInstance(
        instance_id="research-v5-pep-process-b-s2-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="pep-s2-start",
                kind="session_start",
                prompt_text=(
                    "Resume the same simulated proposal. The previous finalized status "
                    "and its evidence are in the project sandbox; only carry survives "
                    "in policy state. Prior source may be reread at metered cost."
                ),
                documents=(),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="pep-next-step-request",
                kind="constraint_injection",
                prompt_text="Read the mock board's next-step request.",
                documents=(later_request,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="pep-next-step-decision",
                kind="act_verify",
                prompt_text=(
                    "Use the earlier finalized status and PEP 1 process evidence to choose "
                    "the next legal action. Request next-step-clearance, inspect its "
                    "receipt, and finalize next_step_plan citing the passing receipt."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_SECOND: {"status": "final"}},
                commit_precondition={
                    "record_id": _SECOND,
                    "prior_finalized_record": _FIRST,
                    "prior_verification": {
                        "check": "status-clearance",
                        "plan_field": "plan",
                        "allowed_later_plans": {
                            _ACCEPTED: [_IMPLEMENT],
                            _PROVISIONAL: [_FEEDBACK],
                        },
                    },
                    "plan_field": "plan",
                    "legal_plans": [_IMPLEMENT, _FEEDBACK],
                    "plan_requirements": {
                        _IMPLEMENT: {"requires_check": "next-step-clearance"},
                        _FEEDBACK: {"requires_check": "next-step-clearance"},
                    },
                },
                verification_oracle={"next-step-clearance": {_IMPLEMENT: True, _FEEDBACK: True}},
            ),
            StageSpec(
                stage_id="pep-s2-end",
                kind="session_end",
                prompt_text="Session ends. Only carry persists.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=len(later_request.text.split()),
            dependency_distance_stages=4,
            persistence_span_resets=1,
            action_dependency="strong",
            environment_changes=0,
        ),
        answer_norm=_IMPLEMENT,
        answer_aliases=(_IMPLEMENT, _FEEDBACK),
        sandbox_spec={
            "records": [_FIRST, _SECOND],
            "action_kinds": ["create_record", "finalize", "request_verification"],
        },
    )
    return first, second


__all__ = ["SOURCE_RELATIVE", "SOURCE_REVISION", "SOURCE_SHA256", "build_pep_process_b_sessions"]
