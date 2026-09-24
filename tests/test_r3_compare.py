"""r3 unified-entry acceptance tests — the three-group artifact shape."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

ARM_KEYS = {
    "baseline",
    "unassisted_update",
    "non_adaptive_search",
    "recuris_s0_matched",
    "recuris_adapted",
}


def _artifact() -> dict[str, Any]:
    artifact = Path("artifacts/rsi-core-v1/r3-comparison.json")
    if not artifact.exists():
        import subprocess

        subprocess.run(
            [
                sys.executable,
                "scripts/r3_compare.py",
                "--offline",
                "--output",
                str(artifact),
            ],
            check=True,
            capture_output=True,
        )
    return cast(dict[str, Any], json.loads(artifact.read_text()))


def test_r3_artifact_shape() -> None:
    payload = _artifact()
    assert set(payload["groups"]) == {"A", "B", "C"}
    for group_id, group in payload["groups"].items():
        assert set(group["arms"]) == ARM_KEYS, (group_id, group["arms"].keys())
        # Every eval cell carries the GroupRun contract fields.
        for arm, cells in group["arms"].items():
            run = cells["eval"]
            for field in (
                "passed",
                "decisions",
                "model_calls",
                "model_tokens_in",
                "model_tokens_out",
                "policy_errors",
            ):
                assert field in run, (group_id, arm, field)
        # Per-group deltas + four-outcome; the aggregate is a CONJUNCTION.
        assert set(group["deltas"]) == {
            "update_vs_baseline",
            "search_vs_baseline",
            "recuris_vs_s0matched",
        }
        assert group["four_outcome"] in ("improves", "ties", "regresses")
    assert payload["aggregate_four_outcome"] in ("improves", "ties", "regresses")


def test_r3_group_shapes_and_decision_keys() -> None:
    payload = _artifact()
    assert payload["groups"]["A"]["shape"] == "lifecycle"
    assert payload["groups"]["B"]["shape"] == "sequence"
    assert payload["groups"]["C"]["shape"] == "sequence"
    # A: three decisions; B: six; C: two (per-session recovery).
    assert set(payload["groups"]["A"]["arms"]["baseline"]["eval"]["decisions"]) == {
        "award",
        "followup_1",
        "followup_2",
    }
    b_dec = payload["groups"]["B"]["arms"]["baseline"]["eval"]["decisions"]
    assert set(b_dec) == {
        "s1_award",
        "s2_calibration",
        "s2_currency",
        "s2_reaward_fresh",
        "s3_award",
        "s3_calibration",
    }
    assert set(payload["groups"]["C"]["arms"]["baseline"]["eval"]["decisions"]) == {
        "c1_recovery",
        "c2_recovery",
    }


def test_r3_offline_all_arms_recorded_with_cost() -> None:
    payload = _artifact()
    for _group_id, group in payload["groups"].items():
        # The improver's rounds + meta attempts + internal dev runs are
        # recorded per group (the cost ledger the contract governs).
        rec = group["arms"]["recuris_adapted"]["improver_record"]
        assert len(rec["rounds"]) == 2
        assert "meta_attempts" in rec and "dev_runs_internal" in rec
        assert "final_package" in group["arms"]["recuris_adapted"]
        # Search candidates recorded with usability.
        candidates = group["arms"]["non_adaptive_search"]["candidates"]
        assert len(candidates) == 3


def test_r3_live_mode_requires_key() -> None:
    import os
    import subprocess

    env = dict(os.environ)
    env.pop("SIFLOW_API_KEY", None)
    out = Path("artifacts/rsi-core-v1/tmp-r3-skip.json")
    if out.exists():
        out.unlink()
    result = subprocess.run(
        [sys.executable, "scripts/r3_compare.py", "--output", str(out)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2
    assert not out.exists()


def test_r3_eval_runs_use_heldout_worlds(monkeypatch: Any) -> None:
    """Stats-contract §4: the eval cells must run the EVAL twin worlds,
    never the dev worlds. Regression for the conflation where
    _run_arm_on_group ignored the phase and every eval_* cell re-ran
    spec.dev_worlds (found before the first live r3 run; the run was
    killed and no artifact written).
    """

    from r3_compare import GroupSpec, _run_arm_on_group

    class _FakeInst:
        instance_id = "fake-a-inst"

    spec = GroupSpec(
        "A",
        [_FakeInst()],
        [_FakeInst()],
        shape="lifecycle",
        turns=1,
        baseline_policy="",
        dev_experience_stages=[],
    )
    spec.eval_worlds[0].instance_id = "fake-a-eval"
    seen: dict[str, object] = {}

    def _fake_run_arm(
        policy_text: str,
        inst: Any,
        responder: Any,
        max_turns: int = 2,
        initial_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        seen[inst.instance_id] = policy_text
        return {"instance_id": inst.instance_id, "passed": True, "decisions": {}}

    import r3_compare

    monkeypatch.setattr(r3_compare, "_run_arm", _fake_run_arm)
    dev_run = _run_arm_on_group(spec, "policy-dev", None)
    eval_run = _run_arm_on_group(spec, "policy-eval", None, phase="eval")
    assert dev_run["instance_id"] == "fake-a-inst"
    assert eval_run["instance_id"] == "fake-a-eval"


def test_r3_b_group_eval_twin_is_full_reverse_triple() -> None:
    """B's eval worlds must be the full b1-reverse triple (worlds
    swapped), not one reverse session mixed with two dev sessions."""

    from r3_compare import _b_worlds

    dev, ev = _b_worlds()
    dev_ids = [i.instance_id for i in dev]
    ev_ids = [i.instance_id for i in ev]
    assert dev_ids == [
        "research-v5-b1-s1-0001",
        "research-v5-b1-s2-0001",
        "research-v5-b1-s3-0001",
    ]
    assert ev_ids == [
        "research-v5-b1r-s1-0001",
        "research-v5-b1r-s2-0001",
        "research-v5-b1r-s3-0001",
    ]
    assert not set(dev_ids) & set(ev_ids)


def test_r3_c_group_eval_twin_is_mirror_pair() -> None:
    """C's eval worlds must be the c1-mirror pair."""

    from r3_compare import _c_worlds

    dev, ev = _c_worlds()
    dev_ids = [i.instance_id for i in dev]
    ev_ids = [i.instance_id for i in ev]
    assert dev_ids == ["research-v5-c1-s1-0001", "research-v5-c1-s2-0001"]
    assert ev_ids == ["research-v5-c1m-s1-0001", "research-v5-c1m-s2-0001"]
    assert not set(dev_ids) & set(ev_ids)


