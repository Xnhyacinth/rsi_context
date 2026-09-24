"""RSI core v1 — the act->observe channel (receipts), pinned.

The gap analysis (2026-09-22) found the environment's responses never
reached the participant: actions applied into a sandbox the hook could
never read again, refusals crashed runs, and the loop was open. These
tests pin the closed loop: every action gets a receipt, refusals are
named outcomes (not crashes), and receipts are delivered in the NEXT
stage's view.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rsicontext.lifecycle.env import Action, ProjectState, Receipt
from rsicontext.lifecycle.material_v3 import build_research_v3_instance
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle


class _ReceiptCollectingHook:
    """Emits actions at the constraint stage; records every view's receipts."""

    def __init__(self, actions_fn: Sequence[Action] | None = None) -> None:
        self.actions_fn = actions_fn
        self.received: dict[str, tuple[Receipt, ...]] = {}

    def on_stage(self, stage: StageView) -> StageResponse:
        if stage.receipts:
            self.received[stage.kind] = stage.receipts
        if stage.kind == "constraint_injection" and self.actions_fn:
            return StageResponse(pack_text="notes", actions=tuple(self.actions_fn))
        return StageResponse(pack_text="notes")


def test_submit_returns_receipt_for_applied_and_refused() -> None:
    env = ProjectState()
    env.begin_instance({"replica-lag": {"aurora": True}})
    ok = env.submit(
        Action(
            kind="request_verification",
            record_id="v1",
            fields={"check": "replica-lag", "subject": "aurora"},
        )
    )
    assert ok.applied and ok.verdict == "pass" and ok.protocol_revision == 1
    env.submit(Action(kind="create_record", record_id="dup", fields={"a": 1}))
    refused = env.submit(Action(kind="create_record", record_id="dup", fields={"a": 2}))
    assert not refused.applied
    assert "already exists" in refused.cause
    # The refusal left the state untouched.
    assert env.records["dup"] == {"a": 1}


def test_drain_receipts_is_fifo_and_clearing() -> None:
    env = ProjectState()
    env.begin_instance({"c": {"s": True}})
    env.submit(
        Action(kind="request_verification", record_id="v", fields={"check": "c", "subject": "s"})
    )
    first = env.drain_receipts()
    assert len(first) == 1 and first[0].applied
    assert env.drain_receipts() == ()


def test_receipts_reach_the_next_stage_view() -> None:
    hook = _ReceiptCollectingHook(
        actions_fn=[
            Action(kind="create_record", record_id="dup", fields={"a": 1}),
            Action(kind="create_record", record_id="dup", fields={"a": 2}),
            Action(
                kind="request_verification",
                record_id="v",
                fields={"check": "replica-lag", "subject": "aurora"},
            ),
        ]
    )
    record = run_lifecycle(build_research_v3_instance(), hook, ProjectState())
    # The run survived the refused duplicate — a refusal is a recorded
    # outcome, never a mid-run crash.
    assert record.final_check is not None
    receipts = hook.received["delegation"]
    assert receipts[0].applied is True
    assert receipts[1].applied is False and "already exists" in receipts[1].cause
    assert receipts[2].applied and receipts[2].verdict == "pass"
    assert receipts[2].protocol_revision == 1


def test_rule_change_receipts_carry_the_new_revision() -> None:
    """A verification re-requested AFTER the rule change is stamped rev 2."""

    class _TimedHook(_ReceiptCollectingHook):
        def on_stage(self, stage: StageView) -> StageResponse:
            if stage.receipts:
                self.received[stage.kind] = stage.receipts
            if stage.kind == "rule_change":
                return StageResponse(
                    pack_text="notes",
                    actions=(
                        Action(
                            kind="request_verification",
                            record_id="v2",
                            fields={"check": "replica-lag", "subject": "aurora"},
                        ),
                    ),
                )
            return StageResponse(pack_text="notes")

    hook = _TimedHook()
    run_lifecycle(build_research_v3_instance(), hook, ProjectState())
    receipts = hook.received["act_verify"]
    assert receipts[0].verdict == "pass"
    assert receipts[0].protocol_revision == 2


def test_receipt_serialization_is_plain_dict() -> None:
    receipt = Receipt(action_kind="create_record", record_id="x", applied=True)
    payload = receipt.to_dict()
    assert payload["applied"] is True
    assert set(payload) == {
        "action_kind",
        "record_id",
        "applied",
        "cause",
        "check",
        "subject",
        "verdict",
        "protocol_revision",
    }
