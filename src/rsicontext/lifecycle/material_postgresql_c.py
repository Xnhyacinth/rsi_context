"""Unqualified PostgreSQL 17 C candidate over pinned source and sandbox state.

The SGML/COPYRIGHT files are real, immutable source material. Subscription
names, slot states, readiness receipts, and promotion actions are constructed
benchmark state; no PostgreSQL server is contacted or changed here.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from rsicontext.lifecycle.spec import DescriptionAxes, DocumentRef, LifecycleInstance, StageSpec

SOURCE_REVISION = "d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e"
SOURCE_SHA256 = {
    "COPYRIGHT": "9bf20ee493926a7e17a74bc7f05089fbc014269667b1540bc35a6b194a40c9de",
    "doc/src/sgml/logical-replication.sgml": (
        "1acce9f3166655f999c02ce7d2d454ee85f768cf9edeb83bd0c44c4766b6d709"
    ),
    "doc/src/sgml/ref/create_subscription.sgml": (
        "935c1a67d7c013410012b753ca81d75e84ed5ce2f622b195601ce1e688e97340"
    ),
}
_SOURCE_URL = "https://github.com/postgres/postgres/blob/" + SOURCE_REVISION + "/"
_DATE = "2026-09-26"
_PREPARED = "subscription_prepared"
_DECISION = "standby_decision"
_SELECTION = "slot-selection"
_SUB_READY = "subscription-slot-ready"
_COPY_READY = "table-copy-slot-ready"
_OTHER_COPY_READY = "other-table-copy-ready"
_AHEAD = "standby-ahead-of-subscriber"
_NOT_READY = "standby-not-ready"
_SLOTS = ("slot-a", "slot-b")
_PROMOTIONS = ("promote-a", "promote-b")
_HOLDS = ("hold-a", "hold-b")


def _source_doc(root: Path, relative: str, doc_id: str, title: str) -> DocumentRef:
    raw = (root / relative).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    expected = SOURCE_SHA256[relative]
    if actual != expected:
        raise ValueError(
            f"pinned PostgreSQL source mismatch for {relative}: {actual} != {expected}"
        )
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n" + raw.decode("utf-8"),
        source_url=_SOURCE_URL + relative,
        retrieved_date=_DATE,
    )


def _constructed_doc(doc_id: str, title: str, body: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\nBENCHMARK SANDBOX ONLY. {body}",
        source_url="benchmark:constructed/postgresql17-failover-v1",
        retrieved_date=_DATE,
    )


def build_postgresql17_c_sessions(
    source_root: Path, *, table_copy_a_ready: bool = True, standby_ahead: bool = True
) -> tuple[LifecycleInstance, LifecycleInstance]:
    """Build one two-session development task with two legal prior slot choices.

    The default world accepts either correctly verified prior slot, but the
    later action must follow THAT finalized choice. Setting
    ``table_copy_a_ready=False`` or ``standby_ahead=False`` changes only the
    current environment oracle: an old standby report still looks ready,
    while a fresh receipt forces a hold. All variants share one proposed
    parent lineage.
    """

    replication = _source_doc(
        source_root,
        "doc/src/sgml/logical-replication.sgml",
        "postgresql17-logical-replication-full",
        "PostgreSQL 17.0 logical replication SGML, complete file",
    )
    subscription = _source_doc(
        source_root,
        "doc/src/sgml/ref/create_subscription.sgml",
        "postgresql17-create-subscription-full",
        "PostgreSQL 17.0 CREATE SUBSCRIPTION SGML, complete file",
    )
    notice = _source_doc(
        source_root, "COPYRIGHT", "postgresql17-copyright", "PostgreSQL 17.0 COPYRIGHT notice"
    )
    inventory = _constructed_doc(
        "sandbox-subscription-inventory",
        "Constructed publisher and subscription inventory",
        "The local project has ONE subscription and two mutually exclusive "
        "candidate configurations, slot-a and slot-b. Both candidates use "
        "create_slot=false and failover=true; the named publisher slot for "
        "each reports failover=true. A historical slot-c reports "
        "failover=false. Only the candidate actually finalized in "
        "subscription_prepared becomes the active failover-enabled "
        "subscription configuration. The unchosen candidate and slot-c "
        "remain inactive and are not served by this standby. Each candidate "
        "has one finished-table-copy slot with the matching letter and one "
        "other table-copy slot whose copy is still in progress. These names "
        "and values are fictional.",
    )
    standby = _constructed_doc(
        "sandbox-standby-report",
        "Earlier constructed standby inspection",
        "A standby inspection taken before the session pause listed slot-a, "
        "slot-b, the finished table-copy-a and table-copy-b as present, "
        "synced=true, temporary=false, conflicting=false. The in-progress "
        "copies other-copy-a and other-copy-b were present but unsynced; "
        "the standby was ahead of the "
        "subscriber. This report is a prior snapshot, "
        "not the current environment's verification; synchronization can "
        "change while paused. The current verification receipts govern the "
        "next sandbox action. No real PostgreSQL instance was inspected.",
    )
    interface = _constructed_doc(
        "sandbox-standby-action-interface",
        "Constructed standby action and verification interface",
        "The sandbox accepts final plan values promote-a, promote-b, hold-a, "
        "and hold-b in standby_decision. The suffix must match the slot that "
        "was actually finalized in subscription_prepared. Available current "
        "checks are subscription-slot-ready for that candidate's subscription "
        "slot, table-copy-slot-ready for its finished copy, "
        "other-table-copy-ready for its still-in-progress copy, "
        "standby-ahead-of-subscriber, and standby-not-ready. Request checks "
        "with the proposed action plan as subject; the pinned source governs "
        "which slot states matter before promotion. For hold-a or hold-b, "
        "request standby-not-ready with the proposed "
        "hold plan as subject; a PASS confirms a required slot is not ready "
        "or the standby is not ahead of the subscriber. Verification IDs "
        "must be cited in the "
        "final action's provenance. This interface states no current verdict; "
        "inspect environment receipts before deciding.",
    )
    first = LifecycleInstance(
        instance_id="research-v5-postgresql17-c-s1-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="pg-source-survey",
                kind="survey",
                prompt_text=(
                    "Review the complete pinned PostgreSQL 17.0 source documents "
                    "and their COPYRIGHT notice. Retain the slot-alignment and "
                    "standby-readiness rules for the later project session."
                ),
                documents=(replication, subscription, notice),
                gold_evidence_ids=(replication.doc_id, subscription.doc_id),
            ),
            StageSpec(
                stage_id="pg-constructed-inventory",
                kind="constraint_injection",
                prompt_text="Assess the constructed project's subscription and slot inventory.",
                documents=(inventory,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="pg-prepare-subscription",
                kind="act_verify",
                prompt_text=(
                    "Choose one aligned candidate subscription slot, request the "
                    "environment's slot-selection verification, inspect its "
                    "receipt, then finalize subscription_prepared with that slot "
                    "as plan and the environment evidence as provenance."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_PREPARED: {"status": "final"}},
                commit_precondition={
                    "record_id": _PREPARED,
                    "plan_field": "plan",
                    "legal_plans": list(_SLOTS),
                    "plan_requirements": {slot: {"requires_check": _SELECTION} for slot in _SLOTS},
                    "current_revision": 1,
                    "revision_scope": [_SELECTION],
                },
                verification_oracle={_SELECTION: {"slot-a": True, "slot-b": True, "slot-c": False}},
            ),
            StageSpec(
                stage_id="pg-s1-end",
                kind="session_end",
                prompt_text="Session ends; only bounded carry state survives.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            # Metadata estimate only; qualification needs final-chat tokenizer offsets.
            information_scale_tokens=sum(
                len(doc.text.split()) for doc in (replication, subscription)
            ),
            dependency_distance_stages=2,
            persistence_span_resets=1,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm="verified-slot-a-or-b",
        sandbox_spec={
            "records": [_PREPARED, _DECISION],
            "action_kinds": ["create_record", "finalize", "request_verification"],
        },
    )
    second = LifecycleInstance(
        instance_id="research-v5-postgresql17-c-s2-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="pg-s2-start",
                kind="session_start",
                prompt_text=(
                    "Resume the same constructed project after a process reset. "
                    "Only bounded carry survived; the prior finalized action "
                    "and sandbox can be queried."
                ),
                documents=(),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="pg-standby-notice",
                kind="rule_change",
                prompt_text=(
                    "An earlier standby inspection arrived during the pause. "
                    "Use the pinned source and fresh environment verification "
                    "before choosing the next sandbox action."
                ),
                documents=(standby, interface),
                gold_evidence_ids=(),
                rule_change_effect=2,
                rule_change_scope=(_SUB_READY, _COPY_READY, _OTHER_COPY_READY, _AHEAD, _NOT_READY),
            ),
            StageSpec(
                stage_id="pg-standby-decision",
                kind="act_verify",
                prompt_text=(
                    "For the slot actually prepared and finalized before this "
                    "session, choose a promotion or hold action for the standby. "
                    "Request the relevant current environment checks, inspect "
                    "their receipts, and finalize standby_decision with the "
                    "chosen plan and environment evidence as provenance."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_DECISION: {"status": "final"}},
                commit_precondition={
                    "record_id": _DECISION,
                    "prior_finalized_record": _PREPARED,
                    "prior_verification": {
                        "check": _SELECTION,
                        "plan_field": "plan",
                        "allowed_later_plans": {
                            "slot-a": ["promote-a", "hold-a"],
                            "slot-b": ["promote-b", "hold-b"],
                        },
                    },
                    "plan_field": "plan",
                    "legal_plans": [*_PROMOTIONS, *_HOLDS],
                    "plan_requirements": {
                        **{
                            plan: {"requires_check": [_SUB_READY, _COPY_READY, _AHEAD]}
                            for plan in _PROMOTIONS
                        },
                        **{plan: {"requires_check": _NOT_READY} for plan in _HOLDS},
                    },
                    "current_revision": 2,
                    "revision_scope": [
                        _SUB_READY,
                        _COPY_READY,
                        _OTHER_COPY_READY,
                        _AHEAD,
                        _NOT_READY,
                    ],
                },
                verification_oracle={
                    _SUB_READY: {"promote-a": True, "promote-b": True},
                    _COPY_READY: {
                        "promote-a": table_copy_a_ready,
                        "promote-b": True,
                    },
                    _OTHER_COPY_READY: {"promote-a": False, "promote-b": False},
                    _AHEAD: {"promote-a": standby_ahead, "promote-b": standby_ahead},
                    _NOT_READY: {
                        "hold-a": not table_copy_a_ready or not standby_ahead,
                        "hold-b": not standby_ahead,
                    },
                },
            ),
            StageSpec(
                stage_id="pg-s2-end",
                kind="session_end",
                prompt_text="Session ends; only bounded carry state survives.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=sum(len(doc.text.split()) for doc in (standby, interface)),
            dependency_distance_stages=2,
            persistence_span_resets=1,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm="prior-slot-and-current-readiness-dependent",
        sandbox_spec={
            "records": [_PREPARED, _DECISION],
            "action_kinds": ["create_record", "finalize", "request_verification"],
        },
    )
    return first, second


__all__ = ["SOURCE_REVISION", "SOURCE_SHA256", "build_postgresql17_c_sessions"]