def test_r3_four_outcome_fixed_sufficient() -> None:
    """The four-outcome classification keeps r2a's semantics:
    fixed-sufficient is a distinct, publishable class."""

    from r3_compare import _four_outcome

    assert _four_outcome(1, 0, False) == "improves"
    assert _four_outcome(1, -1, False) == "improves"
    assert _four_outcome(-1, 0, False) == "regresses"
    assert _four_outcome(0, 0, True) == "fixed-sufficient"
    assert _four_outcome(0, 1, True) == "fixed-sufficient"
    assert _four_outcome(0, 0, False) == "ties"
    # Dev regression with no eval gain is a regression, not a tie.
    assert _four_outcome(0, -1, False) == "regresses"


def test_r3_dev_experience_union_failures() -> None:
    """The researcher's experience payload carries failures from BOTH
    GroupRun spellings (A's `failures`, B/C's `failure_detail`)."""

    from r3_compare import GroupSpec, _dev_experience

    spec = GroupSpec(
        "B", [], [], shape="sequence", turns=2, baseline_policy="", dev_experience_stages=[]
    )
    run = {
        "passed": False,
        "decisions": {"s1_award": False},
        "failure_detail": {"s1_award": ["commit gate[corridor-reaward]"]},
    }
    exp = _dev_experience(spec, run)
    assert exp["failures"] == ["commit gate[corridor-reaward]"]
    run2 = {"passed": True, "decisions": {}, "failures": ["commit gate"]}
    exp2 = _dev_experience(spec, run2)
    assert exp2["failures"] == ["commit gate"]


