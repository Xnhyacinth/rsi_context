"""Contract-level tests for the v3 sandbox semantics (finalize-lock + preconditions).

Implements the action-semantics half of docs/task-card-research-v3.md:
finalize LOCKS a record (later update_record refused — a committed
conclusion cannot be silently revised; supersession requires a new
record), and migration-commit finalization carries a checkable
PRECONDITION over the sandbox's actual records (referenced records
exist, carry the current protocol revision where the rule-change scope
applies, and satisfy the scope constraint). Failures are refusals with
names, never silent zeros.
"""

from __future__ import annotations

import pytest

from rsicontext.lifecycle.env import Action, ProjectState, ProjectStateError

# --- finalize locks ------------------------------------------------------------


def test_finalize_locks_record_against_update() -> None:
    state = ProjectState()
    state.apply(Action(kind="create_record", record_id="r", fields={"v": 1}))
    state.apply(Action(kind="finalize", record_id="r", fields={"v": 2}, provenance=("doc-1",)))
    with pytest.raises(ProjectStateError, match="finalized"):
        state.apply(Action(kind="update_record", record_id="r", fields={"v": 3}))


def test_finalize_locks_record_against_finalize() -> None:
    state = ProjectState()
    state.apply(Action(kind="create_record", record_id="r", fields={"v": 1}))
    state.apply(Action(kind="finalize", record_id="r", fields={}, provenance=("doc-1",)))
    with pytest.raises(ProjectStateError, match="finalized"):
        state.apply(Action(kind="finalize", record_id="r", fields={}, provenance=("doc-2",)))


def test_finalize_lock_survives_across_other_records() -> None:
    # Locking r does not lock sibling records: supersession proceeds by
    # NEW records, per the task card.
    state = ProjectState()
    state.apply(Action(kind="create_record", record_id="r", fields={"v": 1}))
    state.apply(Action(kind="finalize", record_id="r", fields={}, provenance=("doc-1",)))
    state.apply(Action(kind="create_record", record_id="r2", fields={"supersedes": "r"}))
    state.apply(Action(kind="finalize", record_id="r2", fields={}, provenance=("doc-2",)))
    assert state.records["r2"]["supersedes"] == "r"


# --- migration-commit precondition ---------------------------------------------


def test_commit_requires_referenced_records() -> None:
    state = ProjectState()
    state.apply(Action(kind="create_record", record_id="migration_commit", fields={"plan": "a"}))
    with pytest.raises(ProjectStateError, match="references unknown record"):
        state.apply(
            Action(
                kind="finalize",
                record_id="migration_commit",
                fields={"status": "final"},
                provenance=("verif-1",),
                precondition_refs=("verif-1",),
            )
        )


def test_commit_requires_current_revision_in_scope() -> None:
    # The referenced verification record carries the OLD protocol
    # revision while the rule change's scope covers it -> refused.
    state = ProjectState()
    state.apply(
        Action(
            kind="create_record",
            record_id="verif-1",
            fields={"check": "replica-lag", "protocol_revision": 1},
        )
    )
    state.apply(Action(kind="create_record", record_id="migration_commit", fields={"plan": "a"}))
    with pytest.raises(ProjectStateError, match="protocol revision"):
        state.apply(
            Action(
                kind="finalize",
                record_id="migration_commit",
                fields={"status": "final"},
                provenance=("verif-1",),
                precondition_refs=("verif-1",),
                precondition_current_revision=2,
                precondition_revision_scope=("replica-lag",),
            )
        )


def test_commit_allens_stale_record_outside_scope() -> None:
    # A stale-revision record OUTSIDE the rule-change scope does not
    # block the commit: partial invalidation, not global wipe.
    state = ProjectState()
    state.apply(
        Action(
            kind="create_record",
            record_id="verif-1",
            fields={"check": "disk-encryption", "protocol_revision": 1},
        )
    )
    state.apply(Action(kind="create_record", record_id="migration_commit", fields={"plan": "a"}))
    state.apply(
        Action(
            kind="finalize",
            record_id="migration_commit",
            fields={"status": "final"},
            provenance=("verif-1",),
            precondition_refs=("verif-1",),
            precondition_current_revision=2,
            precondition_revision_scope=("replica-lag",),
        )
    )
    assert state.records["migration_commit"]["status"] == "final"


def test_commit_requires_scope_constraint_satisfied() -> None:
    # Finance-domain plans must carry an online-cutover verification.
    state = ProjectState()
    state.apply(
        Action(
            kind="create_record",
            record_id="cand-a",
            fields={"plan": "a", "domain": "finance"},
        )
    )
    state.apply(Action(kind="create_record", record_id="migration_commit", fields={"plan": "a"}))
    with pytest.raises(ProjectStateError, match="constraint"):
        state.apply(
            Action(
                kind="finalize",
                record_id="migration_commit",
                fields={"status": "final"},
                provenance=("cand-a",),
                precondition_refs=("cand-a",),
                precondition_scope_constraint={
                    "domain": "finance",
                    "requires_check": "online-cutover",
                },
            )
        )


def test_commit_passes_when_constraint_record_present() -> None:
    state = ProjectState()
    state.apply(
        Action(
            kind="create_record",
            record_id="cand-a",
            fields={"plan": "a", "domain": "finance"},
        )
    )
    state.apply(
        Action(
            kind="create_record",
            record_id="verif-2",
            fields={"check": "online-cutover", "protocol_revision": 2},
        )
    )
    state.apply(Action(kind="create_record", record_id="migration_commit", fields={"plan": "a"}))
    state.apply(
        Action(
            kind="finalize",
            record_id="migration_commit",
            fields={"status": "final"},
            provenance=("cand-a", "verif-2"),
            precondition_refs=("cand-a", "verif-2"),
            precondition_current_revision=2,
            precondition_revision_scope=("replica-lag",),
            precondition_scope_constraint={"domain": "finance", "requires_check": "online-cutover"},
        )
    )
    assert state.records["migration_commit"]["status"] == "final"


def test_plain_finalize_has_no_precondition() -> None:
    # Backward compatibility: finalize without precondition fields is
    # the v2 behavior (v1/v2 material and all existing call sites).
    state = ProjectState()
    state.apply(Action(kind="create_record", record_id="answer_project", fields={"answer": "x"}))
    state.apply(
        Action(kind="finalize", record_id="answer_project", fields={}, provenance=("doc-1",))
    )
    assert state.records["answer_project"]["answer"] == "x"
