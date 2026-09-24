#!/usr/bin/env python3
"""M2 — the task-validity panel (new parents + solvability audit).

The M2 deliverable from the plan: per group, a small set of GENUINELY
DIFFERENT parent worlds (dependency-structure changes, not
name-swaps) plus an independent-reviewer solvability check against
the evaluator, recorded for reconciliation.

Two parts:

1. REFERENCE EXECUTION: for every parent world (the originals + the
   M2 parents), run the group's own reference executor offline —
   strong_model_fixed for A, the carry-aware B baseline, the
   receipt-reading C baseline — and record each decision, the gate
   failures, and a reference_solvable boolean.
2. SOLVABILITY AUDIT: for every world, the mechanical
   independent-reviewer checks — (a) every legal plan is a NAMED
   candidate in the survey material; (b) the STATED rules (constraint
   text + mutation notices) DETERMINISTICALLY select the legal set
   when applied to the survey cards' own text. Executed, not asserted.

Visibility scope (stated precisely): the REFERENCE RUN's scripted
workers see only PUBLIC material — the prompts the reference policies
themselves build (stage documents, retained notes, receipts, carried
conclusions); no oracle, no evaluator fields. The AUDIT step is
evaluator-side by design and legitimately reads the worlds' declared
gates and oracles to reconcile what the public rules derive against
what the gate enforces — that is the review it performs.

Offline only (no model key needed): the responders are deterministic
scripted workers whose answers follow the PROMPT's own material — the
established scripting discipline (r2a_compare._offline_responder).

Artifact: artifacts/rsi-core-v1/m2-validity-panel.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from r2a_compare import _offline_responder

from rsicontext.lifecycle.dossier_variants import build_dossier_variant
from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.group_baselines import (
    group_b_basline_policy_text,
    group_c_baseline_policy_text,
)
from rsicontext.lifecycle.material_b_group import (
    build_b1_reverse_sessions,
    build_b1_sessions,
)
from rsicontext.lifecycle.material_c_group import (
    build_c1_mirror_sessions,
    build_c1_sessions,
)
from rsicontext.lifecycle.material_m2_parents import (
    build_aurora_swap,
    build_b2_sessions,
    build_c2_sessions,
    build_vector,
)
from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier
from rsicontext.lifecycle.policy import PolicyHook
from rsicontext.lifecycle.runner import run_lifecycle
from rsicontext.lifecycle.session_sequence import run_session_sequence
from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text
from rsicontext.lifecycle.tools import DocumentRegistry, ToolBudget

# ---------------------------------------------------------------------------
# Reference executors (offline, text-following scripted workers)
# ---------------------------------------------------------------------------


def _a_responder(prompt: str) -> str:
    """The A-group scripted worker, extended for the M2 parents.

    Follows the SAME discipline as r2a_compare._offline_responder
    (answers derive from the prompt's own card/notes text): the award
    choice keys on the qualification clause the carried notes actually
    contain. The M2 additions: aurora-swap's harborline clause (bonded
    port-corridor, with the northwind 'depot bonding lapsed' buried
    condition present) and the currency diagnosis reading the RULE
    ANALYSIS line the prompt carries (the mirror's s7 analysis says
    'invalidates=cold-chain-integrity' — the customs evidence the
    award cites was not superseded, so 'current').
    """

    lowered = prompt.lower()
    if "name the one supplier" in lowered:
        # aurora-swap: harborline qualifies; the decoy (northwind)
        # carries 'depot bonding lapsed' in the same notes.
        if "harborline freight" in lowered and "depot bonding lapsed" in lowered:
            return "supplier=harborline-freight"
        if "atlas carriage" in lowered and "lapsed" in lowered:
            return "supplier=atlas-carriage"
        if "harborline freight" in lowered and "suspended" in lowered:
            return "supplier=harborline-freight"
        if "atlas carriage" in lowered:
            return "supplier=atlas-carriage"
        if "harborline freight" in lowered:
            return "supplier=harborline-freight"
        return "supplier=unknown"
    if "both a passing" in lowered or "both checks" in lowered:
        # vector's constraint analysis: the TWO-check rule.
        if "atlas carriage" in lowered:
            return "check=customs-preclearance candidate=atlas-carriage"
        return "check=customs-preclearance candidate=atlas-carriage"
    if "instrument supplier" in lowered or "which instrument supplier" in lowered:
        if "orbit hosting" in lowered:
            return "supplier=orbit-hosting"
        return "supplier=vesper-instruments"
    if "still current" in lowered:
        # The currency question carries the worker's OWN rule analysis
        # ('Rule analyses held: invalidates=<check or none>'): the
        # evidence is stale iff the invalidated check is the one the
        # award cited (customs-preclearance in every A world).
        if "invalidates=customs-preclearance" in lowered:
            return "status=reverify"
        if "invalidates=cold-chain-integrity" in lowered or "invalidates=none" in lowered:
            return "status=current"
        if "customs-preclearance check only" in lowered:
            return "status=reverify"
        if "cold-chain-integrity check only" in lowered:
            return "status=current"
        return "status=reverify"
    return _offline_responder(prompt)


#: The two-check award actions for vector: BOTH verifications cited.
_VECTOR_AWARD_ACTIONS = """
TWO_CHECKS = ("customs-preclearance", "cold-chain-integrity")