def test_r3_sequence_project_state_and_carry_boundary(monkeypatch: Any) -> None:
    """B continues its first project, then starts a new one; only carry survives."""

    import r3_compare
    from r3_compare import GroupSpec, _b_worlds, _run_arm_on_group

    from rsicontext.lifecycle.session_sequence import run_session_sequence as original_sequence

    dev, ev = _b_worlds()
    spec = GroupSpec(
        "B", dev, ev, shape="sequence", turns=1, baseline_policy="", dev_experience_stages=[]
    )
    seen_envs: list[Any] = []
    seen_states: list[dict[str, Any]] = []
    original_hook = r3_compare._make_hook

    def record_sequence(*args: Any, **kwargs: Any) -> Any:
        seen_envs.extend(kwargs["envs"])
        return original_sequence(*args, **kwargs)

    def record_hook(
        policy_text: Any, state: dict[str, Any], budget: Any, registry: Any, responder: Any
    ) -> Any:
        seen_states.append({key: value for key, value in state.items()})
        return original_hook(policy_text, state, budget, registry, responder)

    monkeypatch.setattr(r3_compare, "run_session_sequence", record_sequence)
    monkeypatch.setattr(r3_compare, "_make_hook", record_hook)
    policy = """
def on_turn(turn):
    if turn.view.kind == "survey":
        turn.state["scratch"] = "session-local"
    if turn.view.kind == "session_end":
        turn.state["carry"] = {"marker": "persisted"}
    return {"pack_text": "ok"}
"""
    _run_arm_on_group(spec, policy, None, initial_state={"recuris_memory": {"marker": "injected"}})
    assert seen_envs[0] is seen_envs[1]
    assert seen_envs[1] is not seen_envs[2]
    assert seen_states[0]["carry"] == {}
    assert seen_states[1]["carry"] == {"marker": "persisted"}
    assert seen_states[2]["carry"] == {"marker": "persisted"}
    assert all(state["recuris_memory"] == {"marker": "injected"} for state in seen_states)
    assert all("scratch" not in state for state in seen_states)


def test_r3_sequence_rejects_non_memory_initial_state() -> None:
    from r3_compare import GroupSpec, _c_worlds, _run_arm_on_group

    dev, ev = _c_worlds()
    spec = GroupSpec(
        "C", dev, ev, shape="sequence", turns=1, baseline_policy="", dev_experience_stages=[]
    )
    cases: tuple[dict[str, object], ...] = (
        {"carry": {"forged": True}},
        {"scratch": "forged"},
    )
    for initial_state in cases:
        try:
            _run_arm_on_group(
                spec,
                "def on_turn(turn):\n    return {'pack_text': 'ok'}\n",
                None,
                initial_state=initial_state,
            )
        except ValueError as exc:
            assert "only accepts recuris_memory" in str(exc)
        else:
            raise AssertionError("unexpected initial state was accepted")


def test_r3_c_sessions_share_project_state(monkeypatch: Any) -> None:
    import r3_compare
    from r3_compare import GroupSpec, _c_worlds, _run_arm_on_group

    from rsicontext.lifecycle.session_sequence import run_session_sequence as original_sequence

    dev, ev = _c_worlds()
    spec = GroupSpec(
        "C", dev, ev, shape="sequence", turns=1, baseline_policy="", dev_experience_stages=[]
    )
    seen_envs: list[Any] = []

    def record_sequence(*args: Any, **kwargs: Any) -> Any:
        seen_envs.extend(kwargs["envs"])
        return original_sequence(*args, **kwargs)

    monkeypatch.setattr(r3_compare, "run_session_sequence", record_sequence)
    _run_arm_on_group(spec, "def on_turn(turn):\n    return {'pack_text': 'ok'}\n", None)
    assert seen_envs[0] is seen_envs[1]


