"""Frozen two-session Iceberg reader hook for one target call per session.

The benchmark owns prompts, parsing, actions and receipts. The responder is
the only model channel. This hook exposes neither DocumentRegistry nor a
reread tool; a new hook receives only the bounded carry after each reset.
"""

from __future__ import annotations

from collections.abc import Callable

from rsicontext.lifecycle.env import Action, Receipt
from rsicontext.lifecycle.runner import StageResponse, StageView

_DATA_RULE = "counter=data; bound=strict; partition=same-or-global; row=all-equality-ids"
_FILE_RULE = "counter=file; bound=strict; partition=same-or-global; row=all-equality-ids"
_UNKNOWN_RULE = "counter=unknown; bound=unknown; partition=unknown; row=unknown"
RULE_BUNDLES = (_DATA_RULE, _FILE_RULE, _UNKNOWN_RULE)
PLANS = ("emit-row", "suppress-row")


class InvalidReaderReply(ValueError):
    """The target returned a mixed, malformed or unregistered answer."""


def parse_rule(reply: str) -> str:
    """Accept only two coherent source rules or the all-unknown control."""

    if not isinstance(reply, str) or reply.strip() not in RULE_BUNDLES:
        raise InvalidReaderReply("S1 rule is mixed, malformed or unregistered")
    return reply.strip()


def parse_plan(reply: str) -> str:
    if not isinstance(reply, str) or reply.strip() not in {f"plan={plan}" for plan in PLANS}:
        raise InvalidReaderReply("S2 plan is malformed or unregistered")
    return reply.strip().removeprefix("plan=")


def _has_pass(receipts: tuple[Receipt, ...], *, record_id: str, check: str, subject: str) -> bool:
    return any(
        receipt.record_id == record_id
        and receipt.action_kind == "request_verification"
        and receipt.applied
        and receipt.check == check
        and receipt.subject == subject
        and receipt.verdict == "pass"
        for receipt in receipts
    )


class IcebergFixedHook:
    """One session-local hook. Only ``state['carry']`` survives reset."""

    def __init__(
        self,
        state: dict[str, object],
        responder: Callable[[str], str],
        survey_user: Callable[[str], str],
        decision_user: Callable[[str, str], str],
    ) -> None:
        self.state = state
        self.responder = responder
        self.survey_user = survey_user
        self.decision_user = decision_user
        self.model_calls = 0

    def _ask_once(self, prompt: str) -> str:
        if self.model_calls >= 1:
            raise RuntimeError("Iceberg session target-call cap reached")
        self.model_calls += 1
        return self.responder(prompt)

    def on_stage(self, stage: StageView) -> StageResponse:
        if stage.stage_id == "source-survey":
            if len(stage.documents) != 1:
                raise ValueError("Iceberg source survey requires exactly one document")
            rule = parse_rule(self._ask_once(self.survey_user(stage.documents[0].text)))
            self.state["carry"] = {"rule": rule}
            return StageResponse("[[doc:reference-source]] source rule retained")
        if stage.stage_id == "review-source":
            if not stage.receipts:
                return StageResponse(
                    "request source review",
                    (
                        Action(
                            "request_verification",
                            "prior-review",
                            {"check": "review-complete", "subject": "reviewed"},
                        ),
                    ),
                )
            if not _has_pass(
                stage.receipts,
                record_id="prior-review",
                check="review-complete",
                subject="reviewed",
            ):
                raise RuntimeError("source review receipt is missing or failed")
            return StageResponse(
                "source review committed",
                (
                    Action("create_record", "source_review", {"plan": "reviewed"}),
                    Action("finalize", "source_review", {"status": "final"}, ("prior-review",)),
                ),
            )
        if stage.stage_id == "row-request-stage":
            carry = self.state.get("carry")
            if not isinstance(carry, dict) or set(carry) != {"rule"}:
                raise RuntimeError("S2 lacks the bounded source-rule carry")
            rule = parse_rule(carry["rule"])
            if len(stage.documents) != 1:
                raise ValueError("Iceberg row request requires exactly one document")
            request = stage.documents[0].text
            if "[[doc:reference-source]]" in request:
                raise ValueError("S2 request unexpectedly contains S1 source")
            plan = parse_plan(self._ask_once(self.decision_user(request, rule)))
            self.state["plan"] = plan
            return StageResponse("row decision selected")
        if stage.stage_id == "decide-row-scan":
            selected: object = self.state.get("plan")
            if not isinstance(selected, str) or selected not in PLANS:
                raise RuntimeError("S2 has no valid row decision")
            if not stage.receipts:
                return StageResponse(
                    "request row review",
                    (
                        Action(
                            "request_verification",
                            "later-review",
                            {"check": "scan-reviewed", "subject": selected},
                        ),
                    ),
                )
            if not _has_pass(
                stage.receipts, record_id="later-review", check="scan-reviewed", subject=selected
            ):
                raise RuntimeError("row review receipt is missing or failed")
            return StageResponse(
                "row decision committed",
                (
                    Action("create_record", "row_scan_decision", {"plan": selected}),
                    Action("finalize", "row_scan_decision", {"status": "final"}, ("later-review",)),
                ),
            )
        return StageResponse("observed")


__all__ = [
    "PLANS",
    "RULE_BUNDLES",
    "IcebergFixedHook",
    "InvalidReaderReply",
    "parse_plan",
    "parse_rule",
]
