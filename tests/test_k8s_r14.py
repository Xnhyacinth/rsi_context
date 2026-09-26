"""Development controls for the pinned KEP-753 resource-order card."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import replace
from pathlib import Path

import pytest

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_k8s_r14 import SOURCE_FILES, build_k8s_resource_order_sessions
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle
from rsicontext.lifecycle.session_sequence import run_session_sequence
from rsicontext.lifecycle.spec import LifecycleInstance, canonical_instance_json
from rsicontext.session.state import canonical_state_bytes

_DEFAULT_SOURCE_ROOT = Path(
    "/volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753"
)
_FORMULA = "InitContainerUse(i) = Sum(sidecar containers with index < i) + InitContainer(i)"


def _source_root() -> Path:
    root = Path(os.environ.get("RSICONTEXT_K8S_SOURCE_ROOT", _DEFAULT_SOURCE_ROOT))
    if not root.is_dir():
        pytest.skip("set RSICONTEXT_K8S_SOURCE_ROOT to the pinned detached KEP checkout")
    return root


def _sessions() -> tuple[LifecycleInstance, LifecycleInstance]:
    return build_k8s_resource_order_sessions(_source_root())


def _verify(record_id: str, plan: str) -> Action:
    return Action(
        kind="request_verification",
        record_id=record_id,
        fields={"check": "resource-review", "subject": plan},
    )


def _commit(record_id: str, plan: str, receipt: str) -> tuple[Action, Action]:
    return (
        Action(kind="create_record", record_id=record_id, fields={"plan": plan}),
        Action(
            kind="finalize", record_id=record_id, fields={"status": "final"}, provenance=(receipt,)
        ),
    )


class ResourceHook:
    """Scripted source reader and arithmetic witness, never a model result."""

    def __init__(self, state: dict[str, object] | None = None, *, stale: bool = False) -> None:
        self.state = state if state is not None else {}
        carry = self.state.get("carry")
        self.carry: dict[str, object] = carry if isinstance(carry, dict) else {}
        self.state["carry"] = self.carry
        self.stale = stale
        self.phases: dict[str, int] = {}
        self.plans: dict[str, str] = {}

    def on_stage(self, stage: StageView) -> StageResponse:
        if stage.stage_id == "resource-source-survey":
            source = stage.documents[0].text
            self.carry["ordered_prefix_formula"] = _FORMULA in source
        elif stage.stage_id == "resource-request-stage":
            request = stage.documents[0].text
            assert "1000m CPU request capacity" in request
            assert re.search(r"sidecar S requests 300m; regular init A requests 800m", request)
            self.plans["resource_assessment"] = self._plan(("S", "A", "B"))
        elif stage.stage_id == "resource-order-change":
            amendment = stage.documents[0].text
            assert "A (800m), S (300m), B (500m)" in amendment
            self.plans["resource_reassessment"] = self._plan(("A", "S", "B"))
        elif stage.stage_id.startswith("decide-"):
            record_id = stage.stage_id.removeprefix("decide-")
            plan = self.plans[record_id]
            phase = self.phases.get(record_id, 0)
            self.phases[record_id] = phase + 1
            receipt_id = f"review-{record_id}"
            if phase >= 2 or (self.stale and record_id == "resource_reassessment" and phase >= 1):
                return StageResponse("decision submitted")
            if phase == 0:
                if self.stale and record_id == "resource_reassessment":
                    return StageResponse(
                        "reuse stale receipt", _commit(record_id, plan, "review-old")
                    )
                return StageResponse("request procedural review", (_verify(receipt_id, plan),))
            assert any(receipt.verdict == "pass" for receipt in stage.receipts)
            return StageResponse("commit computed plan", _commit(record_id, plan, receipt_id))
        return StageResponse("read visible material")

    def _plan(self, order: tuple[str, ...]) -> str:
        requests = {"S": 300, "A": 800, "B": 500}
        running_sidecars = 0
        init_peaks: list[int] = []
        for name in order:
            if name == "S":
                running_sidecars += requests[name]
            else:
                init_peaks.append(requests[name] + running_sidecars)
        if self.carry.get("ordered_prefix_formula"):
            effective = max(*init_peaks, running_sidecars + 400)
        else:
            # The KEP calls this the easiest conservative formula; it misses
            # the benefit when a large init runs before the first sidecar.
            effective = max(max(requests[name] for name in order if name != "S") + 300, 700)
        return "admit-at-1000m" if effective <= 1000 else "hold-at-1000m"


def _run(
    sessions: tuple[LifecycleInstance, LifecycleInstance],
    *,
    second_stale: bool = False,
) -> tuple[list[bool], ProjectState, list[dict[str, object]]]:
    env = ProjectState()
    states: list[dict[str, object]] = []

    def factory(state: dict[str, object]) -> ResourceHook:
        states.append(state)
        return ResourceHook(state, stale=second_stale and len(states) == 2)

    record = run_session_sequence(list(sessions), factory, envs=[env, env], max_turns_per_stage=3)
    return [session.passed for session in record.sessions], env, states


def test_pinned_source_and_material_identity() -> None:
    root = _source_root()
    for relative, expected in SOURCE_FILES.items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected
    raw = (root / "keps/sig-node/753-sidecar-containers/README.md").read_bytes()
    lines = raw.splitlines(keepends=True)
    span = b"".join(lines[760:798])
    assert hashlib.sha256(span).hexdigest() == (
        "335a67c7a8a77ce39322a2a0b575f68ac4c8bbaeeb665777d837878e852dc33b"
    )
    first, second = _sessions()
    assert _FORMULA in first.stages[0].documents[0].text
    assert first.stages[0].documents[0].source_url.endswith("#L761-L798")
    assert second.stages[1].rule_change_scope == ("resource-review",)
    for world, expected in (
        (first, "4565339a3636212ede2dd7fd3ef9e4f4d961e613c939a0f6c2a6010e3e96042a"),
        (second, "542cae04f4b34a356bf321771bc988590bb238dd49afad7250c69cd57100a99e"),
    ):
        assert hashlib.sha256(canonical_instance_json(world).encode()).hexdigest() == expected
    for document, size, expected in (
        (
            first.stages[1].documents[0],
            695,
            "9fc1271856509a0db74e1893a74fa6a965e38c4ce6d640468f6ac0b00903b391",
        ),
        (
            second.stages[1].documents[0],
            650,
            "979d1bc19950aec013ef0b81e2a664f1fd19b493314e00e907a264a8cff4ce0c",
        ),
    ):
        data = document.text.encode()
        assert len(data) == size
        assert hashlib.sha256(data).hexdigest() == expected


def test_order_change_recalculates_and_uses_fresh_receipt_after_reset() -> None:
    first, second = _sessions()
    passed, env, states = _run((first, second))
    assert passed == [True, True]
    assert states[1]["carry"] == {"ordered_prefix_formula": True}
    assert len(canonical_state_bytes(states[1]["carry"])) <= 65536
    assert env.records["resource_assessment"]["plan"] == "hold-at-1000m"
    assert env.records["resource_reassessment"]["plan"] == "admit-at-1000m"
    assert env.records["review-resource_assessment"]["protocol_revision"] == 1
    assert env.records["review-resource_reassessment"]["protocol_revision"] == 2


def test_source_formula_withheld_breaks_later_decision_without_changing_receipt() -> None:
    first, second = _sessions()
    survey = first.stages[0]
    source = survey.documents[0]
    withheld = replace(source, text="[[doc:kep753-resource-source]] source withheld")
    first = replace(first, stages=(replace(survey, documents=(withheld,)), *first.stages[1:]))
    passed, env, _states = _run((first, second))
    assert passed == [True, False]
    assert env.records["resource_reassessment"]["plan"] == "hold-at-1000m"
    assert env.records["review-resource_reassessment"]["verdict"] == "pass"


def test_scripted_literal_lookup_changes_but_equivalent_source_rule_remains() -> None:
    first, second = _sessions()
    survey = first.stages[0]
    source = survey.documents[0]
    assert _FORMULA in source.text
    targeted = replace(source, text=source.text.replace(_FORMULA, "[target formula withheld]"))
    # The README restates the ordered-prefix rule later. This intervention
    # checks the scripted hook's literal lookup, not rule-level dependence.
    assert "Sum(sidecar containers with index < i) + Max(" in targeted.text
    targeted_first = replace(
        first, stages=(replace(survey, documents=(targeted,)), *first.stages[1:])
    )
    targeted_pass, _env, _states = _run((targeted_first, second))
    assert targeted_pass == [True, False]

    unrelated = replace(source, text=source.text.replace("## Summary", "## Summary [index note]"))
    unrelated_first = replace(
        first, stages=(replace(survey, documents=(unrelated,)), *first.stages[1:])
    )
    unrelated_pass, _env, _states = _run((unrelated_first, second))
    assert unrelated_pass == [True, True]


def test_naive_formula_is_wrong_only_after_reorder() -> None:
    hook = ResourceHook({"carry": {"ordered_prefix_formula": False}})
    assert hook._plan(("S", "A", "B")) == "hold-at-1000m"
    assert hook._plan(("A", "S", "B")) == "hold-at-1000m"
    hook.carry["ordered_prefix_formula"] = True
    assert hook._plan(("S", "A", "B")) == "hold-at-1000m"
    assert hook._plan(("A", "S", "B")) == "admit-at-1000m"


def test_missing_prior_finalization_blocks_second_even_with_source_carry() -> None:
    _first, second = _sessions()
    env = ProjectState()
    hook = ResourceHook({"carry": {"ordered_prefix_formula": True}})
    result = run_lifecycle(second, hook, env, max_turns_per_stage=3)
    assert not result.final_check.passed
    assert any("absent at session start" in failure for failure in result.final_check.failures)


def test_stale_review_receipt_cannot_be_reused_after_amendment() -> None:
    first, second = _sessions()
    env = ProjectState()
    first_hook = ResourceHook()
    assert run_lifecycle(first, first_hook, env, max_turns_per_stage=3).final_check.passed
    env.apply(_verify("review-old", "admit-at-1000m"))
    second_hook = ResourceHook({"carry": first_hook.carry}, stale=True)
    result = run_lifecycle(second, second_hook, env, max_turns_per_stage=3)
    assert not result.final_check.passed
    assert any("stale" in failure for failure in result.final_check.failures)


def test_pinned_source_drift_refused(tmp_path: Path) -> None:
    root = _source_root()
    for relative in SOURCE_FILES:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((root / relative).read_bytes())
    readme = tmp_path / "keps/sig-node/753-sidecar-containers/README.md"
    readme.write_bytes(readme.read_bytes().replace(b"InitContainerUse(i)", b"OtherFormula(i)"))
    with pytest.raises(ValueError, match="pinned KEP-753 source mismatch"):
        build_k8s_resource_order_sessions(tmp_path)
