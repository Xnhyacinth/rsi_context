"""Tests for the Recuris-style participant arm (review step 5, small fidelity).

Group 5: external-method integration — the participant interface must admit a
Recuris-STYLE improvement process (memory package, component-scoped patches,
validation gate) without any benchmark-rule change, and with agent strategy
code byte-frozen (only the memory-package data file moves).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rsicontext.participant import (
    EvidenceTier,
    ImprovementProcess,
    ImprovementRoundInput,
    ImprovementRoundOutput,
    ModelPool,
    RecurisStyleImprover,
    Registration,
    StateSpec,
    qualify_registration,
)
from rsicontext.participant.recuris_arm import (
    MEMORY_PACKAGE_FILENAME,
    EEntry,
    FeedbackReport,
    InvocationPolicy,
    MemoryPackage,
    ParticipantState,
    PatchRecord,
    RecurisArmError,
    WorkingMemory,
    neutral_seed_package,
)

BYTE_CAP = 65_536
TOKEN_BUDGET = 1500


def _feedback(*signals: dict[str, object]) -> bytes:
    return json.dumps({"signals": list(signals)}).encode("utf-8")


def _stage_failure(
    item: str = "i2", stage: str = "verify", skill: str = "verify_citations"
) -> dict[str, object]:
    return {"kind": "stage_failure", "item_id": item, "stage": stage, "missing_skill": skill}


def _usage_anomaly(item: str = "i3", budget: int = 12000) -> dict[str, object]:
    return {
        "kind": "usage_anomaly",
        "item_id": item,
        "budget_tokens": budget,
        "stages": ["retrieve", "read"],
    }


def _state_field(item: str = "i4", field: str = "open_queries") -> dict[str, object]:
    return {"kind": "unknown_state_field", "item_id": item, "field": field}


def _make_round(
    agent_dir: Path,
    state_path: Path,
    round_index: int,
    feedback: bytes,
) -> ImprovementRoundInput:
    return ImprovementRoundInput(
        round_index=round_index,
        task_text=f"research task {round_index}",
        restricted_feedback_bytes=feedback,
        current_agent_dir=agent_dir,
        state_path=state_path,
        remaining_slots=8 - round_index,
        task_order_seed=1234,
    )


@pytest.fixture
def agent_dir(tmp_path: Path) -> Path:
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "strategy.py").write_text("# frozen strategy code\n", encoding="utf-8")
    return agent


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    return tmp_path / "state.json"


@pytest.fixture
def improver() -> RecurisStyleImprover:
    return RecurisStyleImprover(byte_cap=BYTE_CAP, token_budget=TOKEN_BUDGET)


def _apply_round(
    improver: RecurisStyleImprover,
    agent_dir: Path,
    state_path: Path,
    round_index: int,
    feedback: bytes,
) -> ImprovementRoundOutput:
    """Run one round and persist what the harness would apply (files + state)."""

    output = improver.improve(_make_round(agent_dir, state_path, round_index, feedback))
    state_path.write_bytes(output.state_update or b"")
    for relative, content in output.agent_files_changed.items():
        (agent_dir / relative).write_text(content, encoding="utf-8")
    return output


# --- Group 5a: the arm satisfies the participant protocol ---


def test_satisfies_improvement_process_protocol(improver: RecurisStyleImprover) -> None:
    """The arm is a registrable ImprovementProcess (runtime_checkable)."""

    assert isinstance(improver, ImprovementProcess)


def test_qualification_smoke_passes(tmp_path: Path, agent_dir: Path) -> None:
    """The arm passes the ordinary registration qualification machinery."""

    registration = Registration(
        participant_id="recuris-style-1",
        arm="experience_accumulation",
        agent_dir=agent_dir,
        state_spec=StateSpec(
            schema={"accepted": "list", "rejected": "list", "previous_feedback": "object"},
            byte_cap=BYTE_CAP,
        ),
        improver=RecurisStyleImprover(byte_cap=BYTE_CAP),
        pool=ModelPool(
            pool_id="pool-anchor",
            tier=EvidenceTier.T1_ANCHOR,
            models=("qwen3.6-27b",),
            version_strings={"qwen3.6-27b": "1b559cf"},
            access_window=None,
        ),
        registration_label="external_researcher_assisted",
        seed_id="seed-1",
    )
    result = qualify_registration(registration, lambda path: [])
    assert result.passed, result.reasons


# --- Group 5b: localization and component-scoped patching ---


def test_localization_maps_each_failure_kind_to_one_component(
    improver: RecurisStyleImprover, agent_dir: Path, state_path: Path
) -> None:
    """stage_failure -> E add_card; usage_anomaly -> rho; state-field -> W."""

    out_e = _apply_round(improver, agent_dir, state_path, 0, _feedback(_stage_failure()))
    assert MEMORY_PACKAGE_FILENAME in out_e.agent_files_changed
    pkg = MemoryPackage.from_bytes((agent_dir / MEMORY_PACKAGE_FILENAME).read_bytes())
    assert [entry.id for entry in pkg.entries] == ["verify_verify_citations"]
    assert pkg.entries[0].type == "procedure"
    assert pkg.entries[0].handles == ("verify_citations",)
    # component-scoped: W and rho untouched (same objects as the seed).
    seed = neutral_seed_package()
    assert pkg.working_memory == seed.working_memory
    assert pkg.invocation == seed.invocation
    assert pkg.checkers == seed.checkers

    out_w = _apply_round(improver, agent_dir, state_path, 1, _feedback(_state_field()))
    assert MEMORY_PACKAGE_FILENAME in out_w.agent_files_changed
    pkg_w = MemoryPackage.from_bytes((agent_dir / MEMORY_PACKAGE_FILENAME).read_bytes())
    assert "open_queries" in pkg_w.working_memory.state_fields
    # E and rho untouched by the W patch.
    assert pkg_w.entries == pkg.entries
    assert pkg_w.invocation == pkg.invocation


def test_usage_anomaly_patch_lowers_invocation_cap(
    improver: RecurisStyleImprover, agent_dir: Path, state_path: Path
) -> None:
    """A genuinely over-budget package gets a rho patch that must fit the budget."""

    # Seed a package whose projected usage exceeds the budget at cap 2 but
    # fits at cap 1: base 1000, three cards, per-card cost 1500.
    # cap 2 -> 1000 + 3*1500 = 5500 > 1500; cap 1 -> 1000 + 2*1500 = 4000 > 1500.
    # Budget must sit between: use 4000 as the budget via a custom improver.
    heavy = MemoryPackage(
        name="neutral",
        entries=(
            EEntry(
                id="a",
                type="knowledge",
                stage="retrieve",
                handles=("skill_a",),
                requires_field=None,
                body="b",
                source="s",
            ),
            EEntry(
                id="b",
                type="knowledge",
                stage="retrieve",
                handles=("skill_b",),
                requires_field=None,
                body="b",
                source="s",
            ),
            EEntry(
                id="c",
                type="knowledge",
                stage="read",
                handles=("skill_c",),
                requires_field=None,
                body="b",
                source="s",
            ),
        ),
        working_memory=WorkingMemory(goals=("g",), state_fields={}, base_token_cost=1000),
        invocation=InvocationPolicy(
            invoked_on_stages=("retrieve", "read"), max_cards_per_stage=2, per_card_token_cost=1500
        ),
        checkers=neutral_seed_package().checkers,
    )
    (agent_dir / MEMORY_PACKAGE_FILENAME).write_bytes(heavy.to_bytes())
    tight = RecurisStyleImprover(byte_cap=BYTE_CAP, token_budget=4000)

    out = _apply_round(tight, agent_dir, state_path, 0, _feedback(_usage_anomaly()))
    assert MEMORY_PACKAGE_FILENAME in out.agent_files_changed
    patched = MemoryPackage.from_bytes((agent_dir / MEMORY_PACKAGE_FILENAME).read_bytes())
    assert patched.invocation.max_cards_per_stage == 1
    # Only rho changed: E and W pass through untouched.
    assert patched.entries == heavy.entries
    assert patched.working_memory == heavy.working_memory


def test_patch_is_component_scoped_bytes_pass_through(
    improver: RecurisStyleImprover, agent_dir: Path, state_path: Path
) -> None:
    """A W patch leaves the E and rho component bytes untouched."""

    _apply_round(improver, agent_dir, state_path, 0, _feedback(_state_field()))
    before = MemoryPackage.from_bytes((agent_dir / MEMORY_PACKAGE_FILENAME).read_bytes())
    # second W patch on a different field
    out2 = _apply_round(
        improver, agent_dir, state_path, 1, _feedback(_state_field(item="i5", field="cite_queue"))
    )
    assert MEMORY_PACKAGE_FILENAME in out2.agent_files_changed
    after = MemoryPackage.from_bytes((agent_dir / MEMORY_PACKAGE_FILENAME).read_bytes())
    assert after.to_mapping()["E"] == before.to_mapping()["E"]
    assert after.to_mapping()["rho"] == before.to_mapping()["rho"]
    assert after.to_mapping()["W"] != before.to_mapping()["W"]
    assert "cite_queue" in after.working_memory.state_fields


def test_one_patch_per_round_even_with_many_signals(
    improver: RecurisStyleImprover, agent_dir: Path, state_path: Path
) -> None:
    """Multiple signals still yield exactly one component-scoped patch."""

    _apply_round(
        improver,
        agent_dir,
        state_path,
        0,
        _feedback(
            _stage_failure(item="i1", stage="retrieve", skill="plan_queries"),
            _stage_failure(item="i2", stage="verify", skill="verify_citations"),
            _state_field(),
        ),
    )
    pkg = MemoryPackage.from_bytes((agent_dir / MEMORY_PACKAGE_FILENAME).read_bytes())
    # Only the first localized failure (kind order, then item id) is patched.
    assert [entry.id for entry in pkg.entries] == ["retrieve_plan_queries"]
    # W was not touched this round even though a state-field signal existed.
    assert pkg.working_memory == neutral_seed_package().working_memory


# --- Group 5c: the validation gate ---


def test_gate_accepts_a_patch_that_repairs(
    improver: RecurisStyleImprover, agent_dir: Path, state_path: Path
) -> None:
    """A repairing, non-regressing patch is admitted and emitted."""

    out = _apply_round(improver, agent_dir, state_path, 0, _feedback(_stage_failure()))
    assert MEMORY_PACKAGE_FILENAME in out.agent_files_changed
    state = json.loads((state_path).read_bytes())
    assert [record["target"] for record in state["accepted"]] == ["verify_verify_citations"]
    assert state["rejected"] == []
    assert (
        improver.gate_reason_of(_make_round(agent_dir, state_path, 1, _feedback(_stage_failure())))
        == "no proposal for the diagnosed component"
    )


def test_gate_blocks_a_patch_that_does_not_repair(
    improver: RecurisStyleImprover, agent_dir: Path, state_path: Path
) -> None:
    """A patch that cannot repair its own failure is never admitted.

    The RHO patch lowers the cap by one; when even the lowered cap stays over
    budget, the gate must reject and emit no file change.
    """

    heavy = MemoryPackage(
        name="neutral",
        entries=(
            EEntry(
                id="a",
                type="knowledge",
                stage="retrieve",
                handles=("skill_a",),
                requires_field=None,
                body="b",
                source="s",
            ),
            EEntry(
                id="b",
                type="knowledge",
                stage="retrieve",
                handles=("skill_b",),
                requires_field=None,
                body="b",
                source="s",
            ),
            EEntry(
                id="c",
                type="knowledge",
                stage="read",
                handles=("skill_c",),
                requires_field=None,
                body="b",
                source="s",
            ),
        ),
        working_memory=WorkingMemory(goals=("g",), state_fields={}, base_token_cost=1000),
        invocation=InvocationPolicy(
            invoked_on_stages=("retrieve", "read"), max_cards_per_stage=2, per_card_token_cost=1500
        ),
        checkers=neutral_seed_package().checkers,
    )
    (agent_dir / MEMORY_PACKAGE_FILENAME).write_bytes(heavy.to_bytes())
    # Budget 2000: cap 1 usage is 1000 + 2*1500 = 4000 > 2000 -> no repair.
    tight = RecurisStyleImprover(byte_cap=BYTE_CAP, token_budget=2000)
    out = _apply_round(tight, agent_dir, state_path, 0, _feedback(_usage_anomaly()))
    assert out.agent_files_changed == {}
    state = json.loads(state_path.read_bytes())
    assert state["accepted"] == []
    assert len(state["rejected"]) == 1
    assert "does not repair" in state["rejected"][0]["reason"]


def test_gate_blocks_a_repairing_patch_that_regresses(agent_dir: Path, state_path: Path) -> None:
    """Repair alone is not enough: a previous-round regression blocks admission.

    Round 0: a usage anomaly the seed package already repairs (usage within
    budget) — recorded as the replay set. Round 1: a stage failure whose E
    card would push projected usage over budget, so the patched package no
    longer repairs the round-0 signal. The gate must block (reg_cap=0).
    """

    # Base 1000, per-card 600, cap 1: seed usage 1000 <= 1600 (round 0
    # repairs). After the E patch: 1000 + 600 = 1600 > 1550 (regresses).
    seed = MemoryPackage(
        name="neutral",
        entries=(),
        working_memory=WorkingMemory(goals=("g",), state_fields={}, base_token_cost=1000),
        invocation=InvocationPolicy(
            invoked_on_stages=("retrieve", "read", "verify", "synthesize"),
            max_cards_per_stage=1,
            per_card_token_cost=600,
        ),
        checkers=neutral_seed_package().checkers,
    )
    improver_local = RecurisStyleImprover(byte_cap=BYTE_CAP, token_budget=1550, seed_package=seed)
    first = _apply_round(improver_local, agent_dir, state_path, 0, _feedback(_usage_anomaly()))
    assert first.agent_files_changed == {}  # seed already repairs: nothing to do

    out = _apply_round(improver_local, agent_dir, state_path, 1, _feedback(_stage_failure()))
    assert out.agent_files_changed == {}
    state = json.loads(state_path.read_bytes())
    assert state["accepted"] == []
    assert len(state["rejected"]) == 1
    assert "regress" in state["rejected"][0]["reason"]
    # The package on disk is unchanged: the rejected patch was discarded.
    assert not (agent_dir / MEMORY_PACKAGE_FILENAME).exists()


def test_gate_replays_previous_feedback_through_patched_package(
    improver: RecurisStyleImprover, agent_dir: Path, state_path: Path
) -> None:
    """The regression check is a genuine replay: prev signals are re-evaluated."""

    # Round 0 accepts an E card for verify (usage stays in budget).
    _apply_round(improver, agent_dir, state_path, 0, _feedback(_stage_failure()))
    state_after_0 = json.loads(state_path.read_bytes())
    assert len(state_after_0["accepted"]) == 1
    # Round 1 carries the round-0 signal in its replay set.
    assert len(state_after_0["previous_feedback"]["signals"]) == 1
    assert state_after_0["previous_feedback"]["signals"][0]["kind"] == "stage_failure"


def test_rejected_patch_is_not_reproposed_ledger(agent_dir: Path, state_path: Path) -> None:
    """The do-not-repeat ledger blocks re-proposing a regressed patch."""

    seed = MemoryPackage(
        name="neutral",
        entries=(),
        working_memory=WorkingMemory(goals=("g",), state_fields={}, base_token_cost=1000),
        invocation=InvocationPolicy(
            invoked_on_stages=("retrieve", "read", "verify", "synthesize"),
            max_cards_per_stage=1,
            per_card_token_cost=600,
        ),
        checkers=neutral_seed_package().checkers,
    )
    improver_local = RecurisStyleImprover(byte_cap=BYTE_CAP, token_budget=1550, seed_package=seed)
    # Round 0: usage anomaly the seed repairs (no-op round, replay set set).
    _apply_round(improver_local, agent_dir, state_path, 0, _feedback(_usage_anomaly()))
    # Round 1: E patch that regresses -> rejected into the ledger.
    _apply_round(improver_local, agent_dir, state_path, 1, _feedback(_stage_failure()))
    state = json.loads(state_path.read_bytes())
    assert len(state["rejected"]) == 1
    rejected_key = (
        state["rejected"][0]["record"]["component"],
        state["rejected"][0]["record"]["action"],
        state["rejected"][0]["record"]["target"],
    )
    assert rejected_key == ("E", "add_card", "verify_verify_citations")
    # Round 2: the same failure re-appears; the ledger blocks the same patch.
    round_input = _make_round(agent_dir, state_path, 2, _feedback(_stage_failure()))
    reason = improver_local.gate_reason_of(round_input)
    assert reason == "ledger blocks a repeat of a previous patch"


# --- Group 5d: state contract ---


def test_memory_package_round_trips_through_the_arm(
    improver: RecurisStyleImprover, agent_dir: Path, state_path: Path
) -> None:
    """Package -> agent file -> parse back yields the identical package."""

    _apply_round(improver, agent_dir, state_path, 0, _feedback(_stage_failure()))
    _apply_round(improver, agent_dir, state_path, 1, _feedback(_state_field()))
    on_disk = (agent_dir / MEMORY_PACKAGE_FILENAME).read_bytes()
    parsed = MemoryPackage.from_bytes(on_disk)
    assert MemoryPackage.from_bytes(parsed.to_bytes()).to_bytes() == on_disk
    assert parsed.entries[0].id == "verify_verify_citations"
    assert "open_queries" in parsed.working_memory.state_fields


def test_participant_state_round_trips(
    improver: RecurisStyleImprover, agent_dir: Path, state_path: Path
) -> None:
    """State bytes parse back into the same ledger and replay set."""

    _apply_round(improver, agent_dir, state_path, 0, _feedback(_stage_failure()))
    loaded = ParticipantState.load(state_path)
    assert len(loaded.accepted) == 1
    assert loaded.accepted[0].key == ("E", "add_card", "verify_verify_citations")
    assert loaded.last_round_index == 0
    assert len(loaded.previous_feedback.signals) == 1
    re_encoded = ParticipantState.from_mapping(loaded.to_mapping())
    assert re_encoded.to_bytes() == state_path.read_bytes()


def test_corrupt_state_fails_loudly(
    improver: RecurisStyleImprover, agent_dir: Path, state_path: Path
) -> None:
    """Participant-authored state is re-validated at load: no silent reset."""

    state_path.write_bytes(b"{not json")
    with pytest.raises(RecurisArmError, match="not valid JSON"):
        improver.improve(_make_round(agent_dir, state_path, 0, _feedback(_stage_failure())))


def test_malformed_feedback_yields_no_patch(
    improver: RecurisStyleImprover, agent_dir: Path, state_path: Path
) -> None:
    """Unknown/unparseable feedback is tolerated: a round that admits nothing."""

    for bad in (b"", b"not json", b'{"signals": "no"}', b'{"signals": [{"kind": "mystery"}]}'):
        out = _apply_round(improver, agent_dir, state_path, 0, bad)
        assert out.agent_files_changed == {}
        assert out.state_update is not None


def test_state_respects_byte_cap(agent_dir: Path, state_path: Path) -> None:
    """The arm refuses to emit state the declared cap cannot hold."""

    improver = RecurisStyleImprover(byte_cap=10, token_budget=TOKEN_BUDGET)
    with pytest.raises(RecurisArmError, match="byte cap"):
        improver.improve(_make_round(agent_dir, state_path, 0, _feedback(_stage_failure())))


# --- Group 5e: strategy code stays byte-frozen ---


def test_agent_strategy_code_byte_frozen(
    improver: RecurisStyleImprover, agent_dir: Path, state_path: Path
) -> None:
    """Only the memory-package data file changes; no agent .py is touched."""

    strategy_before = (agent_dir / "strategy.py").read_bytes()
    outputs = []
    outputs.append(_apply_round(improver, agent_dir, state_path, 0, _feedback(_stage_failure())))
    outputs.append(_apply_round(improver, agent_dir, state_path, 1, _feedback(_state_field())))
    outputs.append(_apply_round(improver, agent_dir, state_path, 2, _feedback(_usage_anomaly())))
    assert (agent_dir / "strategy.py").read_bytes() == strategy_before
    for output in outputs:
        for relative in output.agent_files_changed:
            assert relative == MEMORY_PACKAGE_FILENAME
            assert relative.endswith(".json")


def test_usage_is_accounted_every_round(
    improver: RecurisStyleImprover, agent_dir: Path, state_path: Path
) -> None:
    """Every round reports a UsageReport; zero model tokens, real wall time."""

    out = _apply_round(improver, agent_dir, state_path, 0, _feedback(_stage_failure()))
    assert isinstance(out.usage.input_tokens, int)
    assert out.usage.input_tokens == 0 and out.usage.output_tokens == 0
    assert out.usage.wall_seconds >= 0.0
    assert len(improver.usage_reports()) == 1


# --- Group 5f: determinism ---


def test_identical_rounds_produce_identical_outputs(tmp_path: Path) -> None:
    """Two arms from the same seed see byte-identical file and state bytes."""

    streams = []
    for copy in ("a", "b"):
        agent_dir = tmp_path / f"agent-{copy}"
        agent_dir.mkdir()
        state_path = tmp_path / f"state-{copy}.json"
        improver = RecurisStyleImprover(byte_cap=BYTE_CAP, token_budget=TOKEN_BUDGET)
        file_bytes = []
        state_bytes = []
        for index, feedback in enumerate(
            [
                _feedback(_stage_failure()),
                _feedback(_state_field()),
                _feedback(_usage_anomaly()),
            ]
        ):
            out = _apply_round(improver, agent_dir, state_path, index, feedback)
            file_bytes.append(
                (agent_dir / MEMORY_PACKAGE_FILENAME).read_bytes()
                if MEMORY_PACKAGE_FILENAME in out.agent_files_changed
                else b""
            )
            state_bytes.append(out.state_update or b"")
        streams.append((tuple(file_bytes), tuple(state_bytes)))
    assert streams[0] == streams[1]


# --- Group 5g: package validation ---


def test_memory_package_rejects_wrong_shape() -> None:
    """The package loader re-validates shape: no silently disabled components."""

    seed = neutral_seed_package()
    payload = seed.to_mapping()
    del payload["rho"]
    with pytest.raises(RecurisArmError, match="keys must be exactly"):
        MemoryPackage.from_mapping(payload)
    # A wrong card type is rejected at parse, not silently accepted.
    card = EEntry(
        id="x",
        type="procedure",
        stage="verify",
        handles=("h",),
        requires_field=None,
        body="b",
        source="s",
    )
    bad_card = card.to_mapping()
    bad_card["type"] = "alien"
    with pytest.raises(RecurisArmError, match="card type"):
        EEntry.from_mapping(bad_card)


def test_seed_package_is_neutral_and_deterministic() -> None:
    """The neutral seed is empty-E and byte-stable across calls."""

    first = neutral_seed_package()
    second = neutral_seed_package()
    assert first.entries == ()
    assert first.to_bytes() == second.to_bytes()
    assert first.checkers.gate == "repair_and_regression"
    assert first.checkers.reg_cap == 0


def test_ledger_blocks_accepted_and_rejected_keys() -> None:
    """Direct unit check of the do-not-repeat ledger."""

    record = PatchRecord(
        component="E",
        action="add_card",
        target="verify_verify_citations",
        trigger_signal_id="stage_failure:i2:verify:verify_citations",
        evidence_signal_ids=("stage_failure:i2:verify:verify_citations",),
    )
    fresh = ParticipantState()
    assert not fresh.ledger_blocks(record.key)
    advanced = fresh.advance(
        report=FeedbackReport(),
        round_index=0,
        record=record,
        accepted=True,
    )
    assert advanced.ledger_blocks(record.key)
    rejected_state = fresh.advance(
        report=FeedbackReport(),
        round_index=0,
        record=record,
        accepted=False,
        reason="regressed",
    )
    assert rejected_state.ledger_blocks(record.key)
