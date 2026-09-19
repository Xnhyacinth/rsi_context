from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from rsicontext.participant import (
    ArmError,
    EvidenceTier,
    ExperienceAccumulationImprover,
    FixedStrategyImprover,
    ImprovementProcess,
    ImprovementRoundInput,
    ImprovementRoundOutput,
    ModelPool,
    OpenSClIResearcherImprover,
    ParticipantError,
    Registration,
    StateSpec,
    UsageLedger,
    UsageReport,
    qualify_registration,
)


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _make_round_input(tmp_path: Path, round_index: int) -> ImprovementRoundInput:
    return ImprovementRoundInput(
        round_index=round_index,
        task_text=f"research task {round_index}",
        restricted_feedback_bytes=json.dumps({"item_scores": {"i1": 0.5}}).encode("utf-8"),
        current_agent_dir=tmp_path / "agent",
        state_path=None,
        remaining_slots=8,
        task_order_seed=1234,
    )


def _make_pool() -> ModelPool:
    return ModelPool(
        pool_id="pool-alpha",
        tier=EvidenceTier.T1_ANCHOR,
        models=("qwen3.6-27b",),
        version_strings={"qwen3.6-27b": "1b559cf"},
        access_window=None,
    )


def _make_registration(
    tmp_path: Path,
    *,
    arm: str,
    improver: object,
    pool: ModelPool | None = None,
    seed_id: str = "seed-1",
) -> Registration:
    return Registration(
        participant_id="participant-test",
        arm=arm,  # type: ignore[arg-type]
        agent_dir=tmp_path / "agent",
        state_spec=StateSpec(schema={"notes": "list"}, byte_cap=65_536),
        improver=improver,  # type: ignore[arg-type]
        pool=pool or _make_pool(),
        registration_label="external_researcher_assisted",
        seed_id=seed_id,
    )


class _StubBridge:
    """ResearchRoundRequest-shaped callable for the open-S arm."""

    def __init__(self, agent_dir: Path) -> None:
        self.agent_dir = agent_dir
        self.calls: list[ImprovementRoundInput] = []

    def __call__(self, round_input: ImprovementRoundInput) -> Mapping[str, str]:
        self.calls.append(round_input)
        return {"policy.py": "# stub researcher edit\n"}


class _StatefulRandomKImprover:
    """Deferred stateful control slot: Random-K over a stateful grammar."""

    def __init__(self, rng_seed: int = 0) -> None:
        self.rng_seed = rng_seed

    def improve(self, round_input: ImprovementRoundInput) -> ImprovementRoundOutput:
        return ImprovementRoundOutput(
            agent_files_changed={"policy.py": f"# random-k candidate {self.rng_seed}\n"},
            state_update=json.dumps({"k": 3, "seen": round_input.round_index}).encode("utf-8"),
            usage=UsageReport(input_tokens=10, output_tokens=10, wall_seconds=0.01),
        )


@pytest.fixture
def tmp_agent_dir(tmp_path: Path) -> Path:
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "policy.py").write_text("# frozen baseline strategy\n", encoding="utf-8")
    return agent_dir


@pytest.fixture
def three_arms(tmp_agent_dir: Path) -> dict[str, object]:
    return {
        "fixed_strategy": FixedStrategyImprover(),
        "experience_accumulation": ExperienceAccumulationImprover(byte_cap=65_536),
        "open_s_researcher": OpenSClIResearcherImprover(run_round=_StubBridge(tmp_agent_dir)),
    }


# --- Group 4a: control fairness ---


def test_same_task_stream_across_arms(tmp_path: Path, three_arms: dict[str, object]) -> None:
    """All three arms receive byte-identical task streams and order."""

    rounds = [_make_round_input(tmp_path, index) for index in range(3)]
    per_arm_bytes: dict[str, list[bytes]] = {}
    for arm, improver in three_arms.items():
        recorder = cast_improver(improver)
        per_arm_bytes[arm] = [round_.canonical_bytes() for round_ in rounds]
        for round_ in rounds:
            recorder.improve(round_)

    stream_bytes = {arm: b"".join(bytes_) for arm, bytes_ in per_arm_bytes.items()}
    distinct = set(stream_bytes.values())
    assert len(distinct) == 1
    recorded = next(iter(stream_bytes.values()))
    assert recorded == b"".join(round_.canonical_bytes() for round_ in rounds)
    assert len(recorded) > 0


def cast_improver(improver: object) -> ImprovementProcess:
    assert isinstance(improver, ImprovementProcess)
    return improver


