"""Development-only two-session B card for KEP-753 resource ordering.

The scheduling request, node capacity, review receipts, and project records are
constructed benchmark state. This builder does not simulate a Kubernetes node.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from rsicontext.lifecycle.spec import DescriptionAxes, DocumentRef, LifecycleInstance, StageSpec

SOURCE_REVISION = "13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a"
SOURCE_FILES = {
    "keps/sig-node/753-sidecar-containers/README.md": (
        "ba9ef6b591cb626023c6e8a0c77cbc3f3cd2ede98d6ab3ff086e41ebef0cdf21"
    ),
    "keps/sig-node/753-sidecar-containers/kep.yaml": (
        "c991d242d163e88f933172239fa9e712351604448985a6fa302b0010b70cd2d3"
    ),
    "LICENSE": "b40930bbcf80744c86c46a12bc9da056641d722716c378f5659b9e555ef833e1",
}
_SOURCE_URL = (
    "https://github.com/kubernetes/enhancements/blob/"
    f"{SOURCE_REVISION}/keps/sig-node/753-sidecar-containers/README.md"
)
_FIRST = "resource_assessment"
_SECOND = "resource_reassessment"
_CHECK = "resource-review"
_HOLD = "hold-at-1000m"
_ADMIT = "admit-at-1000m"


def _pinned_source(source_root: Path) -> DocumentRef:
    source = b""
    for relative, expected in SOURCE_FILES.items():
        raw = (source_root / relative).read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected:
            raise ValueError(
                f"pinned KEP-753 source mismatch for {relative}: {actual} != {expected}"
            )
        if relative.endswith("README.md"):
            source = raw
    return DocumentRef(
        doc_id="kep753-resource-source",
        title="Pinned KEP-753 proposal and resource calculation",
        text="[[doc:kep753-resource-source]]\n" + source.decode("utf-8"),
        source_url=f"{_SOURCE_URL}#L761-L798",
        retrieved_date="2026-09-26",
    )


def _brief(doc_id: str, title: str, body: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n{body}",
        source_url="benchmark:constructed/kep753-resource-order-v1",
        retrieved_date="2026-09-26",
    )


def _decision_stage(*, record_id: str, legal: str, revision: int) -> StageSpec:
    return StageSpec(
        stage_id=f"decide-{record_id}",
        kind="act_verify",
        prompt_text=(
            f"Request a current {_CHECK} receipt for the chosen plan, inspect the "
            f"receipt, then finalize {record_id} with that evidence. The review "
            "receipt confirms procedure only, not the CPU calculation."
        ),
        documents=(),
        gold_evidence_ids=(),
        expected_state_delta={record_id: {"status": "final"}},
        commit_precondition={
            "record_id": record_id,
            **({"prior_finalized_record": _FIRST} if record_id == _SECOND else {}),
            "plan_field": "plan",
            "legal_plans": [legal],
            "plan_requirements": {
                _HOLD: {"requires_check": _CHECK},
                _ADMIT: {"requires_check": _CHECK},
            },
            "current_revision": revision,
            "revision_scope": [_CHECK],
        },
        verification_oracle={_CHECK: {_HOLD: True, _ADMIT: True}},
    )


def build_k8s_resource_order_sessions(
    source_root: Path,
) -> tuple[LifecycleInstance, LifecycleInstance]:
    """Build a source-dependent capacity reassessment across one reset."""

    source = _pinned_source(source_root)
    first_brief = _brief(
        "resource-request",
        "Constructed scheduling request",
        (
            "BENCHMARK SANDBOX ONLY. Apply the supplied KEP proposal's effective "
            "CPU-request formula to this new Pod; this is an estimate, not an "
            "observation of a running scheduler. Pod overhead is 0m. The node "
            "has 1000m CPU request capacity. Ordered initContainers: native "
            "sidecar S requests 300m; regular init A requests 800m; regular "
            "init B requests 500m. The regular application container requests "
            "400m. Choose plan=admit-at-1000m only if the Pod's effective CPU "
            "request is at most 1000m; otherwise choose plan=hold-at-1000m. "
            "Create and finalize project-state record resource_assessment "
            "with the chosen plan after a current resource-review receipt."
        ),
    )
    amendment = _brief(
        "resource-order-amendment",
        "Constructed scheduling-order amendment",
        (
            "The project moves regular init A before native sidecar S. Ordered "
            "initContainers are now A (800m), S (300m), B (500m). The application "
            "remains 400m, node capacity remains 1000m, and Pod overhead remains "
            "0m. Recalculate using the supplied KEP formula; earlier resource-review "
            "receipts are stale under revision 2. Choose admit-at-1000m only if "
            "the new effective CPU request is at most 1000m; otherwise choose "
            "hold-at-1000m. Finalize resource_reassessment only after the prior "
            "resource_assessment was finalized and a new resource-review receipt "
            "has been issued for the chosen plan."
        ),
    )
    axes = DescriptionAxes(
        information_scale_tokens=len(source.text.split()),
        dependency_distance_stages=2,
        persistence_span_resets=1,
        action_dependency="strong",
        environment_changes=1,
    )
    sandbox = {
        "records": [_FIRST, _SECOND],
        "action_kinds": ["create_record", "finalize", "request_verification"],
    }
    first = LifecycleInstance(
        instance_id="research-v5-kep753-resource-order-s1-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="resource-source-survey",
                kind="survey",
                prompt_text="Review the pinned KEP proposal and its resource calculation.",
                documents=(source,),
                gold_evidence_ids=(source.doc_id,),
            ),
            StageSpec(
                stage_id="resource-request-stage",
                kind="constraint_injection",
                prompt_text="Apply the constructed scheduling request.",
                documents=(first_brief,),
                gold_evidence_ids=(),
            ),
            _decision_stage(record_id=_FIRST, legal=_HOLD, revision=1),
            StageSpec(
                stage_id="resource-s1-end",
                kind="session_end",
                prompt_text="Session ends; retain only permitted carry state.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=axes,
        answer_norm="kep753-resource-order-conditional",
        sandbox_spec=sandbox,
    )
    second = LifecycleInstance(
        instance_id="research-v5-kep753-resource-order-s2-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="resource-s2-start",
                kind="session_start",
                prompt_text="Resume the same project after a process reset.",
                documents=(),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="resource-order-change",
                kind="rule_change",
                prompt_text="Apply the attached scheduling-order amendment.",
                documents=(amendment,),
                gold_evidence_ids=(),
                rule_change_effect=2,
                rule_change_scope=(_CHECK,),
            ),
            _decision_stage(record_id=_SECOND, legal=_ADMIT, revision=2),
            StageSpec(
                stage_id="resource-s2-end",
                kind="session_end",
                prompt_text="Session ends.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=axes,
        answer_norm="kep753-resource-order-conditional",
        sandbox_spec=sandbox,
    )
    return first, second


__all__ = ["SOURCE_FILES", "SOURCE_REVISION", "build_k8s_resource_order_sessions"]
