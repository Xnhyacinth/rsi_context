"""Frozen model-driven reader policy for the OTel source-contrast development pair."""

from __future__ import annotations

OTEL_MODEL_FIXED_POLICY = """
import re


def _select_from_source(turn, source):
    if not source or "|" not in source:
        return ""
    reply = turn.ask_model(
        "Read the complete upstream database client span convention below. "
        "Before seeing any project request, identify the attribute whose "
        "table row is Recommended and describes the SQL query or database "
        "statement text. Return exactly attribute=<key>. Do not use version "
        "names or migration advice.\\n\\n" + source
    )
    if not reply.ok or len(reply.content) > 128:
        return ""
    answer = reply.content.strip()
    return answer if re.fullmatch("attribute=db[.][a-z.]+", answer) else ""


def _receipt(turn, record_id, check, subject):
    return any(
        receipt.record_id == record_id
        and receipt.action_kind == "request_verification"
        and receipt.applied and receipt.check == check
        and receipt.subject == subject and receipt.verdict == "pass"
        for receipt in turn.receipts
    )


def on_turn(turn):
    stage = turn.view.stage_id
    state = turn.state
    if stage == "source-survey":
        source = turn.view.documents[0].text if turn.view.documents else ""
        attribute = _select_from_source(turn, source)
        if not attribute:
            return {"pack_text": "source survey failed", "errors": ["invalid attribute"]}
        state["carry"] = {"attribute": attribute}
        return {"pack_text": "[[doc:upstream-db]] attribute surveyed"}
    if stage == "review-source":
        if state.get("review_completed"):
            return {"pack_text": "source review completed"}
        if not state.get("review_requested"):
            state["review_requested"] = True
            return {"pack_text": "request source review", "actions": (
                turn.actions.request_verification("review-receipt", "review-complete", "reviewed"),
            )}
        if not _receipt(turn, "review-receipt", "review-complete", "reviewed"):
            return {"pack_text": "source review rejected",
                    "errors": ["source review receipt absent or failed"]}
        state["review_completed"] = True
        return {"pack_text": "commit source review", "actions": (
            turn.actions.create_record("convention_review", {"plan": "reviewed"}),
            turn.actions.finalize("convention_review", {"plan": "reviewed", "status": "final"},
                                  ("review-receipt",)),
        )}
    if stage == "project-request-stage":
        carry = state.get("carry")
        attribute = carry.get("attribute", "") if isinstance(carry, dict) else ""
        if not attribute:
            reread = turn.tools.reread("upstream-db")
            attribute = _select_from_source(turn, reread.answer) if reread.ok else ""
            if attribute:
                state["carry"] = {"attribute": attribute}
        if not attribute:
            return {"pack_text": "no attribute", "errors": ["attribute unavailable"]}
        request = "\\n\\n".join(doc.text for doc in turn.view.documents)
        reply = turn.ask_model(
            "Use only the retained upstream attribute and the visible new "
            "instrumentation request. Return exactly plan=<attribute-key> "
            "for the query-text field. The review receipt confirms procedure, "
            "not field correctness.\\n\\nRetained attribute:\\n" + attribute +
            "\\n\\nProject request:\\n" + request
        )
        if not reply.ok or not re.fullmatch("plan=db[.][a-z.]+", reply.content.strip()):
            return {"pack_text": "invalid worker plan", "errors": ["invalid worker plan"]}
        state["chosen_plan"] = reply.content.strip().split("=", 1)[1]
        return {"pack_text": "worker chose plan"}
    if stage == "decide-attribute":
        if state.get("decision_completed"):
            return {"pack_text": "decision completed"}
        plan = state.get("chosen_plan")
        if not isinstance(plan, str):
            return {"pack_text": "no worker plan", "errors": ["worker plan unavailable"]}
        if not state.get("decision_requested"):
            state["decision_requested"] = True
            return {"pack_text": "request plan review", "actions": (
                turn.actions.request_verification("decision-receipt", "plan-reviewed", plan),
            )}
        if not _receipt(turn, "decision-receipt", "plan-reviewed", plan):
            return {"pack_text": "plan review rejected",
                    "errors": ["plan review receipt absent or failed"]}
        state["decision_completed"] = True
        return {"pack_text": "commit worker plan", "actions": (
            turn.actions.create_record("query_attribute_plan", {"plan": plan}),
            turn.actions.finalize("query_attribute_plan", {"plan": plan, "status": "final"},
                                  ("decision-receipt",)),
        )}
    return {"pack_text": "observed"}
""".lstrip()


def otel_model_fixed_policy_text() -> str:
    """Return the unchanged benchmark-owned policy source."""

    return OTEL_MODEL_FIXED_POLICY


__all__ = ["OTEL_MODEL_FIXED_POLICY", "otel_model_fixed_policy_text"]