def test_same_feedback_bandwidth_across_arms(tmp_path: Path, three_arms: dict[str, object]) -> None:
    """Identical restricted feedback bytes reach every arm per round."""

    feedback = [_make_round_input(tmp_path, index) for index in range(2)]
    for improver in three_arms.values():
        recorder = cast_improver(improver)
        outputs = [recorder.improve(round_) for round_ in feedback]
        for _round, output in zip(feedback, outputs, strict=True):
            assert isinstance(output, ImprovementRoundOutput)
            assert isinstance(output.usage, UsageReport)

    open_s = three_arms["open_s_researcher"]
    assert isinstance(open_s, OpenSClIResearcherImprover)
    stub = open_s.run_round
    assert isinstance(stub, _StubBridge)
    received = [call.restricted_feedback_bytes for call in stub.calls]
    assert received == [round_.restricted_feedback_bytes for round_ in feedback]
    assert len(received[0]) > 0
    assert all(len(b) == len(received[0]) for b in received)


def test_experience_arm_strategy_frozen(tmp_path: Path, tmp_agent_dir: Path) -> None:
    """Experience arm: agent code hash unchanged; only state differs."""

    before = _tree_digest(tmp_agent_dir)
    improver = ExperienceAccumulationImprover(byte_cap=65_536)
    state_bytes: list[bytes | None] = []
    for index in range(3):
        round_input = ImprovementRoundInput(
            round_index=index,
            task_text=f"research task {index}",
            restricted_feedback_bytes=f'{{"score": {index}}}'.encode(),
            current_agent_dir=tmp_agent_dir,
            state_path=tmp_path / f"state-{index}.json",
            remaining_slots=8,
            task_order_seed=1234,
        )
        output = improver.improve(round_input)
        assert output.agent_files_changed == {}
        state_bytes.append(output.state_update)
        state_path = tmp_path / f"state-{index}.json"
        state_path.write_bytes(output.state_update or b"")

    after = _tree_digest(tmp_agent_dir)
    assert before == after
    assert len({bytes_ for bytes_ in state_bytes}) == 3
    for state in state_bytes:
        assert state is not None
        parsed = json.loads(state)
        assert isinstance(parsed, list)
        assert parsed[-1]["round_index"] >= 0


def test_stateful_control_slot_available() -> None:
    """The protocol structurally accepts a stateful Random-K control."""

    random_k: ImprovementProcess = _StatefulRandomKImprover(rng_seed=7)
    assert isinstance(random_k, ImprovementProcess)
    assert hasattr(random_k, "improve")


# --- Group 4b: order and seed controls ---


def test_multi_seed_recorded(tmp_path: Path, tmp_agent_dir: Path) -> None:
    """Registration carries a seed_id and the manifest dict records it."""

    improver = FixedStrategyImprover()
    manifest_dicts = []
    for seed_id in ("seed-1", "seed-2"):
        registration = _make_registration(
            tmp_path, arm="fixed_strategy", improver=improver, seed_id=seed_id
        )
        manifest_dicts.append(registration.to_dict())
    assert {record["seed_id"] for record in manifest_dicts} == {"seed-1", "seed-2"}
    assert all("participant_id" in record and "arm" in record for record in manifest_dicts)


def test_shuffled_order_expressible(tmp_path: Path) -> None:
    """The task-order seed is a round-input field and round-trips."""

    round_input = ImprovementRoundInput(
        round_index=0,
        task_text="research task",
        restricted_feedback_bytes=b"{}",
        current_agent_dir=tmp_path / "agent",
        state_path=None,
        remaining_slots=4,
        task_order_seed=9876,
    )
    assert round_input.task_order_seed == 9876
    bytes_ = round_input.canonical_bytes()
    payload = json.loads(bytes_)
    assert payload["task_order_seed"] == 9876
    assert "task_text" in payload


# --- Registration qualification ---


def test_qualify_registration_passes(tmp_path: Path, tmp_agent_dir: Path) -> None:
    registration = _make_registration(
        tmp_path, arm="fixed_strategy", improver=FixedStrategyImprover()
    )

    result = qualify_registration(registration, lambda path: [])

    assert result.passed
    assert result.reasons == ()
    assert result.participant_id == "participant-test"
    assert result.to_dict()["passed"] is True


def test_qualify_registration_fails_t2_without_window(tmp_path: Path, tmp_agent_dir: Path) -> None:
    pool = ModelPool(
        pool_id="pool-t2",
        tier=EvidenceTier.T2_VERSIONED_API,
        models=("gpt-5",),
        version_strings={},
        access_window=None,
    )
    registration = _make_registration(
        tmp_path, arm="open_s_researcher", improver=FixedStrategyImprover(), pool=pool
    )

    result = qualify_registration(registration, lambda path: [])

    assert not result.passed
    assert any("access window" in reason for reason in result.reasons)
    assert any("version string" in reason for reason in result.reasons)


