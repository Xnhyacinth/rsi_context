"""Benchmark-owned model-driven reader for the R14 KEP resource-order card."""

from __future__ import annotations

K8S_MODEL_FIXED_POLICY = """
import re


def _receipt(turn, record_id, subject):
    return any(
        receipt.record_id == record_id
        and receipt.action_kind == "request_verification"
        and receipt.applied
        and receipt.check == "resource-review"
        and receipt.subject == subject
        and receipt.verdict == "pass"
        for receipt in turn.receipts
    )


def _choose(turn, label, request, formula, prior=""):
    reply = turn.ask_model(
        "Apply the retained KEP resource calculation to the visible scheduling "
        "request. Use the actual init-container order and CPU requests. "
        "Return exactly plan=hold-at-1000m or plan=admit-at-1000m, with no "
        "explanation.\\n\\nRetained formula: " + formula +
        "\\nPrior decision: " + prior + "\\n\\n" + label + ":\\n" + request
    )
    if not reply.ok or len(reply.content) > 80:
        return ""
    answer = reply.content.strip()
    return answer.split("=", 1)[1] if re.fullmatch(
        "plan=(hold-at-1000m|admit-at-1000m)", answer
    ) else ""


def on_turn(turn):
    stage = turn.view.stage_id
    state = turn.state
    if stage == "resource-source-survey":
        source = turn.view.documents[0].text if turn.view.documents else ""
        reply = turn.ask_model(
            "Read the supplied KEP proposal before seeing the project request. "
            "Classify its effective CPU-request calculation for a regular init "
            "container when a native sidecar also runs. Return exactly "
            "formula=prefix if only earlier sidecars are added, "
            "formula=conservative if every sidecar is added regardless of "
            "order, or formula=unknown if the supplied material does not "
            "resolve this. Do not answer a scheduling decision.\\n\\n" + source
        )
        if not reply.ok or len(reply.content) > 64:
            return {"pack_text": "source read failed", "errors": ["invalid formula reply"]}
        answer = reply.content.strip()
        if not re.fullmatch("formula=(prefix|conservative|unknown)", answer):
            return {"pack_text": "source read failed", "errors": ["invalid formula reply"]}
        state["carry"] = {"formula": answer}
        return {"pack_text": "[[doc:kep753-resource-source]] source reviewed"}
    if stage == "resource-request-stage":
        carry = state.get("carry")
        formula = carry.get("formula", "") if isinstance(carry, dict) else ""
        if not formula or not turn.view.documents:
            return {"pack_text": "missing source or request", "errors": ["missing material"]}
        plan = _choose(turn, "Project request", turn.view.documents[0].text, formula)
        if not plan:
            return {"pack_text": "invalid first plan", "errors": ["invalid first plan"]}
        state["first_plan"] = plan
        carry["first_plan"] = plan
        return {"pack_text": "first plan selected"}
    if stage == "decide-resource_assessment":
        plan = state.get("first_plan")
        if not isinstance(plan, str):
            return {"pack_text": "first plan missing", "errors": ["first plan missing"]}
        if state.get("first_committed"):
            return {"pack_text": "first decision complete"}
        if not state.get("first_review_requested"):
            state["first_review_requested"] = True
            return {"pack_text": "request first review", "actions": (
                turn.actions.request_verification("first-review", "resource-review", plan),
            )}
        if not _receipt(turn, "first-review", plan):
            return {"pack_text": "first receipt rejected", "errors": ["first receipt absent"]}
        state["first_committed"] = True
        return {"pack_text": "commit first decision", "actions": (
            turn.actions.create_record("resource_assessment", {"plan": plan}),
            turn.actions.finalize("resource_assessment", {"status": "final"},
                                  ("first-review",)),
        )}
    if stage == "resource-order-change":
        carry = state.get("carry")
        formula = carry.get("formula", "") if isinstance(carry, dict) else ""
        prior = carry.get("first_plan", "") if isinstance(carry, dict) else ""
        if not formula or not isinstance(prior, str) or not turn.view.documents:
            return {"pack_text": "carry or amendment missing", "errors": ["missing material"]}
        plan = _choose(turn, "Order amendment", turn.view.documents[0].text,
                       formula, prior)
        if not plan:
            return {"pack_text": "invalid later plan", "errors": ["invalid later plan"]}
        state["later_plan"] = plan
        return {"pack_text": "later plan selected"}
    if stage == "decide-resource_reassessment":
        plan = state.get("later_plan")
        if not isinstance(plan, str):
            return {"pack_text": "later plan missing", "errors": ["later plan missing"]}
        if state.get("later_committed"):
            return {"pack_text": "later decision complete"}
        if not state.get("later_review_requested"):
            state["later_review_requested"] = True
            return {"pack_text": "request later review", "actions": (
                turn.actions.request_verification("later-review", "resource-review", plan),
            )}
        if not _receipt(turn, "later-review", plan):
            return {"pack_text": "later receipt rejected", "errors": ["later receipt absent"]}
        state["later_committed"] = True
        return {"pack_text": "commit later decision", "actions": (
            turn.actions.create_record("resource_reassessment", {"plan": plan}),
            turn.actions.finalize("resource_reassessment", {"status": "final"},
                                  ("later-review",)),
        )}
    return {"pack_text": "observed"}
""".lstrip()


def k8s_model_fixed_policy_text() -> str:
    return K8S_MODEL_FIXED_POLICY


__all__ = ["K8S_MODEL_FIXED_POLICY", "k8s_model_fixed_policy_text"]
