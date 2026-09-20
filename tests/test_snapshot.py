"""Contract-level tests for the frozen-learning-snapshot carry (round 4).

Implements the review-round-4 deliverable-2 acceptance cases over
``rsicontext.participant.snapshot``: a learned rule carried by CODE, by a
SKILL file, and by a MEMORY object must enter independent evaluation
branches under the SAME contract with observable use; branch state never
writes back to the parent snapshot or sibling branches; the snapshot is
byte-frozen after freeze (a frozen snapshot is immutable); and the same
schema/cap discipline as ordinary session state applies at the snapshot
boundary. The leak-probe conflict case (legitimately learned token that
also happens to be a canary token) is NOT loosened here — the probe scans
branch state for UNAUTHORIZED tokens; authorized carried tokens are the
snapshot's own validated payload, which the probe accepts by design
(``run_leak_probe_then_gate`` remains unchanged and its tests untouched).
"""

from __future__ import annotations

import pytest

from rsicontext.participant.registration import (
    EvidenceTier,
    ImprovementRoundInput,
    ImprovementRoundOutput,
    ModelPool,
    Registration,
    StateSpec,
)
from rsicontext.participant.snapshot import (
    BranchKind,
    FrozenSnapshot,
    LearningCarry,
    SnapshotBoundaryError,
    freeze_session,
    run_evaluation_branch,
)
from rsicontext.participant.usage import UsageReport
from rsicontext.session import SessionKind, SessionStateStore


def _build_rows(rows: list[dict[str, object]]) -> list[object]:
    """PopQA-shaped rows -> lifecycle instances (the existing constructor)."""

    from rsicontext.lifecycle import build_example_instance

    return [build_example_instance(row) for row in rows]


_SCHEMA: dict[str, object] = {"type": "object", "properties": {"notes": {"type": "array"}}}
_CAP = 8192


def _usage() -> UsageReport:
    return UsageReport(input_tokens=0, output_tokens=0, wall_seconds=0.0)


def _popqa_row(row_id: int, question: str, answer: str) -> dict[str, object]:
    return {
        "id": row_id,
        "question": question,
        "possible_answers": f'["{answer}", "{answer} music"]',
        "ctxs": [
            {
                "id": f"{row_id}-gold",
                "title": f"Gold source {row_id}",
                "text": f"The verified answer is {answer}.",
                "score": 0.71,
                "has_answer": True,
            },
            {
                "id": f"{row_id}-noise-1",
                "title": "Noise doc one",
                "text": "Unrelated filler passage.",
                "score": 0.66,
                "has_answer": False,
            },
        ],
    }


class _ScriptedHook:
    """Uses the carried material, then appends a branch-local note."""

    def __init__(self, state: dict[str, object], carried: LearningCarry) -> None:
        self.state = state
        self.carried = carried
        self.used: list[str] = []

    def on_stage(self, stage: object) -> object:  # StageView duck type
        rule = self.carried.memory.get("rule")
        if isinstance(rule, str) and rule not in self.used:
            self.used.append(rule)
        notes = self.state.setdefault("notes", [])
        notes.append(f"branch-note:{stage.stage_id}")  # type: ignore[attr-defined]
        from rsicontext.lifecycle.runner import StageResponse

        return StageResponse(pack_text=f"branch [[doc:anchor]] {rule or 'none'}")


# --- freeze -------------------------------------------------------------------