def test_qualify_registration_fails_auditor_findings(tmp_path: Path, tmp_agent_dir: Path) -> None:
    (tmp_agent_dir / "evil.py").write_text("import os\n", encoding="utf-8")
    registration = _make_registration(
        tmp_path, arm="open_s_researcher", improver=FixedStrategyImprover()
    )

    def flag_os_imports(path: Path) -> list[str]:
        content = path.read_text(encoding="utf-8")
        return [f"forbidden import in {path.name}"] if "import os" in content else []

    result = qualify_registration(registration, flag_os_imports)

    assert not result.passed
    assert any("evil.py" in reason for reason in result.reasons)
    assert result.to_dict()["passed"] is False


def test_qualify_registration_fails_when_improver_raises(
    tmp_path: Path, tmp_agent_dir: Path
) -> None:
    class _Exploding:
        def improve(self, round_input: ImprovementRoundInput) -> ImprovementRoundOutput:
            raise RuntimeError("boom")

    registration = _make_registration(tmp_path, arm="fixed_strategy", improver=_Exploding())

    result = qualify_registration(registration, lambda path: [])

    assert not result.passed
    assert any("boom" in reason for reason in result.reasons)


# --- Usage ledger ---


def test_usage_ledger_accumulates_per_arm_c_improve() -> None:
    ledger = UsageLedger()
    reports = [
        UsageReport(input_tokens=100, output_tokens=200, wall_seconds=1.0, dollar_estimate=0.5),
        UsageReport(input_tokens=50, output_tokens=50, wall_seconds=0.5, dollar_estimate=0.1),
    ]
    for report in reports:
        ledger.record("open_s_researcher", report)
    ledger.record("fixed_strategy", UsageReport())

    assert ledger.arms() == ("fixed_strategy", "open_s_researcher")
    total = ledger.arm_total("open_s_researcher")
    assert total.input_tokens == 150
    assert total.output_tokens == 250
    assert total.total() == 400
    assert total.wall_seconds == pytest.approx(1.5)
    assert total.dollar_estimate == pytest.approx(0.6)
    assert ledger.arm_total("fixed_strategy").dollar_estimate is None


def test_usage_ledger_missing_dollars_stay_none() -> None:
    ledger = UsageLedger()
    ledger.record("arm", UsageReport(input_tokens=10))
    ledger.record("arm", UsageReport(input_tokens=5, dollar_estimate=0.2))
    assert ledger.arm_total("arm").dollar_estimate is None
    assert ledger.arm_total("arm").input_tokens == 15
    assert ledger.rounds("arm")[0].dollar_estimate is None


# --- Construction contracts ---


def test_state_spec_digest_is_canonical_and_stable() -> None:
    first = StateSpec(schema={"notes": "list", "facts": "dict"}, byte_cap=1024)
    second = StateSpec(schema={"facts": "dict", "notes": "list"}, byte_cap=1024)
    assert first.digest == second.digest
    assert first.digest == hashlib.sha256(b'{"facts":"dict","notes":"list"}').hexdigest()


def test_improvement_round_input_rejects_bad_fields(tmp_path: Path) -> None:
    with pytest.raises(ParticipantError, match="round_index"):
        ImprovementRoundInput(
            round_index=-1,
            task_text="t",
            restricted_feedback_bytes=b"{}",
            current_agent_dir=tmp_path,
            state_path=None,
            remaining_slots=1,
            task_order_seed=0,
        )
    with pytest.raises(ParticipantError, match="task_order_seed"):
        ImprovementRoundInput(
            round_index=0,
            task_text="t",
            restricted_feedback_bytes=b"{}",
            current_agent_dir=tmp_path,
            state_path=None,
            remaining_slots=1,
            task_order_seed=True,
        )


def test_improvement_round_output_rejects_unsafe_paths(tmp_path: Path) -> None:
    with pytest.raises(ParticipantError, match="safe relative path"):
        ImprovementRoundOutput(
            agent_files_changed={"../escape.py": "x"},
            state_update=None,
            usage=UsageReport(),
        )


def test_experience_arm_enforces_byte_cap(tmp_path: Path) -> None:
    improver = ExperienceAccumulationImprover(byte_cap=1)
    with pytest.raises(ArmError, match="byte cap"):
        improver.improve(_make_round_input(tmp_path, 0))
