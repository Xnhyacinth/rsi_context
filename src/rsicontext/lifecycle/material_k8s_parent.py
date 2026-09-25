"""Development-only C candidate grounded in pinned Kubernetes KEP-753.

The KEP supplies container semantics. The batch rollout, verification service,
and readiness-policy amendment are constructed benchmark scenarios, not claims
that the upstream project approved a particular deployment.
"""

from __future__ import annotations

from rsicontext.lifecycle.spec import DescriptionAxes, DocumentRef, LifecycleInstance, StageSpec

_SOURCE = (
    "https://github.com/kubernetes/enhancements/blob/"
    "13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a/"
    "keps/sig-node/753-sidecar-containers/README.md"
)
SOURCE_SHA256 = "ba9ef6b591cb626023c6e8a0c77cbc3f3cd2ede98d6ab3ff086e41ebef0cdf21"
_FIRST = "sidecar_rollout"
_SECOND = "readiness_rollout"
_JOB_CHECK = "job-completion"
_READY_CHECK = "readiness-contract"
_NATIVE = "native-sidecar"
_REGULAR = "regular-companion"
_PROBED = "native-sidecar-with-probe"


def _source_doc(doc_id: str, title: str, text: str, lines: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n{text}",
        source_url=f"{_SOURCE}#L{lines}",
        retrieved_date="2026-09-25",
    )


def _scenario_doc(doc_id: str, title: str, text: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n{text}",
        source_url="benchmark:constructed-kep753-batch-rollout-v1",
        retrieved_date="2026-09-25",
    )


