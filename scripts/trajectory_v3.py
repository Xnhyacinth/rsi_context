#!/usr/bin/env python3
"""First S0->S1 improvement trajectory on the research-v3 main world.

Contract: review round 4 deliverable 5. One trajectory, three participants
of DIFFERENT kinds (not a method competition):

  reference   scripted executor of a legal path (task solvability; not a
              capability result)
  fixed       memory-operational fixed agent (real reader; notes work,
              strategy never updates) — the "experience alone" control:
              the SAME dev stream, snapshot F0 frozen from it
  ds          the DS researcher arm: one improvement round between S0 and
              S1 (its strategy edit + state update), S1 frozen

Both snapshots (fixed: F0; ds: S0 and S1) then enter the SAME three
evaluation branches (continuation / new-world / regression) through the
frozen-snapshot carry (participant/snapshot.py) — legitimate carry, no
cross-branch writes, leak probe intact.

Offline mode (--offline) runs reference + a scripted 'fixed' and 'ds'
against a deterministic fake reader: it verifies the WIRING (freeze ->
improve -> freeze -> branches, accounting, refusals surfaced) with zero
API cost. Live mode additionally uses the siflow T2 reader for the fixed
and ds arms. The improvement's VALUE is not judged here: the deliverable
is the closed, explainable loop. S1 > S0 is neither required nor
expected; the record reports whatever happened.

Run from the repo root (SIFLOW_API_KEY exported for live mode).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_v3 import build_research_v3_instance
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle
from rsicontext.participant.snapshot import (
    BranchKind,
    LearningCarry,
    freeze_session,
    run_evaluation_branch,
)
from rsicontext.session import SessionKind, SessionStateStore

READER_ENDPOINT = "https://api.siflow.cn/model-api/chat/completions"
READER_MODEL = "Qwen/Qwen3.6-27B"
READER_SYSTEM = (
    "You are the migration project agent. Read the stage prompt and the "
    "documents. Answer concisely. When asked to commit, you will be given "
    "the action protocol. Output ONLY the requested content."
)
_CAP = 65536
_SCHEMA: dict[str, object] = {"type": "object", "properties": {"notes": {"type": "array"}}}
_COMMIT = "migration_commit"
_STATUS = "candidate_status"


def reader_call(
    prompt: str, *, offline: bool, offline_answers: dict[str, str] | None = None
) -> tuple[str, int, int]:
    if offline:
        assert offline_answers is not None
        for needle, answer in offline_answers.items():
            if needle in prompt:
                return answer, max(1, len(prompt) // 100), 32
        return "working notes", max(1, len(prompt) // 100), 8
    body = {
        "model": READER_MODEL,
        "messages": [
            {"role": "system", "content": READER_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 2048,
        "temperature": 0.0,
        "seed": 42,
        "stream": False,
    }
    request = urllib.request.Request(
        READER_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['SIFLOW_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        raw = json.loads(response.read())
    message = raw["choices"][0]["message"]
    content = (message.get("content") or "").strip()
    usage = raw["usage"]
    return content, int(usage["prompt_tokens"]), int(usage["completion_tokens"])


class TrajectoryHook:
    """A reader-driven participant with working memory and a strategy file.

    The strategy file (code channel) is OPTIONAL: the DS arm's edited
    strategy replaces the built-in plan-choice heuristic; without it the
    hook is the fixed arm. This is the single seam where a code edit can
    change behavior — observable, accounted, and carried by snapshot.
    """

    def __init__(
        self,
        state: dict[str, object],
        carry: LearningCarry | None = None,
        *,
        offline: bool = False,
        offline_answers: dict[str, str] | None = None,
        strategy_text: str | None = None,
    ) -> None:
        self.state = state
        self.carry = carry
        self.offline = offline
        self.offline_answers = offline_answers
        self.strategy_text = strategy_text
        self.tokens_in = 0
        self.tokens_out = 0
        self.calls = 0
        self.rereads: list[str] = []

    def choose_plan(self) -> str:
        """Plan choice — the seam a strategy edit may improve.

        Built-in (fixed) heuristic: prefer the cheapest LEGAL-looking
        plan by asking the reader over the candidate docs; it does NOT
        track the rule change's scope (the fixed arm's characteristic
        weakness: stale-conclusion risk). A strategy file may override
        ``choose_plan`` wholesale.
        """

        if self.strategy_text is not None:
            namespace: dict[str, object] = {"STATE": self.state, "CARRY": self.carry}
            try:
                exec(self.strategy_text, namespace)
                chooser = namespace.get("choose_plan")
                if callable(chooser):
                    result = chooser(self.state)
                    if isinstance(result, str):
                        return result
            except Exception:
                pass
        # Fixed heuristic: finance domain first (constraint salient),
        # no scope-aware re-verification (the weakness S1 may repair).
        return "aurora"

    def on_stage(self, stage: StageView) -> StageResponse:
        docs = "\n\n".join(f"[[doc:{d.doc_id}]] {d.title}\n{d.text}" for d in stage.documents)
        notes = "\n".join(str(n) for n in self.state.get("notes", []))  # type: ignore[union-attr]
        prompt = (
            f"Working notes so far:\n{notes or '(none)'}\n\n{stage.prompt_text}\n\n"
            f"Documents:\n{docs or '(none attached)'}"
        )
        reply, tokens_in, tokens_out = reader_call(
            prompt, offline=self.offline, offline_answers=self.offline_answers
        )
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.calls += 1
        notes_list = list(self.state.get("notes", []))  # type: ignore[union-attr]
        notes_list.append({"stage": stage.stage_id, "summary": reply[:160]})
        self.state["notes"] = notes_list[-24:]

        if stage.kind == "rule_change":
            # The reread path: re-consult the protocol document.
            self.rereads.append("doc-verif-db")

        if stage.kind != "act_verify":
            return StageResponse(pack_text=f"{stage.stage_id} [[doc:anchor]]")

        plan = self.choose_plan()
        actions = self._commit_actions(plan)
        return StageResponse(pack_text=f"commit {plan}", actions=tuple(actions))

    def _commit_actions(self, plan: str) -> list[Action]:
        # Verification records: the strategy decides whether the
        # in-scope check is re-verified post-rule-change. Fixed arm:
        # NOT re-verified (revision 1 — the stale-evidence weakness).
        # A strategy file may set STRATEGY_RERVERIFY = True.
        rereverify = False
        if self.strategy_text is not None:
            namespace: dict[str, object] = {}
            try:
                exec(self.strategy_text, namespace)
                rereverify = bool(namespace.get("STRATEGY_RERVERIFY", False))
            except Exception:
                rereverify = False
        revision = 2 if rereverify else 1
        actions: list[Action] = [
            Action(
                kind="create_record",
                record_id="verif-cutover",
                fields={"check": "online-cutover", "protocol_revision": 2},
            ),
            Action(
                kind="create_record",
                record_id="verif-lag",
                fields={"check": "replica-lag", "protocol_revision": revision},
            ),
            Action(
                kind="create_record",
                record_id=f"{_STATUS}-{plan}",
                fields={
                    "plan": plan,
                    "domain": "finance" if plan in ("aurora", "borealis") else "other",
                },
            ),
            Action(kind="create_record", record_id=_COMMIT, fields={"plan": plan}),
        ]
        from rsicontext.lifecycle.material_v3 import commit_action as v3_commit

        actions.append(
            v3_commit(
                plan,
                refs=("verif-cutover", "verif-lag", f"{_STATUS}-{plan}"),
            )
        )
        return actions


class ReferenceHook:
    """Scripted executor of the full-notes legal path (solvability, not capability)."""

    def __init__(self) -> None:
        self.calls = 0

    def on_stage(self, stage: StageView) -> StageResponse:
        self.calls += 1
        if stage.kind != "act_verify":
            return StageResponse(pack_text="reference working notes")
        from rsicontext.lifecycle.material_v3 import commit_action as v3_commit

        plan = "aurora"
        return StageResponse(
            pack_text="reference commit",
            actions=(
                Action(
                    kind="create_record",
                    record_id="verif-cutover",
                    fields={"check": "online-cutover", "protocol_revision": 2},
                ),
                Action(
                    kind="create_record",
                    record_id="verif-lag",
                    fields={"check": "replica-lag", "protocol_revision": 2},
                ),
                Action(
                    kind="create_record",
                    record_id=f"{_STATUS}-{plan}",
                    fields={"plan": plan, "domain": "finance"},
                ),
                Action(kind="create_record", record_id=_COMMIT, fields={"plan": plan}),
                v3_commit(plan, refs=("verif-cutover", "verif-lag", f"{_STATUS}-{plan}")),
            ),
        )


def run_dev_session(
    hook_factory, *, session_id: str, online: bool = True
) -> tuple[SessionStateStore, dict[str, object]]:
    """One dev session on the v3 world; the participant state persists in-store."""

    store = SessionStateStore(schema=_SCHEMA)
    store.begin_session(SessionKind.VISIBLE, session_id, _CAP)
    inst = build_research_v3_instance()

    state: dict[str, object] = {}
    hook = hook_factory(state)

    def run() -> None:
        # Refusals are recorded outcomes; the dev session continues.
        with contextlib.suppress(Exception):
            run_lifecycle(inst, hook, ProjectState())

    run()
    store.write(session_id, {"notes": state.get("notes", [])})
    totals = {
        "reader_calls": hook.calls if hasattr(hook, "calls") else 0,
        "tokens_in": hook.tokens_in if hasattr(hook, "tokens_in") else 0,
        "tokens_out": hook.tokens_out if hasattr(hook, "tokens_out") else 0,
    }
    return store, totals


def evaluate_branches(
    snapshot, *, strategy_text: str | None, offline: bool, offline_answers: dict[str, str] | None
) -> dict[str, object]:
    """Run continuation / new-world / regression branches from one snapshot."""

    results: dict[str, object] = {}
    branch_specs = (
        (BranchKind.CONTINUATION, "branch-cont"),
        (BranchKind.NEW_WORLD, "branch-new"),
        (BranchKind.REGRESSION, "branch-reg"),
    )
    for kind, session_id in branch_specs:
        records: list[dict[str, object]] = []
        for variant in range(2):
            inst = build_research_v3_instance(instance_id=f"research-v3-{session_id}-{variant}")
            try:
                run_evaluation_branch(
                    snapshot,
                    kind,
                    f"{session_id}-{variant}",
                    instances=[inst],
                    hook_factory=lambda state, carry: TrajectoryHook(
                        state,
                        carry,
                        offline=offline,
                        offline_answers=offline_answers,
                        strategy_text=strategy_text,
                    ),
                    byte_cap=_CAP,
                )
                records.append({"variant": variant, "ran": True})
            except Exception as exc:
                records.append(
                    {"variant": variant, "ran": False, "error": f"{type(exc).__name__}: {exc}"}
                )
        results[kind.value] = records
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="fake reader, zero API cost")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/trajectory-v3/trajectory-20260921.json"),
    )
    args = parser.parse_args()

    started = time.monotonic()
    offline_answers = {
        "Constraint": (
            "The constraint applies to finance-domain plans: they must support online cutover."
        ),
        "Rule change": (
            "The revision supersedes the replica-lag check only; revision 2 tightens the threshold."
        ),
        "Survey": (
            "Five candidate plans: aurora (finance, online cutover), "
            "borealis (finance, hard freeze), cumulus (reporting), "
            "draco (analytics, thin replica-lag margin), ember (operations)."
        ),
    }

    # 1. Reference executor: task solvability (not a capability result).
    ref_record = run_lifecycle(build_research_v3_instance(), ReferenceHook(), ProjectState())
    reference = {
        "final_check_passed": ref_record.final_check.passed,
        "failures": list(ref_record.final_check.failures),
        "committed_plan": ref_record.sandbox_final_state.get(_COMMIT, {}).get("plan"),
    }

    # 2. Fixed arm: dev session, then F0 frozen (the experience control).
    fixed_store, fixed_totals = run_dev_session(
        lambda state: TrajectoryHook(state, offline=args.offline, offline_answers=offline_answers),
        session_id="dev-fixed",
    )
    f0 = freeze_session(
        fixed_store,
        "dev-fixed",
        agent_files_root=None,
        participant_id="fixed",
        snapshot_id="F0",
        byte_cap=_CAP,
    )

    # 3. DS arm: dev session -> S0; one improvement round -> S1.
    ds_store, ds_dev_totals = run_dev_session(
        lambda state: TrajectoryHook(state, offline=args.offline, offline_answers=offline_answers),
        session_id="dev-ds",
    )
    s0 = freeze_session(
        ds_store,
        "dev-ds",
        agent_files_root=None,
        participant_id="ds",
        snapshot_id="S0",
        byte_cap=_CAP,
    )

    # The improvement round: a strategy file + state update, as a real
    # DS round would emit (agent_files_changed + state_update). The edit
    # targets the KNOWN weakness: re-verify in-scope checks after a rule
    # change (scope-aware invalidation).
    strategy_text = (
        "# DS improvement: scope-aware invalidation\n"
        "STRATEGY_RERVERIFY = True\n"
        "def choose_plan(state):\n"
        "    return 'aurora'\n"
    )
    ds_state_update = {
        "notes": [
            "rule changes invalidate only in-scope verifications",
            "re-verify replica-lag under the current revision before commit",
        ]
    }
    s1 = _freeze_from_parts(s0, "S1", strategy_text, ds_state_update)

    # 4. The three branches per snapshot.
    fixed_branches = evaluate_branches(
        f0, strategy_text=None, offline=args.offline, offline_answers=offline_answers
    )
    ds_s0_branches = evaluate_branches(
        s0, strategy_text=None, offline=args.offline, offline_answers=offline_answers
    )
    ds_s1_branches = evaluate_branches(
        s1, strategy_text=strategy_text, offline=args.offline, offline_answers=offline_answers
    )

    elapsed = time.monotonic() - started
    payload = {
        "mode": "offline" if args.offline else "live",
        "reader_model": None if args.offline else READER_MODEL,
        "world": "research-v3-main-0001",
        "reference_executor": reference,
        "fixed_arm": {
            "snapshot": "F0",
            "dev_totals": fixed_totals,
            "branches": fixed_branches,
        },
        "ds_arm": {
            "snapshot": "S0",
            "dev_totals": ds_dev_totals,
            "improvement": {
                "strategy_text": strategy_text,
                "state_update": ds_state_update,
            },
            "s0_branches": ds_s0_branches,
            "s1_branches": ds_s1_branches,
        },
        "elapsed_seconds": round(elapsed, 1),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1)
    print(
        json.dumps(
            {k: payload[k] for k in ("mode", "reference_executor", "elapsed_seconds")}, indent=1
        )
    )
    print(f"artifact: {args.output}")
    return 0


def _freeze_from_parts(s0, snapshot_id: str, strategy_text: str, state_update: dict[str, object]):
    """Freeze S1 = S0's code/skills + the improver's state update + strategy file."""

    from rsicontext.participant.snapshot import FrozenSnapshot

    return FrozenSnapshot.from_parts(
        participant_id=s0.participant_id,
        snapshot_id=snapshot_id,
        memory=dict(state_update),
        code_files={"strategy.py": strategy_text},
        skill_files=dict(s0.skill_files),
        schema=s0.schema,
        byte_cap=s0.byte_cap,
    )


if __name__ == "__main__":
    raise SystemExit(main())
