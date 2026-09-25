"""Frozen model-driven policy for the PostgreSQL source-contrast B screen.

The policy only routes source and project observations. The worker authors
the parameter catalog before the project request is visible, then chooses
the later plan from that catalog and request. This is a development control;
its fake responder cannot establish fixed-reader difficulty.
"""

from __future__ import annotations

POSTGRESQL_MODEL_FIXED_POLICY = """
import re

CATALOG_CAP = 4096


def _catalog(turn, source):
    if not source or "<refentry" not in source:
        return ""
    reply = turn.ask_model(
        "Read the complete upstream CREATE SUBSCRIPTION SGML below. "
        "Survey its WITH-parameter catalog without a project request. "
        "Return one line, parameters=<comma-separated lowercase parameter "
        "names>, listing every parameter defined in the catalog. "
        "Do not infer names absent from the source.\\n\\n" + source
    )
    if not reply.ok or len(reply.content) > CATALOG_CAP:
        return ""
    catalog = reply.content.strip()
    if not re.fullmatch(r"parameters=[a-z_]+(?:,[a-z_]+)*", catalog):
        return ""
    return catalog


def _receipt(turn, record_id, check, subject):
    for receipt in turn.receipts:
        if (receipt.record_id == record_id and receipt.action_kind == "request_verification"
                and receipt.applied and receipt.check == check
                and receipt.subject == subject and receipt.verdict == "pass"):
            return True
    return False


def on_turn(turn):
    stage = turn.view.stage_id
    state = turn.state
    if stage == "source-survey":
        source = turn.view.documents[0].text if turn.view.documents else ""
        catalog = _catalog(turn, source)
        if not catalog:
            return {"pack_text": "source survey failed", "errors": ["invalid survey catalog"]}
        state["carry"] = {"parameter_catalog": catalog}
        return {"pack_text": "[[doc:upstream-create-subscription]] catalog surveyed"}
    if stage == "review-source":
        if state.get("review_completed"):
            return {"pack_text": "source review completed"}
        if not state.get("review_requested"):
            state["review_requested"] = True
            return {"pack_text": "request source review", "actions": (
                turn.actions.request_verification(
                    "source-review-receipt", "review-complete", "reviewed"
                ),
            )}
        if not _receipt(turn, "source-review-receipt", "review-complete", "reviewed"):
            return {"pack_text": "source review rejected",
                    "errors": ["source review receipt absent or failed"]}
        state["review_completed"] = True
        return {"pack_text": "commit source review", "actions": (
            turn.actions.create_record("source_review", {"plan": "reviewed"}),
            turn.actions.finalize("source_review", {"plan": "reviewed", "status": "final"},
                                  ("source-review-receipt",)),
        )}
    if stage == "project-request-stage":
        carry = state.get("carry")
        catalog = carry.get("parameter_catalog", "") if isinstance(carry, dict) else ""
        if not catalog:
            reread = turn.tools.reread("upstream-create-subscription")
            catalog = _catalog(turn, reread.answer) if reread.ok else ""
            if catalog:
                state["carry"] = {"parameter_catalog": catalog}
        if not catalog:
            return {"pack_text": "no catalog", "errors": ["catalog unavailable after reset"]}
        request = "\\n\\n".join(doc.text for doc in turn.view.documents)
        reply = turn.ask_model(
            "Use ONLY the retained upstream parameter catalog and the visible "
            "project request to choose the native-capability plan. Return "
            "exactly plan=configure-native or plan=defer-native. The review "
            "receipt confirms local procedure only, not feature support.\\n\\n"
            "Retained catalog:\\n" + catalog + "\\n\\nProject request:\\n" + request
        )
        if not reply.ok or reply.content.strip() not in (
            "plan=configure-native", "plan=defer-native"
        ):
            return {"pack_text": "invalid worker plan", "errors": ["invalid worker plan"]}
        state["chosen_plan"] = reply.content.strip().split("=", 1)[1]
        return {"pack_text": "worker chose plan"}
    if stage == "decide-capability":
        if state.get("decision_completed"):
            return {"pack_text": "decision completed"}
        plan = state.get("chosen_plan")
        if plan not in ("configure-native", "defer-native"):
            return {"pack_text": "no worker plan", "errors": ["worker plan unavailable"]}
        if not state.get("decision_requested"):
            state["decision_requested"] = True
            return {"pack_text": "request decision review", "actions": (
                turn.actions.request_verification(
                    "decision-review-receipt", "decision-reviewed", plan
                ),
            )}
        if not _receipt(turn, "decision-review-receipt", "decision-reviewed", plan):
            return {"pack_text": "decision review rejected",
                    "errors": ["decision review receipt absent or failed"]}
        state["decision_completed"] = True
        return {"pack_text": "commit worker plan", "actions": (
            turn.actions.create_record("native_capability_decision", {"plan": plan}),
            turn.actions.finalize("native_capability_decision",
                                  {"plan": plan, "status": "final"},
                                  ("decision-review-receipt",)),
        )}
    return {"pack_text": "observed"}
""".lstrip()


def postgresql_model_fixed_policy_text() -> str:
    """Return the unchanged benchmark-owned policy source."""

    return POSTGRESQL_MODEL_FIXED_POLICY


__all__ = ["POSTGRESQL_MODEL_FIXED_POLICY", "postgresql_model_fixed_policy_text"]
