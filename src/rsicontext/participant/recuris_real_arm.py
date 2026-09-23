"""The REAL Recuris-adapted improver (maturity: mechanism simulation →
real implementation).

Design (recuris agent, 2026-09-23). One improvement round:
  dev run of the CURRENT package (injected dev_runner callable)
  → build_trace_doc (w_t/E_t/a_t/o_t from the run's own records)
  → Meta-Agent plan (injected callable; the module is network-free)
  → deterministic plan validation (menus, evidence citations,
    capability disclosure, ledger, leak screen)
  → ONE component-scoped patch (add_card / edit_card / set_max_cards /
    add_state_field)
  → run_gate over REAL dev runs (strict improvement + no-regression +
    no-new-policy-errors + fingerprint + leak) — ties reject
  → ledger + package commit or discard.

Every failure is a NAMED round outcome that admits nothing.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

DevRunner = Callable[[dict[str, object]], dict[str, object]]
MetaAgent = Callable[[str], str]

#: The patch vocabulary (the component/action menus the validator pins).
COMPONENTS = ("E", "W", "RHO")
ACTIONS = ("add_card", "edit_card", "set_max_cards", "add_state_field")
COMPONENT_ACTIONS: dict[str, tuple[str, ...]] = {
    "E": ("add_card", "edit_card"),
    "W": ("add_state_field",),
    "RHO": ("set_max_cards",),
}


class PlanBounce(Exception):
    """A plan that never reaches the package (their bounce path)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class RoundRecord:
    """One improvement round's auditable outcome."""

    round_index: int
    outcome: str  # accepted / rejected:<reason> / bounced:<reason> / failed:<cause>
    plan: dict[str, object] | None = None
    patch: dict[str, object] | None = None
    gate: dict[str, object] = field(default_factory=dict)
    meta_tokens_in: int = 0
    meta_tokens_out: int = 0
    package_digest_before: str = ""
    package_digest_after: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "round_index": self.round_index,
            "outcome": self.outcome,
            "plan": self.plan,
            "patch": self.patch,
            "gate": self.gate,
            "meta_tokens_in": self.meta_tokens_in,
            "meta_tokens_out": self.meta_tokens_out,
            "package_digest_before": self.package_digest_before,
            "package_digest_after": self.package_digest_after,
        }


def build_trace_doc(run: Mapping[str, object]) -> dict[str, object]:
    """(w_t, E_t, a_t, o_t) per turn, from the run's own records.

    The design's mapping: w_t = the policy's working-state keys + stage;
    E_t = the delivered card ids (the policy's own log); a_t = the
    ask_model calls (prompt digest + reply head) and action counts;
    o_t = the receipts the policy logged + the graded failures.
    """

    state = run.get("final_state") if isinstance(run.get("final_state"), dict) else {}
    delivered = state.get("memory_delivered") if isinstance(state, dict) else []
    obs = state.get("obs") if isinstance(state, dict) else []
    transcript = run.get("model_transcript") or []
    turns: list[dict[str, object]] = []
    stage_records = run.get("stage_records") or []
    for index, stage in enumerate(stage_records):
        stage_id = stage.get("stage_id", "?")
        stage_kind = stage.get("kind", "?")
        calls = [
            {
                "prompt_sha256": call.get("prompt_sha256"),
                "prompt_head": (call.get("prompt_head") or "")[:400],
                "reply_head": (call.get("reply_head") or "")[:200],
                "ok": call.get("ok"),
            }
            for call in transcript
            if isinstance(call, dict) and call.get("stage_kind") == stage_kind
        ]
        delivered_here = [
            entry
            for entry in delivered or []
            if isinstance(entry, list) and entry and entry[0] == stage_kind
        ]
        turns.append(
            {
                "stage": stage_kind,
                "stage_id": stage_id,
                "delivered_cards": (delivered_here[0][1:] if delivered_here else []),
                "actions": stage.get("actions_applied", 0),
                "model_calls": calls,
            }
        )
    return {
        "world": run.get("instance_id"),
        "run_result": "passed" if run.get("passed") else "failed",
        "decisions": dict(run.get("decisions") or {}),
        "failures": list(run.get("failures") or []),
        "policy_errors": list(run.get("policy_errors") or []),
        "usage": {
            "model_calls": run.get("model_calls", 0),
            "tokens_in": run.get("model_tokens_in", 0),
        },
        "obs_sample": [list(o) for o in (obs or [])[:20] if isinstance(o, list)],
        "turns": turns,
    }