def test_r3_sequence_memory_reaches_each_session_prompt(monkeypatch: Any) -> None:
    import r3_compare
    from r2a_compare import _offline_responder
    from r3_compare import GroupSpec, _b_worlds, _c_worlds, _run_arm_on_group

    from rsicontext.lifecycle.recuris_memory_policy import recuris_memory_policy_text
    from rsicontext.lifecycle.session_sequence import run_session_sequence as original_sequence
    from rsicontext.participant.recuris_real_arm import R2B_NEUTRAL_SEED, package_to_state

    package = json.loads(json.dumps(R2B_NEUTRAL_SEED))
    package["entries"] = [
        {
            "id": "probe-card",
            "body": "probe memory delivery",
            "stage": "act_verify",
            "requires_field": None,
        }
    ]
    records: list[Any] = []

    def record_sequence(*args: Any, **kwargs: Any) -> Any:
        record = original_sequence(*args, **kwargs)
        records.append(record)
        return record

    monkeypatch.setattr(r3_compare, "run_session_sequence", record_sequence)
    for group_id, builder, turns in (("B", _b_worlds, 2), ("C", _c_worlds, 3)):
        dev, ev = builder()
        spec = GroupSpec(
            group_id,
            dev,
            ev,
            shape="sequence",
            turns=turns,
            baseline_policy="",
            dev_experience_stages=[],
        )
        run = _run_arm_on_group(
            spec,
            recuris_memory_policy_text(),
            _offline_responder,
            initial_state=package_to_state(package),
        )
        assert len(records[-1].sessions) == len(dev)
        for session in records[-1].sessions:
            assert any(
                isinstance(entry, dict) and "probe-card" in entry.get("card_ids", [])
                for entry in session.final_memory_delivered
            )
            assert any(
                "[probe-card] probe memory delivery" in str(call["prompt_head"])
                for call in session.model_transcript
                if call["stage_kind"] == "act_verify"
            )
        assert cast(dict[str, Any], run["final_state"])["memory_delivered"]


def test_r3_b_entry_baseline_preserves_first_project_outcome() -> None:
    from r2a_compare import _offline_responder
    from r3_compare import GroupSpec, _b_worlds, _run_arm_on_group

    from rsicontext.lifecycle.group_baselines import group_b_basline_policy_text

    dev, ev = _b_worlds()
    spec = GroupSpec(
        "B", dev, ev, shape="sequence", turns=2, baseline_policy="", dev_experience_stages=[]
    )
    run = _run_arm_on_group(spec, group_b_basline_policy_text(), _offline_responder)
    assert run["passed"] is True
    decisions = cast(dict[str, bool], run["decisions"])
    assert len(decisions) == 6
    assert all(decisions.values()), run["failure_detail"]


def test_r3_b_decision_feedback_contains_failure_strings() -> None:
    from r3_compare import GroupSpec, _b_decision_rules, _dev_experience, _sequence_to_group_run

    from rsicontext.lifecycle.session_sequence import SequenceRecord, SessionRecord

    seq = SequenceRecord(
        sessions=[
            SessionRecord(0, "s1", True, failures=["commit gate[s1-award]: wrong carrier"]),
            SessionRecord(1, "s2", True, failures=["s9-followup-calibration: wrong supplier"]),
            SessionRecord(2, "s3", True, failures=[]),
        ]
    )
    _b_decision_rules(seq, [])
    assert seq.failure_detail == {
        "s1_award": ["commit gate[s1-award]: wrong carrier"],
        "s2_calibration": ["s9-followup-calibration: wrong supplier"],
    }
    run = _sequence_to_group_run(seq, None)
    spec = GroupSpec(
        "B", [], [], shape="sequence", turns=2, baseline_policy="", dev_experience_stages=[]
    )
    assert _dev_experience(spec, run)["failures"] == [
        "commit gate[s1-award]: wrong carrier",
        "s9-followup-calibration: wrong supplier",
    ]


def test_r3_b_live_shaped_failure_reaches_dev_feedback() -> None:
    from r3_compare import GroupSpec, _b_worlds, _dev_experience, _run_arm_on_group

    dev, ev = _b_worlds()
    spec = GroupSpec(
        "B", dev, ev, shape="sequence", turns=2, baseline_policy="", dev_experience_stages=[]
    )
    policy = "def on_turn(turn):\n    return {'pack_text': 'ok'}\n"
    run = _run_arm_on_group(spec, policy, None)
    decisions = cast(dict[str, bool], run["decisions"])
    assert decisions["s1_award"] is False
    details = cast(dict[str, list[str]], run["failure_detail"])["s1_award"]
    assert any("commit gate" in failure for failure in details)
    experience = _dev_experience(spec, run)
    failures = cast(list[str], experience["failures"])
    assert all(failure in failures for failure in details)