def _award(turn, state):
    # The supplier comes from the worker's parsed reply (the base
    # policy stored it in state['supplier']); an unparseable reply
    # falls back to 'unknown' — the base's own convention, judged by
    # the gate, never a world answer.
    supplier = state.get("supplier", "unknown")
    return {
        "pack_text": "award " + supplier,
        "actions": (
            turn.actions.request_verification("sf-v-c", "customs-preclearance", supplier),
            turn.actions.request_verification("sf-v-k", "cold-chain-integrity", supplier),
            turn.actions.create_record(
                "candidate_status-" + supplier, {"plan": supplier, "domain": "shipping"}
            ),
            turn.actions.create_record("migration_commit", {"plan": supplier}),
            turn.actions.finalize(
                "migration_commit",
                {"plan": supplier, "status": "final"},
                ("sf-v-c", "sf-v-k", "candidate_status-" + supplier),
            ),
        ),
    }
"""


def _vector_policy_text() -> str:
    """strong_model_fixed with the TWO-CHECK award shape spliced in.

    The only change from the A reference executor: the award actions
    request and cite BOTH checks (the vector decision type requires
    it — the one-check cite is a legal failure there, and a reference
    executor that fails its own world's decision type would measure
    the policy, not the world). The supplier NAME still comes from the
    model channel (no world answer hardwired).
    """

    base = strong_model_fixed_policy_text()
    needle = """        return {
            "pack_text": "award " + supplier,
            "actions": (
                turn.actions.request_verification(
                    "sf-v1", check, supplier
                ),
                turn.actions.create_record(
                    "candidate_status-" + supplier,
                    {"plan": supplier, "domain": "shipping"},
                ),
                turn.actions.create_record(
                    "migration_commit", {"plan": supplier}
                ),
                turn.actions.finalize(
                    "migration_commit",
                    {"plan": supplier, "status": "final"},
                    ("sf-v1", "candidate_status-" + supplier),
                ),
            ),
        }"""
    replacement = """        return _award(turn, state)"""
    if needle not in base:
        raise AssertionError("strong_model_fixed award block not found for the vector splice")
    return base.replace(needle, replacement) + _VECTOR_AWARD_ACTIONS


def _run_a_world(inst) -> dict[str, Any]:
    """One A-group reference run (single lifecycle)."""

    responder = _a_responder
    policy = strong_model_fixed_policy_text()
    if isinstance(inst.stages[4].commit_precondition, dict):
        requires = (
            inst.stages[4]
            .commit_precondition.get("plan_requirements", {})
            .get(inst.stages[4].commit_precondition.get("legal_plans", [None])[0], {})
            .get("requires_check")
        )
        if isinstance(requires, (list, tuple)):
            policy = _vector_policy_text()
            responder = _vector_responder
    env = ProjectState()
    budget = ToolBudget()
    hook = PolicyHook({}, policy, tool_budget=budget, responder=responder)
    hook.bind_env(env)
    record = run_lifecycle(inst, hook, env, max_turns_per_stage=2)
    failures = list(record.final_check.failures)
    decisions = {
        "award": not any("commit gate" in f for f in failures),
        "followup_1": not any("s6-followup-1" in f for f in failures),
        "followup_2": not any("s8-followup-2" in f for f in failures),
    }
    return {
        "instance_id": inst.instance_id,
        "passed": record.final_check.passed,
        "decisions": decisions,
        "gate_failures": [f for f in failures if "commit gate" in f][:8],
        "all_failures": failures[:8],
        "policy_errors": list(hook.policy_errors)[:6],
    }


def _vector_responder(prompt: str) -> str:
    """The vector world's worker: text-following, no winner hardwired.

    The award choice scans the prompt's retained-notes CARD SEGMENTS
    (pipe/newline-delimited card bodies) for the supplier whose own
    clause text satisfies BOTH required checks — the vector rule is
    cumulative, so a one-check card is not enough. The supplier id is
    derived from the card segment's first sentence (prose name ->
    kebab-case), the same way the A-group offline worker maps the
    mother corpus's 'atlas carriage' prose to its card id. No card
    qualifies -> the honest 'unknown' (the world's gate judges it).
    """

    lowered = prompt.lower()
    if "name the one supplier" in lowered:
        return "supplier=" + _scan_two_check_winner(prompt)
    if "which verification check" in lowered or "check=<name>" in lowered:
        return "check=customs-preclearance candidate=" + _scan_two_check_winner(prompt)
    if "which instrument supplier" in lowered:
        if "orbit hosting" in lowered:
            return "supplier=orbit-hosting"
        return "supplier=vesper-instruments"
    if "does this change invalidate" in lowered:
        return _offline_responder(prompt)
    if "still current" in lowered:
        if "invalidates=customs-preclearance" in lowered:
            return "status=reverify"
        return "status=current"
    return _offline_responder(prompt)


def _scan_two_check_winner(prompt: str) -> str:
    """The supplier whose card segment qualifies BOTH required checks.

    Splits the prompt's retained-notes block into card segments (the
    notes lines pipe-join batch extractions) and returns the first
    segment satisfying both check qualifications, with its supplier id
    derived from the segment's own prose name.
    """

    lowered = prompt.lower()
    if "retained notes: " not in lowered:
        return "unknown"
    notes = prompt[lowered.index("retained notes: ") :]
    segments: list[str] = []
    for line in notes.splitlines():
        body = line.removeprefix("Retained notes: ").removeprefix("notes: ")
        if not body.strip() or "=" in body.split(" ")[0]:
            continue  # a decision line (check=.../supplier=...), not a card
        segments.extend(part.strip() for part in body.split(" | ") if part.strip())
    for segment in segments:
        seg = segment.lower()
        if (
            "satisfies the customs-preclearance check" in seg
            and "satisfies the cold-chain-integrity check" in seg
            and "fails" not in seg
        ):
            return _kebab_from_prose(segment)
    return "unknown"


def _kebab_from_prose(segment: str) -> str:
    """The supplier id for a card segment (its first sentence's name)."""

    first = segment.split(".")[0]
    words = [w for w in first.split() if w]
    # Drop a leading note prefix if one survived the split.
    while words and words[0].lower() in ("notes:", "retained"):
        words = words[1:]
    name_words = []
    for word in words:
        if word == word.capitalize() or word.isupper():
            name_words.append(word)
        elif name_words:
            break
    if not name_words:
        return "unknown"
    return "-".join(w.lower().rstrip(",;:") for w in name_words)


# --- B-group reference executor ---------------------------------------------


def _b_responder(prompt: str) -> str:
    """The B scripted worker, extended for the eval twin and b2.

    Two prompt-following additions over r2a's offline worker:
    - the currency question scans the WHOLE prompt for the carried
      rule analyses: the graded record is the s1 commit citing rev-1
      customs evidence, and the derivation says stale when ANY
      analysis invalidates the award's check — the b2-s3 prompt
      carries BOTH analyses (the carried 'invalidates=customs-
      preclearance' from mutation A distilled into the carry, and the
      current session's 'invalidates=cold-chain-integrity' from
      mutation B), so the honest scan answers 'reverify' from the
      carried one — exactly the derivation's rule;
    - the calibration question in a FRESH project prefers the
      CURRENT survey's notes over the carried conclusions (the
      baseline's own contract: never answer a new project from
      carry). The prompt puts the carry first and 'Retained notes:'
      last — the notes section is the current session's own reading.
    """

    lowered = prompt.lower()
    if "still current" in lowered:
        # The award's evidence is stale iff a carried analysis
        # invalidates the award's check (customs-preclearance in
        # every B world). The b2-s3 prompt carries mutation A's
        # analysis in the distilled carry; b1's prompts carry their
        # own. Mutation B's cold-chain analysis does not touch the
        # customs evidence — but the commit's OWN evidence predates
        # mutation A, so any customs-invalidating analysis present
        # means stale.
        if "invalidates=customs-preclearance" in lowered:
            return "status=reverify"
        if "invalidates=none" in lowered:
            return "status=current"
        return _offline_responder(prompt)
    if "which instrument supplier" in lowered:
        notes_section = prompt.rsplit("Retained notes:", 1)[-1].lower()
        carry_section = prompt.split("Retained notes:", 1)[0].lower()
        if "northern service hub" in notes_section and "vesper" in notes_section:
            return "supplier=vesper-instruments"
        if "northern service hub" in notes_section and "orbit" in notes_section:
            return "supplier=orbit-hosting"
        # Notes empty (mid-project follow-up): read the carry.
        if "orbit hosting" in carry_section:
            return "supplier=orbit-hosting"
        if "vesper" in carry_section:
            return "supplier=vesper-instruments"
        return _offline_responder(prompt)
    return _offline_responder(prompt)


def _b_decision_rules(record, sessions) -> None:
    """B's decision vector, stage-id needles (b1's six + b2's session-3)."""

    by_index = record.sessions

    def _decision(key: str, session, needle: str) -> None:
        failures = session.failures if session else []
        record.decisions[key] = not any(needle in f for f in failures)
        hits = [f for f in failures if needle in f]
        if hits:
            record.failure_detail.setdefault(key, []).extend(hits[:3])

    # The six b1 needles (sessions 1-2 of both b1 and b2 share the
    # stage ids; session 3 of b1 == session 4 of b2).
    if len(by_index) >= 1:
        _decision("s1_award", by_index[0], "commit gate")
    if len(by_index) >= 2:
        _decision("s2_calibration", by_index[1], "s9-followup-calibration")
        _decision("s2_currency", by_index[1], "s10-followup-currency")
        _decision("s2_reaward_fresh", by_index[1], "commit gate[s11-re-award]")
    if len(by_index) == 3:
        _decision("s3_award", by_index[2], "commit gate")
        _decision("s3_calibration", by_index[2], "n6-followup-calibration")
    if len(by_index) >= 4:
        # b2: session 3 is the second-mutation resume; session 4 the
        # fresh-project trap (b1's session-3 stage ids).
        _decision("b2_s3_calibration", by_index[2], "b2-s3-followup-calibration")
        _decision("b2_s3_currency", by_index[2], "b2-s3-followup-currency")
        _decision("b2_s3_reaward_fresh", by_index[2], "commit gate[b2-s3-re-award]")
        _decision("s4_award", by_index[3], "commit gate")
        _decision("s4_calibration", by_index[3], "n6-followup-calibration")


def _b2_policy_text() -> str:
    """The B baseline with the SECOND renewal's record id spliced in.

    b2's second renewal (session 3) commits a NEW record
    (corridor_reaward_2, superseding corridor_reaward) — the world's
    interface change for the second boundary. The splice only adds a
    stage-keyed branch in the baseline's act_verify dispatch; every
    content decision is still the worker's (the same
    group_b_basline_policy_text underneath).
    """

    base = group_b_basline_policy_text()
    needle = """        if re_award:
            return _re_award(turn, state)"""
    replacement = """        if re_award:
            if turn.view.stage_id == "b2-s3-re-award":
                return _re_award_2(turn, state)
            return _re_award(turn, state)"""
    if needle not in base:
        raise AssertionError("baseline re-award dispatch not found for the b2 splice")
    helper = """

def _re_award_2(turn, state):
    # The second renewal: a NEW contract record id (the world's
    # interface for the second boundary). The supplier comes from the
    # carried award (the project's own distilled conclusion) or the
    # worker's earlier parse — never a hardcoded world answer.
    carry_award = state.get("carry", {})
    supplier = (
        carry_award.get("award") if isinstance(carry_award, dict) else None
    ) or state.get("supplier", "unknown")
    ver = "b2-rev-" + turn.view.stage_id
    return {
        "pack_text": "second renewal " + supplier,
        "actions": (
            turn.actions.request_verification(ver, "customs-preclearance", supplier),
            turn.actions.create_record("corridor_reaward_2", {"plan": supplier}),
            turn.actions.finalize(
                "corridor_reaward_2",
                {"plan": supplier, "status": "final"},
                (ver,),
            ),
        ),
    }
"""
    return base.replace(needle, replacement) + helper


def _run_b_world(sessions) -> dict[str, Any]:
    """One B-group reference run (session sequence)."""

    env = ProjectState()
    # Sessions 1..k thread the SAME project env (b2's sessions 1-3);
    # the LAST session is the fresh-project env.
    envs = [env] * (len(sessions) - 1) + [ProjectState()]
    budget = ToolBudget()
    registry = DocumentRegistry()
    stage_ids = {st.stage_id for inst in sessions for st in inst.stages}
    policy = (
        _b2_policy_text()
        if any(sid.startswith("b2-s3") for sid in stage_ids)
        else group_b_basline_policy_text()
    )

    def hook_factory(state):
        return PolicyHook(
            state,
            policy,
            tool_budget=budget,
            responder=_b_responder,
            registry=registry,
        )

    record = run_session_sequence(
        list(sessions),
        hook_factory,
        envs=envs,
        budget=budget,
        registry=registry,
        max_turns_per_stage=2,
        decision_rules=_b_decision_rules,
    )
    gate_failures = [
        f for session in record.sessions for f in session.failures if "commit gate" in f
    ]
    return {
        "instance_ids": [s.instance_id for s in sessions],
        "passed": all(s.passed for s in record.sessions),
        "decisions": dict(record.decisions),
        "gate_failures": gate_failures[:8],
        "all_failures": [f for s in record.sessions for f in s.failures][:8],
        "policy_errors": [e for s in record.sessions for e in s.policy_errors][:6],
    }


# --- C-group reference executor ---------------------------------------------


def _c_responder(prompt: str) -> str:
    """The C scripted worker, extended for c2's double-switch.

    Receipt-following (the test_group_baselines discipline): reads the
    prompt's own receipt lines. The c2 additions: a fail line set
    containing BOTH leaders (atlas + harborline) switches to the third
    carrier (thule); the session-2 re-award follows the RENEWAL
    NOTICE when the prompt carries one (the notice names the renewed
    subject and the SLA ranking rule — c2's world attaches it to the
    re-award stage, and the C baseline includes stage documents in
    the re-award prompt). When no notice is in the prompt (c1: the
    re-award stage carries no documents), the visible signal is the
    failed-receipt set — c1 has exactly ONE failed leader, so the
    renewed subject is that one; a multi-failure world without the
    notice would be unsolvable honestly (c2 presents it).
    """

    lowered = prompt.lower()
    if "name the one supplier to verify now" in lowered:
        fail_subjects = _receipt_subjects(prompt, "fail")
        if "current revision" in lowered:
            renewed = _notice_renewed_subject(prompt)
            if renewed:
                # The notice is in the prompt: follow its rule (the
                # renewed subject is eligible unless the notice says
                # its audit is still pending — and a renewal notice
                # never renews a still-pending subject).
                return "supplier=" + renewed
            if fail_subjects and len(fail_subjects) == 1:
                # No notice in the prompt; exactly one failed leader
                # (c1's shape): the mutation's renewal clears that
                # subject — the receipts identify it unambiguously.
                return "supplier=" + fail_subjects[0]
            return _offline_responder(prompt)
        if fail_subjects:
            # Session 1 recovery: switch away from EVERY failed subject.
            candidate = _c_switch_candidate(fail_subjects, prompt)
            return "supplier=" + candidate
        return _offline_responder(prompt)
    return _offline_responder(prompt)


def _notice_renewed_subject(prompt: str) -> str:
    """The subject a renewal notice in the prompt CLEARS (if any).

    Reads the notice's own sentence: '<Name>'s bonding audit has
    CLEARED ... verifications for <subject> are superseded'. The
    subject id appears in the supersession clause; the prose name in
    the possessive header. Both are prompt text — no world knowledge.
    """

    lowered = prompt.lower()
    if "has cleared" not in lowered:
        return ""
    for marker in (
        "verifications for atlas-carriage are superseded",
        "verifications for harborline-freight are superseded",
        "verifications for thule-carriage are superseded",
    ):
        if marker in lowered:
            return marker.split()[2]
    return ""


def _receipt_subjects(prompt: str, verdict: str) -> list[str]:
    """Subjects of the receipt lines the prompt itself carries."""

    subjects = []
    for line in prompt.splitlines():
        line = line.strip()
        if not line.startswith("record="):
            continue
        if "verdict=" + verdict not in line:
            continue
        for part in line.split():
            if part.startswith("subject="):
                subjects.append(part[len("subject=") :])
    return subjects


def _c_switch_candidate(failed_subjects: list[str], prompt: str) -> str:
    """The recovery candidate for the CURRENT world (prompt-following).

    Reads the prompt's own notes (the survey card bodies the worker
    retained) and picks a bonded-carriage candidate whose verification
    has NOT failed. c1: one leader failed (atlas) -> meridian (the
    notes' other bonded carrier). c1-mirror: harborline failed ->
    atlas (the mirror notes' other passer). c2: BOTH leaders failed
    -> thule (the third bonded carrier the c2 survey names).
    """

    lowered = prompt.lower()
    # The prompt's own candidate signals, in preference order: the
    # constraint analysis's named candidate, then a bonded-carriage
    # card line in the notes — always excluding the failed subjects.
    if "candidate=atlas-carriage" in lowered and "atlas-carriage" not in failed_subjects:
        return "atlas-carriage"
    for candidate, marker in (
        ("thule-carriage", "thule carriage runs cross-border"),
        ("atlas-carriage", "atlas carriage runs cross-border"),
        ("meridian-carriage", "meridian carriage runs cross-border"),
    ):
        if marker in lowered and candidate not in failed_subjects:
            return candidate
    return "meridian-carriage"


def _c_decision_rules(record, sessions) -> None:
    record.decisions = {f"session_{i + 1}_passed": s.passed for i, s in enumerate(record.sessions)}


def _run_c_world(sessions) -> dict[str, Any]:
    """One C-group reference run (session sequence)."""

    env = ProjectState()
    envs = [env, env]
    budget = ToolBudget()
    registry = DocumentRegistry()

    def hook_factory(state):
        return PolicyHook(
            state,
            group_c_baseline_policy_text(),
            tool_budget=budget,
            responder=_c_responder,
            registry=registry,
        )

    record = run_session_sequence(
        list(sessions),
        hook_factory,
        envs=envs,
        budget=budget,
        registry=registry,
        max_turns_per_stage=4,
        decision_rules=_c_decision_rules,
    )
    gate_failures = [
        f for session in record.sessions for f in session.failures if "commit gate" in f
    ]
    return {
        "instance_ids": [s.instance_id for s in sessions],
        "passed": all(s.passed for s in record.sessions),
        "decisions": dict(record.decisions),
        "gate_failures": gate_failures[:8],
        "all_failures": [f for s in record.sessions for f in s.failures][:8],
        "policy_errors": [e for s in record.sessions for e in s.policy_errors][:6],
    }


# ---------------------------------------------------------------------------
# The solvability audit (the mechanical independent reviewer)
# ---------------------------------------------------------------------------


def _named_cards(inst) -> dict[str, str]:
    """{supplier-name: card text} for every card in the survey stage."""

    survey = next((s for s in inst.stages if s.kind == "survey"), None)
    if survey is None:
        return {}
    out: dict[str, str] = {}
    for doc in survey.documents:
        if not doc.text.startswith("[[doc:card-"):
            continue
        header = doc.text.split("] ", 1)[1].split("\n", 1)[0]
        out[header.replace("Supplier card: ", "")] = doc.text
    return out


def _legal_plans_from_stages(inst) -> list[tuple[str, str, list[str]]]:
    """Every (stage_id, record_id, legal_plans) the world's gates declare."""

    out: list[tuple[str, str, list[str]]] = []
    for stage in inst.stages:
        if stage.commit_precondition is None:
            continue
        precondition = stage.commit_precondition
        record_id = precondition.get("record_id")
        legal = precondition.get("legal_plans")
        if isinstance(record_id, str) and isinstance(legal, list):
            out.append((stage.stage_id, record_id, [str(p) for p in legal]))
    return out


def _check_a_plans_named(inst) -> dict[str, Any]:
    """Audit (a): every legal plan is a named survey candidate."""

    cards = _named_cards(inst)
    problems: list[str] = []
    for stage_id, _record, legal in _legal_plans_from_stages(inst):
        for plan in legal:
            if plan not in cards:
                problems.append(f"{stage_id}: legal plan {plan!r} is not a named survey card")
    return {"name": "legal_plans_named_in_survey", "ok": not problems, "problems": problems}


def _rule_selected_winners(
    constraint_text: str, cards: dict[str, str]
) -> tuple[list[str], list[str]]:
    """Apply the STATED award rule to the cards' own text.

    The A-worlds' public rule: the awarded carrier must satisfy the
    required check(s). The cards state their own qualifications:
    - the winner carries an "Exception clause:" naming the check;
    - a decoy's "Buried condition:" names the failure.
    Returns (winners, losers) by clause scanning — the deterministic
    application of the stated rule to the material.
    """

    lowered_rule = constraint_text.lower()
    both_checks = "both" in lowered_rule and "and" in lowered_rule
    winners: list[str] = []
    losers: list[str] = []
    for name, text in cards.items():
        lowered = text.lower()
        # A card's clause either QUALIFIES (says it satisfies the check)
        # or DISQUALIFIES (says the check fails for this supplier —
        # 'suspended'/'lapsed'/'fails'). The wording varies by world
        # (the mother decoy: 'Buried condition ... lapsed'; the mirror
        # decoy: 'Exception clause ... suspended ... fails') — the
        # audit reads the OUTCOME the clause asserts, not the label.
        clause_says_fails = any(
            marker in lowered
            for marker in ("lapsed", "suspended", "pending audit", "pending renewal")
        ) or (
            "customs-preclearance check fails" in lowered
            or ("customs-preclearance verification" in lowered and "fails" in lowered)
        )
        qualified_check = "satisfies the" in lowered and "check" in lowered
        customs_ok = "customs-preclearance" in lowered and qualified_check and not clause_says_fails
        cold_ok = "cold-chain-integrity" in lowered and qualified_check and not clause_says_fails
        if clause_says_fails:
            losers.append(name)
        elif both_checks:
            if customs_ok and cold_ok:
                winners.append(name)
        elif customs_ok:
            winners.append(name)
    return winners, losers


def _check_a_rules_select_legal_set(inst) -> dict[str, Any]:
    """Audit (b): the stated rules deterministically select the legal set."""

    cards = _named_cards(inst)
    constraint = inst.stages[1].documents[0].text if inst.stages[1].documents else ""
    winners, _losers = _rule_selected_winners(constraint, cards)
    problems: list[str] = []
    for stage_id, _record, legal in _legal_plans_from_stages(inst):
        if stage_id != "s5-act-verify":
            continue
        if sorted(winners) != sorted(legal):
            problems.append(
                f"{stage_id}: the stated rule selects {sorted(winners)} "
                f"but the gate's legal set is {sorted(legal)}"
            )
    return {"name": "rules_select_legal_set", "ok": not problems, "problems": problems}


def _check_plans_named_union(insts, label: str) -> dict[str, Any]:
    """Audit (a) for a v5 sequence world: every legal plan the gates
    declare is a named supplier card in the world's OWN survey
    material (the union across sessions — a re-award gate in a
    survey-less session belongs to the project whose cards session 1
    surveyed)."""

    cards: dict[str, str] = {}
    for inst in insts:
        cards.update(_named_cards(inst))
    problems: list[str] = []
    for inst in insts:
        for stage_id, _record, legal in _legal_plans_from_stages(inst):
            for plan in legal:
                if plan not in cards:
                    problems.append(
                        f"{label}/{stage_id}: legal plan {plan!r} is not a named survey card"
                    )
    return {"name": "legal_plans_named_in_survey", "ok": not problems, "problems": problems}


def _check_c_public_rules_match_gate(inst_session_pair) -> dict[str, Any]:
    """Audit (b) for C worlds: the mutation notice's rule derives the legal set.

    The public rule (the notice + re-award prompt): HIGHEST-ranked
    eligible carrier by STANDARD SLA, shortest first, among the
    passers that are named survey cards. Applied mechanically to the
    session-1 survey's SLA numbers and the session-2 oracle passers.
    """

    s1, s2 = inst_session_pair
    cards = _named_cards(s1)
    import re

    slas: dict[str, int] = {}
    for name, text in cards.items():
        match = re.search(r"Standard SLA (\d+)h", text)
        if match:
            slas[name] = int(match.group(1))
    mutation_stage = next(s for s in s2.stages if s.kind == "rule_change")
    notice = mutation_stage.documents[0].text
    award_stage = next(s for s in s2.stages if s.kind == "act_verify")
    oracle = award_stage.verification_oracle or {}
    legal = [str(p) for p in award_stage.commit_precondition["legal_plans"]]
    problems: list[str] = []
    # (a) the notice states the ranking rule and the eligibility of
    # the non-renewed leaders.
    if (
        "HIGHEST-ranked eligible carrier" not in notice
        or "STANDARD SLA, shortest first" not in notice
    ):
        problems.append("the mutation notice does not state the SLA ranking rule")
    # The s2 oracle's passing subjects that are named survey cards,
    # ranked by their stated SLA — the first is the derived winner.
    check = "customs-preclearance"
    passers = [subject for subject, ok in oracle.get(check, {}).items() if ok and subject in slas]
    ranked = sorted(passers, key=lambda name: slas[name])
    if ranked and ranked[0] != legal[0]:
        problems.append(
            f"the stated SLA rule ranks {ranked[0]!r} first among passers "
            f"but the re-award legal set is {legal}"
        )
    return {"name": "rules_select_legal_set", "ok": not problems, "problems": problems}


def _check_b_rules_select_legal_set(insts) -> dict[str, Any]:
    """Audit (b) for B worlds: every gate's legal set is derivable from
    the material the participant actually holds.

    Two rule families:
    - the AWARD gates (session 1's s5-act-verify, the fresh-project
      session's n5-award): the session's OWN survey cards + its
      constraint doc select the legal set (the A-world derivation).
    - the RE-AWARD gates (s11/b2-s3 re-award): the public rule is the
      between-session notice + the re-award prompt — the legal set
      must CONTINUE the project's own session-1 winner (the notices
      never change WHO is legal, only WHICH evidence is fresh), and
      the winner must be the session-1 rule's selection.
    """

    problems: list[str] = []
    session1 = insts[0]
    s1_cards = _named_cards(session1)
    s1_constraint = ""
    for stage in session1.stages:
        if stage.kind == "constraint_injection" and stage.documents:
            s1_constraint = stage.documents[0].text
            break
    s1_winners, _ = _rule_selected_winners(s1_constraint, s1_cards)
    for inst in insts:
        cards = _named_cards(inst) or s1_cards
        constraint = s1_constraint
        for stage in inst.stages:
            if stage.kind == "constraint_injection" and stage.documents:
                constraint = stage.documents[0].text
                break
        winners, _ = _rule_selected_winners(constraint, cards)
        for stage_id, _record, legal in _legal_plans_from_stages(inst):
            if stage_id in ("s5-act-verify", "n5-award"):
                if sorted(winners) != sorted(legal):
                    problems.append(
                        f"{inst.instance_id}/{stage_id}: the session's own rule "
                        f"selects {sorted(winners)} but the gate's legal set is {sorted(legal)}"
                    )
            else:
                # A re-award gate: the project's winner continues (the
                # notices change WHICH evidence is fresh, never WHO is
                # legal).
                if sorted(legal) != sorted(s1_winners):
                    problems.append(
                        f"{inst.instance_id}/{stage_id}: the re-award legal set "
                        f"{sorted(legal)} does not continue the project's own "
                        f"rule-selected winner {sorted(s1_winners)}"
                    )
    return {"name": "rules_select_legal_set", "ok": not problems, "problems": problems}


def _audit_a(inst) -> list[dict[str, Any]]:
    checks = [
        _check_a_plans_named(inst),
        _check_a_rules_select_legal_set(inst),
    ]
    return checks


def _audit_b(insts) -> list[dict[str, Any]]:
    return [
        _check_plans_named_union(insts, insts[0].instance_id),
        _check_b_rules_select_legal_set(insts),
    ]


def _audit_c(session_pair) -> list[dict[str, Any]]:
    s1, s2 = session_pair
    named = _check_plans_named_union([s1, s2], "c")
    return [named, _check_c_public_rules_match_gate(session_pair)]


# ---------------------------------------------------------------------------
# The panel
# ---------------------------------------------------------------------------


def build_worlds() -> dict[str, list[dict[str, Any]]]:
    """The world registry: family, builder, audit factory per world."""

    def _entry(world_id, family, kind, build, audit):
        return {
            "world_id": world_id,
            "family": family,
            "kind": kind,
            "build": build,
            "audit": audit,
        }

    a_original = build_research_v4_dossier()
    a_mirror = build_dossier_variant("mirror")
    a_aurora = build_aurora_swap()
    a_vector = build_vector()
    b1 = build_b1_sessions()
    b1_reverse = build_b1_reverse_sessions()
    b2 = build_b2_sessions()
    c1 = build_c1_sessions()
    c1_mirror = build_c1_mirror_sessions()
    c2 = build_c2_sessions()

    return {
        "A": [
            _entry("a-mother", "research-v4", "lifecycle", lambda: a_original, _audit_a),
            _entry("a-mirror", "research-v4", "lifecycle", lambda: a_mirror, _audit_a),
            _entry("a-aurora-swap", "research-v4", "lifecycle", lambda: a_aurora, _audit_a),
            _entry("a-vector", "research-v4", "lifecycle", lambda: a_vector, _audit_a),
        ],
        "B": [
            _entry("b-b1", "research-v5", "sequence", lambda: list(b1), _audit_b),
            _entry("b-b1-reverse", "research-v5", "sequence", lambda: list(b1_reverse), _audit_b),
            _entry("b-b2", "research-v5", "sequence", lambda: list(b2), _audit_b),
        ],
        "C": [
            _entry("c-c1", "research-v5", "sequence", lambda: list(c1), _audit_c),
            _entry("c-c1-mirror", "research-v5", "sequence", lambda: list(c1_mirror), _audit_c),
            _entry("c-c2", "research-v5", "sequence", lambda: list(c2), _audit_c),
        ],
    }


def run_panel(output: Path) -> dict[str, Any]:
    started = time.monotonic()
    worlds = build_worlds()
    panel: dict[str, Any] = {"contract": "M2 task-validity panel (offline)", "groups": {}}
    for group_id, entries in worlds.items():
        group_rows: list[dict[str, Any]] = []
        for entry in entries:
            run: dict[str, Any]
            if entry["kind"] == "lifecycle":
                run = _run_a_world(entry["build"]())
            elif group_id == "B":
                run = _run_b_world(entry["build"]())
            else:
                run = _run_c_world(entry["build"]())
            world = entry["build"]()
            if entry["kind"] == "lifecycle":
                audit_checks = entry["audit"](world)
            else:
                audit_checks = entry["audit"](world)
            reference_solvable = bool(run["passed"]) and all(c["ok"] for c in audit_checks)
            group_rows.append(
                {
                    "world_id": entry["world_id"],
                    "family": entry["family"],
                    "instance_ids": run.get("instance_ids") or [run["instance_id"]],
                    "decisions": run["decisions"],
                    "gate_failures": run["gate_failures"],
                    "reference_solvable": reference_solvable,
                    "reference_run_passed": bool(run["passed"]),
                    "audit_checks": audit_checks,
                }
            )
        panel["groups"][group_id] = group_rows
    panel["summary"] = {
        "worlds_total": sum(len(rows) for rows in panel["groups"].values()),
        "all_reference_solvable": all(
            row["reference_solvable"] for rows in panel["groups"].values() for row in rows
        ),
        "wall_seconds": round(time.monotonic() - started, 1),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(panel, handle, indent=1)
    return panel


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/rsi-core-v1/m2-validity-panel.json"),
    )
    args = parser.parse_args()
    panel = run_panel(args.output)
    print(json.dumps(panel["summary"], indent=1))
    print(f"artifact: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