def build_k8s_sidecar_sessions() -> tuple[LifecycleInstance, LifecycleInstance]:
    """Build one independent, two-session *development* candidate.

    The environment's pass/fail decisions remain evaluator-side; they are
    deliberately absent from participant-visible documents and prompts.
    """

    semantics = _source_doc(
        "kep753-native-semantics",
        "KEP-753 native sidecar semantics",
        (
            "The proposal marks an init container as a sidecar with "
            "restartPolicy=Always. Startup ordering waits for Started, rather "
            "than for that container to exit. This is distinct from placing "
            "a continuously running helper in ordinary containers."
        ),
        "368-L383",
    )
    problem = _source_doc(
        "kep753-job-problem",
        "KEP-753 ordinary companion problem",
        (
            "A continuously running ordinary companion can keep a Job pod "
            "from finishing after the main worker exits."
        ),
        "249-L263",
    )
    completion = _source_doc(
        "kep753-job-completion",
        "KEP-753 Job completion behavior",
        (
            "Native sidecars do not block Pod completion; the sidecar is "
            "terminated after all regular containers finish."
        ),
        "391-L397",
    )
    readiness = _source_doc(
        "kep753-readiness",
        "KEP-753 readiness semantics",
        (
            "Native sidecars support startup, readiness, and liveness probes. "
            "Their readiness probes contribute to whole-Pod readiness."
        ),
        "407-L411",
    )
    project = _scenario_doc(
        "batch-job-brief",
        "Constructed batch rollout brief",
        (
            "A batch worker exits after processing. Its continuously running "
            "log forwarder must start before the worker and must not prevent "
            "Job completion. Two implementation sketches are on the table: "
            "regular-companion and native-sidecar. The design notes above "
            "define what those implementations mean. A future probe variant "
            "is named by appending '-with-probe' to the selected plan id. "
            "The rollout is permitted only after an environment-issued "
            "job-completion verification passes."
        ),
    )
    constraint = _scenario_doc(
        "job-completion-policy",
        "Constructed first rollout policy",
        (
            "Finalize sidecar_rollout only for a plan with a passing current "
            "job-completion verification. The environment issues the verdict; "
            "source prose alone cannot substitute for that result."
        ),
    )
    mutation = _scenario_doc(
        "readiness-amendment",
        "Constructed readiness-policy amendment",
        (
            "After the first rollout is finalized, a new operational rule "
            "requires a readiness probe for the log forwarder before opening "
            "traffic. The readiness-contract check advances to revision 2; "
            "job-completion is outside this amendment's scope. Finalize "
            "readiness_rollout only after a new passing readiness-contract "
            "verification at revision 2."
        ),
    )

    first = LifecycleInstance(
        instance_id="research-v5-kep753-sidecar-s1-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="kep753-survey",
                kind="survey",
                prompt_text="Review the KEP excerpts and constructed batch rollout brief.",
                documents=(semantics, problem, completion, readiness, project),
                gold_evidence_ids=(
                    semantics.doc_id,
                    problem.doc_id,
                    completion.doc_id,
                    readiness.doc_id,
                    project.doc_id,
                ),
            ),
            StageSpec(
                stage_id="kep753-constraint",
                kind="constraint_injection",
                prompt_text="Apply the attached first rollout policy before writing the record.",
                documents=(constraint,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="kep753-first-rollout",
                kind="act_verify",
                prompt_text=(
                    "Request job-completion verifications, inspect their receipts, "
                    "and finalize sidecar_rollout with the passing plan and "
                    "environment-issued evidence. A failing candidate may be replaced."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_FIRST: {"status": "final"}},
                commit_precondition={
                    "record_id": _FIRST,
                    "plan_field": "plan",
                    "legal_plans": [_REGULAR, _NATIVE],
                    "plan_requirements": {
                        plan: {"domain": "batch-job", "requires_check": _JOB_CHECK}
                        for plan in (_REGULAR, _NATIVE)
                    },
                    "current_revision": 1,
                    "revision_scope": [_JOB_CHECK],
                },
                verification_oracle={
                    _JOB_CHECK: {_REGULAR: False, _NATIVE: True},
                    _READY_CHECK: {_PROBED: True},
                },
            ),
            StageSpec(
                stage_id="kep753-s1-end",
                kind="session_end",
                prompt_text="Session ends; retain only permitted carry state.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=sum(
                len(doc.text.split())
                for doc in (semantics, problem, completion, readiness, project)
            ),
            dependency_distance_stages=2,
            persistence_span_resets=1,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm=_NATIVE,
        sandbox_spec={
            "records": [_FIRST, _SECOND],
            "action_kinds": ["create_record", "finalize", "request_verification"],
        },
    )
    second = LifecycleInstance(
        instance_id="research-v5-kep753-sidecar-s2-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="kep753-s2-start",
                kind="session_start",
                prompt_text="Resume the batch rollout; consult the prior finalized record.",
                documents=(),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="kep753-readiness-change",
                kind="rule_change",
                prompt_text="Apply the attached operational readiness amendment.",
                documents=(mutation,),
                gold_evidence_ids=(),
                rule_change_effect=2,
                rule_change_scope=(_READY_CHECK,),
            ),
            StageSpec(
                stage_id="kep753-readiness-rollout",
                kind="act_verify",
                prompt_text=(
                    "Only an already-finalized sidecar_rollout permits this step. "
                    "Request a current readiness-contract verification and finalize "
                    "readiness_rollout for the plan derived from the prior "
                    "rollout, the source material, and the amendment."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_SECOND: {"status": "final"}},
                commit_precondition={
                    "record_id": _SECOND,
                    "prior_finalized_record": _FIRST,
                    "plan_field": "plan",
                    "legal_plans": [_PROBED],
                    "plan_requirements": {
                        _PROBED: {"domain": "batch-job", "requires_check": _READY_CHECK}
                    },
                    "current_revision": 2,
                    "revision_scope": [_READY_CHECK],
                },
                verification_oracle={_READY_CHECK: {_PROBED: True}},
            ),
            StageSpec(
                stage_id="kep753-s2-end",
                kind="session_end",
                prompt_text="Session ends; retain only permitted carry state.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=len(mutation.text.split()),
            dependency_distance_stages=2,
            persistence_span_resets=1,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm=_PROBED,
        sandbox_spec={
            "records": [_FIRST, _SECOND],
            "action_kinds": ["create_record", "finalize", "request_verification"],
        },
    )
    return first, second