def test_r3_c_dev_feedback_contains_actual_failure_strings() -> None:
    from r3_compare import GroupSpec, _c_worlds, _dev_experience, _run_arm_on_group

    from rsicontext.participant.recuris_real_arm import build_trace_doc

    dev, ev = _c_worlds()
    spec = GroupSpec(
        "C", dev, ev, shape="sequence", turns=1, baseline_policy="", dev_experience_stages=[]
    )
    run = _run_arm_on_group(spec, "def on_turn(turn):\n    return {'pack_text': 'ok'}\n", None)
    detail = cast(dict[str, list[str]], run["failure_detail"])
    assert detail
    assert set(detail).issubset({"c1_recovery", "c2_recovery"})
    failures = cast(list[str], run["failures"])
    assert failures
    experience = _dev_experience(spec, run)
    assert experience["failures"] == failures
    assert build_trace_doc(run)["failures"] == failures


def test_r3_fresh_artifact_labels_worker_usage(tmp_path: Path) -> None:
    import subprocess

    output = tmp_path / "r3-offline.json"
    subprocess.run(
        [sys.executable, "scripts/r3_compare.py", "--offline", "--output", str(output)],
        check=True,
        capture_output=True,
    )
    payload = json.loads(output.read_text())
    assert payload["worker_usage_unit"] == "whitespace_word_estimate"
    assert payload["worker_usage_source"] == (
        "PolicyHook._ask_model local prompt/reply split; not provider token usage"
    )
    assert payload["worker_provider_usage_unit"] == "provider_reported_tokens"
    assert payload["worker_provider_usage_calls"] == []
    assert payload["worker_provider_usage_totals"]["usage_status"] == "not_applicable"
    identity = payload["run_identity"]
    assert len(identity["identity_sha256"]) == 64
    assert set(identity["materials"]) == {"A", "B", "C"}
    assert all(
        len(item["sha256"]) == 64
        for group in identity["materials"].values()
        for phase in ("dev", "eval")
        for item in group[phase]
    )
    assert payload["started_at_utc"] <= payload["completed_at_utc"]
    assert isinstance(payload["run_identity_end"]["matches_start"], bool)
    assert len(payload["run_identity_end"]["identity_sha256"]) == 64


def test_r3_identity_hashes_complete_material_without_disclosing_it(monkeypatch: Any) -> None:
    from r3_compare import GroupSpec, _run_identity

    class Material:
        instance_id = "same-id"

        def __init__(self, secret: str) -> None:
            self.secret = secret

        def to_dict(self) -> dict[str, object]:
            return {
                "instance_id": self.instance_id,
                "stages": [{"gold_evidence_ids": [self.secret]}],
                "sandbox_spec": {"oracle": self.secret},
            }

    monkeypatch.setattr("r3_compare._git_identity", lambda: {"head": "fixed"})
    monkeypatch.setattr("r3_compare._source_sha256", lambda: "fixed-source")

    def spec(secret: str) -> dict[str, GroupSpec]:
        return {
            "A": GroupSpec(
                "A",
                [Material(secret)],
                [Material("eval-label")],
                shape="lifecycle",
                turns=2,
                baseline_policy="policy",
                dev_experience_stages=[],
            )
        }

    first = cast(dict[str, Any], _run_identity(spec("gold-one"), live=False))
    repeat = _run_identity(spec("gold-one"), live=False)
    changed = cast(dict[str, Any], _run_identity(spec("gold-two"), live=False))
    assert first == repeat
    assert first["identity_sha256"] != changed["identity_sha256"]
    assert (
        first["materials"]["A"]["dev"][0]["sha256"] != changed["materials"]["A"]["dev"][0]["sha256"]
    )
    serialized = json.dumps(first)
    assert "gold-one" not in serialized
    assert "eval-label" not in serialized
    assert set(first) == {
        "schema_version",
        "git",
        "source_sha256",
        "uv_lock_sha256",
        "configuration_sha256",
        "mode",
        "models",
        "execution_parameters",
        "materials",
        "identity_sha256",
    }


