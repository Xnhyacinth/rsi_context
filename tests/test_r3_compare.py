"""r3 unified-entry acceptance tests — the three-group artifact shape."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

ARM_KEYS = {
    "baseline",
    "unassisted_update",
    "non_adaptive_search",
    "recuris_s0_matched",
    "recuris_adapted",
}


def _artifact() -> dict:
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
    return json.loads(artifact.read_text())


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
    for group_id, group in payload["groups"].items():
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


def test_r3_eval_runs_use_heldout_worlds() -> None:
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

    def _fake_run_arm(policy_text, inst, responder, initial_state=None, max_turns=2):
        seen[inst.instance_id] = policy_text
        return {"instance_id": inst.instance_id, "passed": True, "decisions": {}}

    import r3_compare

    original = r3_compare._run_arm
    r3_compare._run_arm = _fake_run_arm
    try:
        dev_run = _run_arm_on_group(spec, "policy-dev", None)
        eval_run = _run_arm_on_group(spec, "policy-eval", None, phase="eval")
    finally:
        r3_compare._run_arm = original
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