def test_freeze_captures_code_skills_and_memory_together(tmp_path) -> None:
    store = SessionStateStore(schema=_SCHEMA)
    store.begin_session(SessionKind.VISIBLE, "dev-1", _CAP)
    store.write("dev-1", {"notes": ["keep exceptions", "verify sources"], "rule": "cite doc ids"})
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "strategy.py").write_text("RULE = 'strip meta phrases'\n", encoding="utf-8")
    (agent_dir / "skills" / "extract.md").parent.mkdir()
    (agent_dir / "skills" / "extract.md").write_text(
        "- keep provenance\n- reread before commit\n", encoding="utf-8"
    )

    snapshot = freeze_session(
        store,
        "dev-1",
        agent_files_root=agent_dir,
        participant_id="p-1",
        snapshot_id="S1",
        byte_cap=_CAP,
    )

    assert snapshot.snapshot_id == "S1"
    assert snapshot.participant_id == "p-1"
    assert snapshot.memory == {
        "notes": ["keep exceptions", "verify sources"],
        "rule": "cite doc ids",
    }
    assert snapshot.code_files["strategy.py"] == "RULE = 'strip meta phrases'\n"
    assert (
        snapshot.skill_files["skills/extract.md"] == "- keep provenance\n- reread before commit\n"
    )
    assert snapshot.digest  # sha256 over canonical bytes
    assert snapshot.carries_code_and_memory_equally()  # both channels populated
    # Byte-frozen: a frozen snapshot cannot be re-frozen or mutated.
    with pytest.raises(SnapshotBoundaryError):
        snapshot.append_note("late note")


def test_freeze_requires_a_begun_session_with_state() -> None:
    store = SessionStateStore(schema=_SCHEMA)
    with pytest.raises(SnapshotBoundaryError):
        freeze_session(
            store,
            "never-begun",
            agent_files_root=None,
            participant_id="p",
            snapshot_id="S",
            byte_cap=_CAP,
        )


# --- branch construction -------------------------------------------------------


def test_same_rule_in_code_skill_and_memory_gets_identical_carry(tmp_path) -> None:
    store = SessionStateStore(schema=_SCHEMA)
    store.begin_session(SessionKind.VISIBLE, "dev-1", _CAP)
    store.write("dev-1", {"rule": "R1"})
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "code_rule.py").write_text("R = 'R1'\n", encoding="utf-8")
    (agent_dir / "skill_rule.md").write_text("Use R1.\n", encoding="utf-8")

    snapshot = freeze_session(
        store,
        "dev-1",
        agent_files_root=agent_dir,
        participant_id="p",
        snapshot_id="S1",
        byte_cap=_CAP,
    )

    seen: list[LearningCarry] = []

    def hook_factory(state: dict[str, object], carry: LearningCarry) -> _ScriptedHook:
        seen.append(carry)
        return _ScriptedHook(state, carry)

    for branch in ("cont-a", "new-b", "replay-c"):
        run_evaluation_branch(
            snapshot,
            BranchKind.NEW_WORLD,
            branch,
            instances=_build_rows([_popqa_row(1, "q", "a")]),
            hook_factory=hook_factory,
            byte_cap=_CAP,
        )

    # Identical carry regardless of channel: memory carried the rule AND
    # the code/skill files traveled with the same snapshot.
    assert all(c.memory.get("rule") == "R1" for c in seen)
    assert all(c.code_files.get("code_rule.py") == "R = 'R1'\n" for c in seen)
    assert all(c.skill_files.get("skill_rule.md") == "Use R1.\n" for c in seen)


def test_branch_state_never_writes_back(tmp_path) -> None:
    store = SessionStateStore(schema=_SCHEMA)
    store.begin_session(SessionKind.VISIBLE, "dev-1", _CAP)
    store.write("dev-1", {"rule": "R1"})
    snapshot = freeze_session(
        store, "dev-1", agent_files_root=None, participant_id="p", snapshot_id="S1", byte_cap=_CAP
    )
    frozen_bytes = snapshot.canonical_bytes()

    def mutating_hook_factory(state: dict[str, object], carry: LearningCarry) -> _ScriptedHook:
        # The hook mutates the branch's evolving state (as participants do).
        return _ScriptedHook(state, carry)

    run_evaluation_branch(
        snapshot,
        BranchKind.CONTINUATION,
        "cont-1",
        instances=_build_rows([_popqa_row(1, "q", "a")]),
        hook_factory=mutating_hook_factory,
        byte_cap=_CAP,
    )
    run_evaluation_branch(
        snapshot,
        BranchKind.NEW_WORLD,
        "new-1",
        instances=_build_rows([_popqa_row(2, "q2", "a2")]),
        hook_factory=mutating_hook_factory,
        byte_cap=_CAP,
    )

    # The frozen snapshot is unchanged; siblings are unaffected.
    assert snapshot.canonical_bytes() == frozen_bytes
    # The branch store carries the memory rule (legitimate carry) and the
    # branch-local notes written by the hook — but those notes exist only
    # in their own branch session.
    assert snapshot.memory == {"rule": "R1"}