def _digest(package: dict[str, object]) -> str:
    import hashlib

    blob = json.dumps(package, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


def validate_plan(
    plan: Mapping[str, object],
    trace: Mapping[str, object],
    package: Mapping[str, object],
    ledger_keys: set[tuple[str, str, str]],
    disclosure: Mapping[str, tuple[str, ...]],
) -> dict[str, object]:
    """Deterministic plan validation — bounce or pass, never guess.

    Checks: shape; component/action menu; ONE cluster; evidence cites a
    decision that actually failed; the target is not ledger-blocked; the
    card (if any) has a placeholder-only body (leak screen) and grounds
    on a disclosed state field; the target id is not already present
    (add) / IS present (edit).
    """

    if not isinstance(plan, dict) or "clusters" not in plan:
        raise PlanBounce("plan must be an object with 'clusters'")
    clusters = plan["clusters"]
    if not isinstance(clusters, list) or len(clusters) != 1:
        raise PlanBounce("exactly one cluster per round (one component-scoped patch)")
    cluster = clusters[0]
    if not isinstance(cluster, dict):
        raise PlanBounce("cluster must be an object")
    component = cluster.get("component")
    action = cluster.get("action")
    if component not in COMPONENTS or action not in COMPONENT_ACTIONS.get(str(component), ()):
        raise PlanBounce(f"component/action pair ({component!r}, {action!r}) not in the menu")
    evidence = cluster.get("evidence") or []
    failed_decisions = [
        key for key, value in (trace.get("decisions") or {}).items() if value is False
    ]
    if not failed_decisions:
        raise PlanBounce("nothing failed on the dev run; no repair target")
    cited = [str(item) for item in evidence if isinstance(item, str)]
    if not any(any(decision in item for item in cited) for decision in failed_decisions):
        raise PlanBounce(f"evidence must cite one of the failed decisions {failed_decisions}")
    target = str(cluster.get("target", ""))
    key = (str(component), str(action), target)
    if key in ledger_keys:
        raise PlanBounce(f"ledger: {key} was already tried (do-not-repeat)")
    if action == "add_card":
        card = cluster.get("card") or {}
        body = str(card.get("body", ""))
        if not body.strip():
            raise PlanBounce("add_card requires a card body")
        for token in _leak_tokens():
            if token in body:
                raise PlanBounce(f"leak screen: card body contains {token!r}")
        field = card.get("requires_field")
        if field is not None and field not in disclosure.get("state_fields", ()):
            raise PlanBounce(f"capability disclosure: state field {field!r} is not tracked")
        existing = {str(e.get("id")) for e in package.get("entries", ())}
        if target in existing:
            raise PlanBounce(f"card id {target!r} already exists (use edit_card)")
    if action == "edit_card":
        existing = {str(e.get("id")) for e in package.get("entries", ())}
        if target not in existing:
            raise PlanBounce(f"edit_card target {target!r} does not exist")
        body = str((cluster.get("card") or {}).get("body", ""))
        for token in _leak_tokens():
            if token in body:
                raise PlanBounce(f"leak screen: card body contains {token!r}")
    return dict(cluster)


def _leak_tokens() -> tuple[str, ...]:
    """The eval-leak screen: the mirror variant's distinctive answers."""

    return (
        "harborline-freight",
        "orbit-hosting",
        "northwind-logistics",
        "suspended",
    )


def apply_patch(package: dict[str, object], cluster: Mapping[str, object]) -> dict[str, object]:
    """ONE component-scoped patch (pure data; the package is a mapping)."""

    component = str(cluster.get("component"))
    action = str(cluster.get("action"))
    target = str(cluster.get("target"))
    patched = json.loads(json.dumps(package))
    if action in ("add_card", "edit_card"):
        card = dict(cluster.get("card") or {})
        card.setdefault("id", target)
        card.setdefault("stage", "*")
        card.setdefault("requires_field", None)
        entries = list(patched.get("entries") or [])
        if action == "add_card":
            entries.append(card)
        else:
            entries = [card if str(e.get("id")) == target else e for e in entries]
        patched["entries"] = entries
    elif action == "set_max_cards":
        value = cluster.get("value")
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise PlanBounce("set_max_cards needs a positive integer value")
        rho = dict(patched.get("invocation") or {})
        rho["max_cards_per_stage"] = value
        patched["invocation"] = rho
    elif action == "add_state_field":
        w = dict(patched.get("working_memory") or {})
        fields = dict(w.get("state_fields") or {})
        fields[target] = True
        w["state_fields"] = fields
        patched["working_memory"] = w
    else:  # pragma: no cover — menu-validated
        raise PlanBounce(f"unknown action {action!r}")
    return patched


def run_gate(
    incumbent: Mapping[str, object], candidate: Mapping[str, object], patch: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    """Accept iff strict repair + no regression + no new errors + fingerprint.

    Ties reject (conservative): with 3 binary decisions a bootstrap is
    meaningless; the declared rule is strict improvement.
    """

    inc_dec = dict(incumbent.get("decisions") or {})
    cand_dec = dict(candidate.get("decisions") or {})
    inc_sum = sum(1 for v in inc_dec.values() if v)
    cand_sum = sum(1 for v in cand_dec.values() if v)
    gate: dict[str, object] = {
        "incumbent_decisions": inc_dec,
        "candidate_decisions": cand_dec,
        "incumbent_score": inc_sum,
        "candidate_score": cand_sum,
    }
    if cand_sum <= inc_sum:
        return False, f"tie-or-worse ({cand_sum} vs {inc_sum})", gate
    regressed = [k for k in inc_dec if inc_dec.get(k) and not cand_dec.get(k)]
    if regressed:
        return False, f"regression on {regressed}", gate
    inc_err = set(incumbent.get("policy_errors") or [])
    cand_err = set(candidate.get("policy_errors") or [])
    if not cand_err <= inc_err:
        return False, f"new policy errors: {sorted(cand_err - inc_err)}", gate
    # Fingerprint: the patched mechanism must have FIRED in the candidate.
    action = str(patch.get("action"))
    cand_state = candidate.get("final_state") or {}
    delivered = (cand_state.get("memory_delivered") if isinstance(cand_state, dict) else []) or []
    delivered_ids = {entry for log in delivered if isinstance(log, list) for entry in log[1:]}
    if action in ("add_card", "edit_card"):
        target = str(patch.get("target"))
        if target not in delivered_ids:
            return False, f"fingerprint: card {target!r} never fired", gate
    if action == "set_max_cards":
        if not delivered:
            return False, "fingerprint: no cards delivered at all", gate
    gate["fingerprint_delivered_ids"] = sorted(delivered_ids)
    return True, "strict repair, no regression, fingerprint fired", gate


class RecurisAdaptedImprover:
    """R declared rounds of the Recuris-adapted loop (network-free)."""

    def __init__(
        self,
        *,
        meta_agent: MetaAgent,
        dev_runner: DevRunner,
        rounds: int = 3,
        disclosure: Mapping[str, tuple[str, ...]] | None = None,
    ) -> None:
        self._meta_agent = meta_agent
        self._dev_runner = dev_runner
        self.rounds = rounds
        self._disclosure = dict(disclosure or _DEFAULT_DISCLOSURE)
        self.rounds_log: list[RoundRecord] = []
        self.ledger_keys: set[tuple[str, str, str]] = set()
        self.meta_tokens_in = 0
        self.meta_tokens_out = 0

    def improve(self, package: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
        """Run the declared rounds; return (final package, run record)."""

        current = json.loads(json.dumps(package))
        incumbent_run = self._dev_runner(current)
        for round_index in range(self.rounds):
            record = RoundRecord(
                round_index=round_index,
                outcome="failed: unreachable",
                package_digest_before=_digest(current),
            )
            try:
                trace = build_trace_doc(incumbent_run)
                prompt = self._meta_prompt(current, trace)
                try:
                    reply = self._meta_agent(prompt)
                except Exception as exc:
                    record.outcome = f"failed: meta-agent {type(exc).__name__}: {exc}"
                    self.rounds_log.append(record)
                    continue
                plan = self._parse_plan(reply)
                if plan is None:
                    record.outcome = "bounced: meta-agent reply is not a plan"
                    self.rounds_log.append(record)
                    continue
                record.plan = plan
                cluster = validate_plan(plan, trace, current, self.ledger_keys, self._disclosure)
                record.patch = dict(cluster)
                candidate = apply_patch(current, cluster)
                candidate_run = self._dev_runner(candidate)
                accepted, reason, gate = run_gate(incumbent_run, candidate_run, cluster)
                record.gate = gate
                if accepted:
                    current = candidate
                    incumbent_run = candidate_run
                    record.outcome = f"accepted: {reason}"
                    record.package_digest_after = _digest(current)
                    key = (
                        str(cluster["component"]),
                        str(cluster["action"]),
                        str(cluster["target"]),
                    )
                    self.ledger_keys.add(key)
                else:
                    record.outcome = f"rejected: {reason}"
                    self.ledger_keys.add(
                        (str(cluster["component"]), str(cluster["action"]), str(cluster["target"]))
                    )
            except PlanBounce as exc:
                record.outcome = f"bounced: {exc.reason}"
            except Exception as exc:  # a named no-admit outcome
                record.outcome = f"failed: {type(exc).__name__}: {exc}"
            self.rounds_log.append(record)
        run_record = {
            "rounds": [r.to_dict() for r in self.rounds_log],
            "final_package_digest": _digest(current),
            "meta_tokens_in": self.meta_tokens_in,
            "meta_tokens_out": self.meta_tokens_out,
            "initial_run": {
                "decisions": dict(incumbent_run.get("decisions") or {}),
            }
            if self.rounds_log
            else {},
        }
        return current, run_record

    def _meta_prompt(self, package: Mapping[str, object], trace: Mapping[str, object]) -> str:
        return (
            "You are the memory-maintenance engineer of a project agent. "
            "The agent's MEMORY PACKAGE (below) is the only thing you may "
            "edit; its policy code is frozen. Each improvement round you "
            "propose EXACTLY ONE patch as JSON: "
            '{"clusters": [{"component": "E|W|RHO", "action": '
            '"add_card|edit_card|set_max_cards|add_state_field", "target": '
            "<id-or-field>, "
            '"card": {"body": "...", "stage": "*", '
            '"requires_field": null}, "evidence": ["<must cite a failed '
            'decision>"]}]}.\n'
            "Rules: evidence must cite a decision that FAILED on the dev "
            "run; card bodies are PLACEHOLDLES ONLY (never an answer, "
            "never a supplier name); requires_field must be one of the "
            "tracked state fields; do not repeat a previously-tried "
            "(component, action, target).\n\n"
            "TRACKED STATE FIELDS: "
            + ", ".join(self._disclosure.get("state_fields", ()))
            + "\n\n=== CURRENT PACKAGE ===\n"
            + json.dumps(package, indent=1)
            + "\n\n=== DEV RUN TRACE ===\n"
            + json.dumps(trace, indent=1)
        )

    def _parse_plan(self, reply: str) -> dict[str, object] | None:
        try:
            start = reply.find("{")
            end = reply.rfind("}")
            if start == -1 or end <= start:
                return None
            parsed = json.loads(reply[start : end + 1])
            if isinstance(parsed, dict) and isinstance(parsed.get("clusters"), list):
                return parsed
            return None
        except json.JSONDecodeError:
            return None


_DEFAULT_DISCLOSURE: dict[str, tuple[str, ...]] = {
    "state_fields": ("notes", "constraint_reply", "rule_reply", "supplier"),
    "stage_kinds": (
        "survey",
        "constraint_injection",
        "rule_change",
        "act_verify",
        "follow_up",
    ),
    "action_kinds": ("create_record", "update_record", "finalize", "request_verification"),
}


def package_to_state(package: Mapping[str, object]) -> dict[str, object]:
    """The injection mapping: the run's initial state['recuris_memory']."""

    return {"recuris_memory": json.loads(json.dumps(dict(package)))}


__all__ = [
    "RecurisAdaptedImprover",
    "RoundRecord",
    "build_trace_doc",
    "run_gate",
    "validate_plan",
    "apply_patch",
    "package_to_state",
    "PlanBounce",
]
