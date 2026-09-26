"""Benchmark-owned model policy for the historical PEP development screen."""

from __future__ import annotations

PEP_MODEL_FIXED_R15 = """
import re


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
        if len(turn.view.documents) != 1:
            return {"pack_text": "missing source", "errors": ["source document missing"]}
        source = turn.view.documents[0]
        reply = turn.ask_model(
            "Historical source URL: " + source.source_url +
            "\\n\\nHistorical source:\\n" + source.text +
            "\\n\\nQuestion: For the archival fixture's MIT declaration, "
            "which [project].license form does this historical source prefer "
            "without deprecation? Return exactly form=license-table, "
            "form=license-string, or form=unknown if the source gives no rule."
        )
        if not reply.ok or len(reply.content) > 128:
            return {"pack_text": "source survey failed", "errors": ["worker source call failed"]}
        finding = reply.content.strip()
        if not re.fullmatch("form=(license-table|license-string|unknown)", finding):
            return {"pack_text": "invalid source finding", "errors": ["invalid worker finding"]}
        state["carry"] = {"source_finding": finding}
        return {"pack_text": "[[doc:historical-license-source]] source surveyed"}
    if stage == "source-review":
        if state.get("review_completed"):
            return {"pack_text": "source review complete"}
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
            turn.actions.create_record("source_review", {"plan": "reviewed"}),
            turn.actions.finalize("source_review", {"status": "final"}, ("review-receipt",)),
        )}
    if stage == "archive-request":
        carry = state.get("carry")
        finding = carry.get("source_finding", "") if isinstance(carry, dict) else ""
        if not re.fullmatch("form=(license-table|license-string|unknown)", finding):
            return {"pack_text": "no retained finding", "errors": ["source finding unavailable"]}
        if len(turn.view.documents) != 1:
            return {"pack_text": "missing request", "errors": ["project request missing"]}
        request = turn.view.documents[0].text
        reply = turn.ask_model(
            "Retained source finding:\\n" + finding +
            "\\n\\nProject request:\\n" + request +
            "\\n\\nQuestion: Choose the archival fixture plan using the "
            "retained finding and request. If the finding is unknown, "
            "use only what you can justify. Return exactly "
            "plan=license-table or plan=license-string."
        )
        if not reply.ok or len(reply.content) > 128:
            return {"pack_text": "plan call failed", "errors": ["worker plan call failed"]}
        answer = reply.content.strip()
        if not re.fullmatch("plan=(license-table|license-string)", answer):
            return {"pack_text": "invalid worker plan", "errors": ["invalid worker plan"]}
        state["chosen_plan"] = answer.split("=", 1)[1]
        return {"pack_text": "worker selected plan"}
    if stage == "decide-license-format":
        if state.get("decision_completed"):
            return {"pack_text": "decision complete"}
        plan = state.get("chosen_plan")
        if not isinstance(plan, str):
            return {"pack_text": "no worker plan", "errors": ["worker plan unavailable"]}
        if not state.get("decision_requested"):
            state["decision_requested"] = True
            return {"pack_text": "request license review", "actions": (
                turn.actions.request_verification("license-receipt", "license-review", plan),
            )}
        if not _receipt(turn, "license-receipt", "license-review", plan):
            return {"pack_text": "license review rejected",
                    "errors": ["license review receipt absent or failed"]}
        state["decision_completed"] = True
        return {"pack_text": "commit archival format", "actions": (
            turn.actions.create_record("license_format_decision", {"plan": plan}),
            turn.actions.finalize("license_format_decision", {"status": "final"},
                                  ("license-receipt",)),
        )}
    return {"pack_text": "observed"}
""".lstrip()


def pep_model_fixed_r15_text() -> str:
    """Return the unchanged benchmark-owned policy source."""

    return PEP_MODEL_FIXED_R15


__all__ = ["PEP_MODEL_FIXED_R15", "pep_model_fixed_r15_text"]