def test_r3_identity_end_flags_source_drift(monkeypatch: Any) -> None:
    from r3_compare import GroupSpec, _identity_end_check, _run_identity

    class Material:
        instance_id = "instance"

        def to_dict(self) -> dict[str, object]:
            return {"instance_id": self.instance_id, "answer_norm": "evaluator-only"}

    source = {"sha256": "first"}
    monkeypatch.setattr("r3_compare._git_identity", lambda: {"head": "fixed"})
    monkeypatch.setattr("r3_compare._source_sha256", lambda: source["sha256"])
    specs = {
        "A": GroupSpec(
            "A",
            [Material()],
            [Material()],
            shape="lifecycle",
            turns=2,
            baseline_policy="policy",
            dev_experience_stages=[],
        )
    }
    start = _run_identity(specs, live=False)
    assert _identity_end_check(start, specs, live=False)["matches_start"] is True
    source["sha256"] = "changed"
    end = _identity_end_check(start, specs, live=False)
    assert end["matches_start"] is False
    assert end["identity_sha256"] != start["identity_sha256"]


def test_r3_policy_snapshots_reconstruct_delivered_bytes(tmp_path: Path) -> None:
    import subprocess

    output = tmp_path / "snapshots.json"
    subprocess.run(
        [sys.executable, "scripts/r3_compare.py", "--offline", "--output", str(output)],
        check=True,
        capture_output=True,
    )
    groups = json.loads(output.read_text())["groups"]
    for group in groups.values():
        snapshots = group["policy_snapshots"]
        assert len(snapshots["search_candidates"]) == 3
        for snapshot in (
            snapshots["baseline"],
            snapshots["unassisted_proposed"],
            snapshots["unassisted_delivered"],
            snapshots["search_delivered"],
            snapshots["recuris"],
            *snapshots["search_candidates"],
        ):
            encoded = snapshot["text"].encode("utf-8")
            assert snapshot["utf8_bytes"] == len(encoded)
            assert snapshot["sha256"] == hashlib.sha256(encoded).hexdigest()


def test_r3_sequence_provider_usage_is_scoped_to_one_cell() -> None:
    from r3_compare import GroupSpec, _b_worlds, _run_arm_on_group

    from rsicontext.lifecycle.group_baselines import group_b_basline_policy_text

    dev, ev = _b_worlds()
    spec = GroupSpec(
        "B",
        dev,
        ev,
        shape="sequence",
        turns=2,
        baseline_policy=group_b_basline_policy_text(),
        dev_experience_stages=[],
    )
    calls: list[dict[str, object]] = []

    def responder(prompt: str) -> str:
        calls.append(
            {
                "model": "test-worker",
                "model_echo": "test-worker",
                "outcome": "ok",
                "finish_reason": "stop",
                "usage_status": "reported",
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12,
            }
        )
        return "supplier=atlas-carriage"

    responder.usage_state = lambda: list(calls)  # type: ignore[attr-defined]
    first = _run_arm_on_group(spec, spec.baseline_policy, responder)
    first_count = len(cast(list[dict[str, object]], first["provider_usage_calls"]))
    assert first_count > 0
    second = _run_arm_on_group(spec, spec.baseline_policy, responder)
    second_count = len(cast(list[dict[str, object]], second["provider_usage_calls"]))
    assert second_count > 0
    assert len(calls) == first_count + second_count
    assert first["provider_usage_totals"] == {
        "usage_status": "reported",
        "prompt_tokens": first_count * 10,
        "completion_tokens": first_count * 2,
        "total_tokens": first_count * 12,
    }
    second_totals = cast(dict[str, object], second["provider_usage_totals"])
    assert second_totals["prompt_tokens"] == second_count * 10
    assert first["model_tokens_source"] == "word_estimate"


def test_r3_existing_output_is_rejected_before_work(tmp_path: Path) -> None:
    import subprocess

    output = tmp_path / "existing.json"
    output.write_text("sentinel")
    result = subprocess.run(
        [sys.executable, "scripts/r3_compare.py", "--offline", "--output", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "output already exists" in result.stderr
    assert output.read_text() == "sentinel"