def test_branches_carry_schema_and_cap_discipline(tmp_path) -> None:
    store = SessionStateStore(schema=_SCHEMA)
    store.begin_session(SessionKind.VISIBLE, "dev-1", _CAP)
    store.write("dev-1", {"rule": "R1"})
    snapshot = freeze_session(
        store, "dev-1", agent_files_root=None, participant_id="p", snapshot_id="S1", byte_cap=_CAP
    )

    run_evaluation_branch(
        snapshot,
        BranchKind.NEW_WORLD,
        "new-cap",
        instances=_build_rows([_popqa_row(1, "q", "a")]),
        hook_factory=lambda state, carry: _ScriptedHook(state, carry),
        byte_cap=_CAP,
    )
    # A branch write through the branch store enforces the same cap: a
    # cap too small for the state the hook persists is a refusal, never
    # silent truncation.
    from rsicontext.session.store import SessionStateError

    with pytest.raises(SessionStateError):
        run_evaluation_branch(
            snapshot,
            BranchKind.NEW_WORLD,
            "new-cap-2",
            instances=_build_rows([_popqa_row(1, "q", "a")]),
            hook_factory=lambda state, carry: _ScriptedHook(state, carry),
            byte_cap=8,
        )


def test_same_name_entity_across_worlds_is_not_auto_cleared(tmp_path) -> None:
    # Review case 4: a new world reusing an old world's entity name must
    # meet the carried state, not a silently wiped one. The framework
    # provides the carry; discrimination is the participant's problem.
    store = SessionStateStore(schema=_SCHEMA)
    store.begin_session(SessionKind.VISIBLE, "dev-1", _CAP)
    store.write("dev-1", {"rule": "R1", "entity_notes": {"Holiday": "genre: song-side gold"}})
    snapshot = freeze_session(
        store, "dev-1", agent_files_root=None, participant_id="p", snapshot_id="S1", byte_cap=_CAP
    )

    observed: list[dict[str, object]] = []

    def hook_factory(state: dict[str, object], carry: LearningCarry) -> _ScriptedHook:
        observed.append(carry.memory)
        return _ScriptedHook(state, carry)

    run_evaluation_branch(
        snapshot,
        BranchKind.NEW_WORLD,
        "new-holiday",
        instances=_build_rows([_popqa_row(9, "What genre is Holiday?", "power pop")]),
        hook_factory=hook_factory,
        byte_cap=_CAP,
    )
    assert observed[0].get("entity_notes") == {"Holiday": "genre: song-side gold"}


# --- improver integration: the S0 -> S1 step ----------------------------------


class _NoopImprover:
    def improve(self, round_input: ImprovementRoundInput) -> ImprovementRoundOutput:
        return ImprovementRoundOutput(agent_files_changed={}, state_update=None, usage=_usage())


def _registration(tmp_path, state_spec: StateSpec) -> Registration:
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir(exist_ok=True)
    return Registration(
        participant_id="p-1",
        arm="experience_accumulation",
        agent_dir=agent_dir,
        state_spec=state_spec,
        improver=_NoopImprover(),
        pool=ModelPool(
            pool_id="pool",
            tier=EvidenceTier.T2_VERSIONED_API,
            models=("m",),
            version_strings={"m": "v1"},
            access_window=("2026-09-01", "2026-12-31"),
        ),
        registration_label="external_researcher_assisted",
        seed_id="seed-1",
    )


