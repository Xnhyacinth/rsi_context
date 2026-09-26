"""Unqualified two-session Kafka consumer-protocol migration candidate.

Only the protocol Markdown is upstream material. The group, preference,
review service, records, and alternative rule are constructed benchmark data.
The alternative is a causal diagnostic, never an Apache Kafka revision.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from rsicontext.lifecycle.spec import DescriptionAxes, DocumentRef, LifecycleInstance, StageSpec

SOURCE_REVISION = "379dba2230101f7ca1b73658808d67e6e48bf909"
SOURCE_RELATIVE = "content/en/40/operations/consumer-rebalance-protocol.md"
SOURCE_SHA256 = "82259d8ac257fc5e575f3b44afe270c88db1bb1b85f98410f56c3710d67fc9af"
LICENSE_SHA256 = "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
RULE_START = 4298
RULE_END = 4762
RULE_SHA256 = "53887fc7ebc09cd59265589bf6e7ac57c589a6d58b0721a8ab5dd39e38e69df8"
AUTHENTIC_URL = (
    "https://github.com/apache/kafka-site/blob/" + SOURCE_REVISION + "/" + SOURCE_RELATIVE
)

Case = Literal["full-source", "source-free", "identity-only", "constructed-online-rule"]
CASES: tuple[Case, ...] = (
    "full-source",
    "source-free",
    "identity-only",
    "constructed-online-rule",
)
_MARKER = "[[doc:reference-source]]\n"
_ROLL = "rolling-migration"
_DRAIN = "drain-then-migrate"
_PRIOR = "source_review"
_LATER = "migration_plan"
_REVIEW = "review-complete"
_PLAN_REVIEW = "plan-reviewed"
_DATE = "2026-09-27"
_CONSTRUCTED_RULE = (
    "Consumer groups can be upgraded without downtime by rolling out the consumer with "
    "the `group.protocol=consumer` configuration. When the first consumer using the new "
    "protocol joins, the group converts from `Classic` to `Consumer`. Online conversion "
    "also works when the Classic assignor embeds "
    "custom member metadata: interoperability ignores that legacy metadata while the new "
    "consumers use a supported server-side assignor.\n"
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pinned_source(source_root: Path) -> bytes:
    raw = (source_root / SOURCE_RELATIVE).read_bytes()
    if _sha(raw) != SOURCE_SHA256:
        raise ValueError("pinned Kafka protocol source mismatch")
    if _sha((source_root / "LICENSE").read_bytes()) != LICENSE_SHA256:
        raise ValueError("pinned Kafka license mismatch")
    if _sha(raw[RULE_START:RULE_END]) != RULE_SHA256:
        raise ValueError("pinned Kafka online-rule span mismatch")
    if raw[RULE_END - 1 : RULE_END] != b"\n":
        raise ValueError("pinned Kafka online-rule span is not line-terminated")
    return raw


def kafka_source_ledger(source_root: Path) -> dict[str, object]:
    """Return evaluator-side source identity and the exact constructed edit."""

    raw = _pinned_source(source_root)
    alternative = raw[:RULE_START] + _CONSTRUCTED_RULE.encode() + raw[RULE_END:]
    return {
        "revision": SOURCE_REVISION,
        "source_url": AUTHENTIC_URL,
        "source_relative": SOURCE_RELATIVE,
        "source_sha256": _sha(raw),
        "source_bytes": len(raw),
        "license_sha256": LICENSE_SHA256,
        "rule_byte_interval": [RULE_START, RULE_END],
        "rule_sha256": _sha(raw[RULE_START:RULE_END]),
        "constructed_rule_sha256": _sha(_CONSTRUCTED_RULE.encode()),
        "constructed_source_sha256": _sha(alternative),
        "constructed_not_upstream": True,
        "untouched_prefix_suffix_exact": (
            alternative[:RULE_START] == raw[:RULE_START]
            and alternative[RULE_START + len(_CONSTRUCTED_RULE.encode()) :] == raw[RULE_END:]
        ),
    }


def _constructed(doc_id: str, title: str, body: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\nBENCHMARK SANDBOX ONLY. {body}",
        source_url="benchmark:constructed/group-migration-v1",
        retrieved_date=_DATE,
    )


def build_kafka_migration_sessions(
    source_root: Path, *, case: Case
) -> tuple[LifecycleInstance, LifecycleInstance]:
    """Build one source-arm pair; all answers remain in private stage fields.

    The authentic and constructed arms differ in exactly one source-text
    interval. Both controls keep the authentic private oracle; they are not
    alternate rule worlds. No model call is made here.
    """

    if case not in CASES:
        raise ValueError(f"unknown Kafka source case: {case}")
    raw = _pinned_source(source_root)
    source_text = raw.decode("utf-8")
    if case == "constructed-online-rule":
        source_text = (raw[:RULE_START] + _CONSTRUCTED_RULE.encode() + raw[RULE_END:]).decode(
            "utf-8"
        )
    elif case == "source-free":
        source_text = "[SOURCE WITHHELD]"
    elif case == "identity-only":
        source_text = (
            "Apache Kafka 4.0 Consumer Rebalance Protocol; KIP-848.\n"
            f"Path: {SOURCE_RELATIVE}\nURL: {AUTHENTIC_URL}\n[RULE TEXT WITHHELD]"
        )
    source = DocumentRef(
        doc_id="reference-source",
        title="Reference material",
        text=_MARKER + source_text,
        # The true provenance is in kafka_source_ledger. Model-visible
        # metadata is identical in the matched source-rule pair.
        source_url="benchmark:source-slot/group-migration-v1",
        retrieved_date=_DATE,
    )
    request = _constructed(
        "migration-request",
        "Consumer group migration request",
        "A running legacy consumer group currently uses an assignor that embeds custom "
        "member metadata. The target new-protocol group will use a supported built-in "
        "server-side assignor, with no client-side assignor in the new protocol. "
        "Operations prefers no downtime but permits a maintenance window. Choose the "
        "least disruptive route supported by the supplied reference: rolling-migration "
        "or drain-then-migrate. The latter shuts down all current consumers until the "
        "group is empty, then restarts them under the new protocol. The former rolls out "
        "new-protocol consumers while the group remains active. Request a plan-reviewed "
        "receipt for the selected route before finalizing migration_plan. That receipt "
        "confirms only local procedural review, not technical legality.",
    )
    axes = DescriptionAxes(
        information_scale_tokens=len(raw.decode("utf-8").split()),
        dependency_distance_stages=2,
        persistence_span_resets=1,
        action_dependency="strong",
        environment_changes=0,
    )
    sandbox = {
        "records": [_PRIOR, _LATER],
        "action_kinds": ["create_record", "finalize", "request_verification"],
    }
    first = LifecycleInstance(
        instance_id="research-v5-kafka-migration-s1-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="source-survey",
                kind="survey",
                prompt_text="Review the supplied reference for a later migration decision.",
                documents=(source,),
                gold_evidence_ids=(source.doc_id,),
            ),
            StageSpec(
                stage_id="review-source",
                kind="act_verify",
                prompt_text=(
                    "Request review-complete for plan reviewed. Finalize source_review "
                    "with the environment-issued passing receipt."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_PRIOR: {"status": "final"}},
                commit_precondition={
                    "record_id": _PRIOR,
                    "plan_field": "plan",
                    "legal_plans": ["reviewed"],
                    "plan_requirements": {"reviewed": {"requires_check": _REVIEW}},
                },
                verification_oracle={_REVIEW: {"reviewed": True}},
            ),
            StageSpec(
                stage_id="pause-project",
                kind="session_end",
                prompt_text="Session ends; bounded carry and project records persist.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=axes,
        answer_norm="source-conditional-migration",
        sandbox_spec=sandbox,
    )
    legal = _ROLL if case == "constructed-online-rule" else _DRAIN
    second = LifecycleInstance(
        instance_id="research-v5-kafka-migration-s2-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="resume-project",
                kind="session_start",
                prompt_text="Resume the same project after a process reset.",
                documents=(),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="migration-request-stage",
                kind="constraint_injection",
                prompt_text="Apply the project request to the retained reference.",
                documents=(request,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="decide-migration",
                kind="act_verify",
                prompt_text="Commit the supported route with a current procedural review receipt.",
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_LATER: {"status": "final"}},
                commit_precondition={
                    "record_id": _LATER,
                    "prior_finalized_record": _PRIOR,
                    "prior_verification": {
                        "check": _REVIEW,
                        "plan_field": "plan",
                        "allowed_later_plans": {"reviewed": [_ROLL, _DRAIN]},
                    },
                    "plan_field": "plan",
                    "legal_plans": [legal],
                    "plan_requirements": {
                        _ROLL: {"requires_check": _PLAN_REVIEW},
                        _DRAIN: {"requires_check": _PLAN_REVIEW},
                    },
                },
                verification_oracle={_PLAN_REVIEW: {_ROLL: True, _DRAIN: True}},
            ),
            StageSpec(
                stage_id="end-project",
                kind="session_end",
                prompt_text="Session ends.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=axes,
        answer_norm="source-conditional-migration",
        sandbox_spec=sandbox,
    )
    return first, second


__all__ = [
    "AUTHENTIC_URL",
    "CASES",
    "LICENSE_SHA256",
    "RULE_END",
    "RULE_SHA256",
    "RULE_START",
    "SOURCE_RELATIVE",
    "SOURCE_REVISION",
    "SOURCE_SHA256",
    "build_kafka_migration_sessions",
    "kafka_source_ledger",
]