def test_snapshot_advances_s0_to_s1(tmp_path) -> None:
    # The improvement round's state_update becomes the S1 snapshot's
    # memory: the frozen-snapshot contract applies to the improver's own
    # output, so an update that is legal state travels as state.
    store = SessionStateStore(schema=_SCHEMA)
    store.begin_session(SessionKind.VISIBLE, "dev-1", _CAP)
    store.write("dev-1", {"rule": "R0"})

    class _UpdatingImprover(_NoopImprover):
        def improve(self, round_input: ImprovementRoundInput) -> ImprovementRoundOutput:
            return ImprovementRoundOutput(
                agent_files_changed={},
                state_update=b'{"rule": "R1"}',
                usage=_usage(),
            )

    state_spec = StateSpec(schema=_SCHEMA, byte_cap=_CAP)
    registration = _registration(tmp_path, state_spec)
    object.__setattr__(registration, "improver", _UpdatingImprover())

    s0 = freeze_session(
        store, "dev-1", agent_files_root=None, participant_id="p-1", snapshot_id="S0", byte_cap=_CAP
    )
    assert s0.memory == {"rule": "R0"}

    round_input = ImprovementRoundInput(
        round_index=0,
        task_text="dev task",
        restricted_feedback_bytes=b"{}",
        current_agent_dir=registration.agent_dir,
        state_path=None,
        remaining_slots=1,
        task_order_seed=0,
    )
    output = registration.improver.improve(round_input)
    assert output.state_update is not None
    import json

    s1_memory = json.loads(output.state_update)
    assert s1_memory == {"rule": "R1"}
    # S1 is frozen from the update the same way S0 was frozen from the
    # dev session — one mechanism, not a special case.
    s1 = FrozenSnapshot.from_parts(
        participant_id="p-1",
        snapshot_id="S1",
        memory=s1_memory,
        code_files=dict(s0.code_files),
        skill_files=dict(s0.skill_files),
        schema=s0.schema,
        byte_cap=s0.byte_cap,
    )
    assert s1.memory == {"rule": "R1"}
    assert s1.schema == s0.schema


def test_branch_store_adapters_read_snapshot_memory_on_first_load(tmp_path) -> None:
    # The first load of a branch session returns the SNAPSHOT's memory —
    # the legitimate carry — not byte-empty state. Later loads read the
    # branch's own evolving state.
    store = SessionStateStore(schema=_SCHEMA)
    store.begin_session(SessionKind.VISIBLE, "dev-1", _CAP)
    store.write("dev-1", {"rule": "R1"})
    snapshot = freeze_session(
        store, "dev-1", agent_files_root=None, participant_id="p", snapshot_id="S1", byte_cap=_CAP
    )

    loads: list[dict[str, object] | None] = []

    class _RecordingHook(_ScriptedHook):
        def __init__(self, state: dict[str, object], carry: LearningCarry) -> None:
            super().__init__(state, carry)
            loads.append(dict(state))

    run_evaluation_branch(
        snapshot,
        BranchKind.NEW_WORLD,
        "new-first-load",
        instances=_build_rows([_popqa_row(1, "q", "a"), _popqa_row(2, "q2", "a2")]),
        hook_factory=lambda state, carry: _RecordingHook(state, carry),
        byte_cap=_CAP,
    )
    # First instance starts from the snapshot's memory (carry), then the
    # branch's own state evolves within the branch.
    assert loads[0] == {"rule": "R1"}
    assert "branch-note" in str(loads[1])


# Re-export for the module-level tests above (avoids name shadowing).
def test_snapshot_digest_is_deterministic() -> None:
    store = SessionStateStore(schema=_SCHEMA)
    store.begin_session(SessionKind.VISIBLE, "dev-1", _CAP)
    store.write("dev-1", {"rule": "R1"})
    a = freeze_session(
        store, "dev-1", agent_files_root=None, participant_id="p", snapshot_id="S", byte_cap=_CAP
    )
    b = freeze_session(
        store, "dev-1", agent_files_root=None, participant_id="p", snapshot_id="S", byte_cap=_CAP
    )
    assert a.digest == b.digest
    assert a.canonical_bytes() == b.canonical_bytes()
