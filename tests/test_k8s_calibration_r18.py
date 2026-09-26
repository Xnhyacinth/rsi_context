"""R18 short-input calibration contracts use pinned artifacts and fake SSE."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import cast

import pytest

from rsicontext.analysis.chat_geometry import ChatTokenizer
from rsicontext.analysis.k8s_calibration_r18 import (
    CASE_ORDER,
    R17_TASK_SHA256,
    REGISTRY_SHA256,
    build_registration,
    interpret_reply,
    projected_rule,
    prompts,
    require_r17_observation,
)
from rsicontext.analysis.k8s_diagnostic_r17 import amendment_text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import r15_exact_profile_canary as canary  # noqa: E402
import r18_kep_calibration_offline as offline  # noqa: E402

SOURCE = Path(
    os.environ.get(
        "RSICONTEXT_K8S_SOURCE_ROOT",
        "/volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753",
    )
)
R16_TASK = Path(
    os.environ.get(
        "RSICONTEXT_R16_KEP_TASK",
        "/volume/pt-dev/qjiu/rsi_context_external/r16-paid-runs/kep-development-v1/task.json",
    )
)
R17_TASK = Path(
    os.environ.get(
        "RSICONTEXT_R17_KEP_TASK",
        "/volume/pt-dev/qjiu/rsi_context_external/r17-paid-runs/"
        "kep-arithmetic-diagnostic-v1/task.json",
    )
)
TOKENIZER = Path(
    os.environ.get(
        "RSICONTEXT_QWEN_TOKENIZER_ROOT",
        "/volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b",
    )
)


def _historical_registry_matches() -> bool:
    current = hashlib.sha256((ROOT / "configs/registry.json").read_bytes()).hexdigest()
    return current == REGISTRY_SHA256


def _require_historical_registry() -> None:
    if not _historical_registry_matches():
        pytest.skip("R18 calibration requires its original registry-bound material")


@pytest.fixture(scope="module")
def tokenizer() -> ChatTokenizer:
    if not all(path.exists() for path in (SOURCE, R16_TASK, R17_TASK, TOKENIZER)):
        pytest.skip("pinned source, paid observations or tokenizer unavailable")
    try:
        return canary._tokenizer(TOKENIZER)
    except (ImportError, canary.CanaryRefusal):
        pytest.skip("pinned tokenizer runtime unavailable")


def test_r17_paid_failure_is_immutable_input(tmp_path: Path) -> None:
    if not R17_TASK.is_file():
        pytest.skip("R17 paid diagnostic unavailable")
    observed = require_r17_observation(R17_TASK)
    assert observed["r17_task_sha256"] == R17_TASK_SHA256
    assert observed["observed_membership"] == {"a_sidecar_m": 300, "b_sidecar_m": 0}
    assert observed["observed_effective_cpu_m"] == 1200
    altered = tmp_path / "task.json"
    altered.write_bytes(R17_TASK.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="differs from reviewed bytes"):
        require_r17_observation(altered)


def test_exact_source_projection_changes_only_rule_material(tmp_path: Path) -> None:
    if not SOURCE.is_dir():
        pytest.skip("pinned KEP source unavailable")
    rule, spans = projected_rule(SOURCE)
    assert [(item["first_line"], item["last_line"]) for item in spans] == [
        (780, 794),
    ]
    assert "sidecar containers with index < i" in rule
    assert "Max ( Max( each InitContainerUse )" in rule
    assert "Defining `InitContainerUse` as:" not in rule
    amendment = amendment_text(SOURCE)
    rendered = prompts(amendment, rule)
    assert rendered["explicit-membership"].replace(rule, "formula=prefix") == rendered[
        "coarse-membership"
    ]
    assert rendered["explicit-numeric"].replace(rule, "formula=prefix") == rendered[
        "coarse-numeric"
    ]
    assert all(amendment in prompt for prompt in rendered.values())
    assert all("a_sidecar_m=0" not in prompt for prompt in rendered.values())
    assert all("effective_cpu_m=800" not in prompt for prompt in rendered.values())
    forged = tmp_path / "keps/sig-node/753-sidecar-containers/README.md"
    forged.parent.mkdir(parents=True)
    original = SOURCE / "keps/sig-node/753-sidecar-containers/README.md"
    forged.write_bytes(original.read_bytes() + b" ")
    with pytest.raises(ValueError, match="differs from pinned bytes"):
        projected_rule(tmp_path)


def test_registration_short_geometry_and_bound_task_budget(tokenizer: ChatTokenizer) -> None:
    _require_historical_registry()
    actual = build_registration(
        SOURCE, R16_TASK, R17_TASK, profile=canary._profile(), tokenizer=tokenizer
    )
    frozen = json.loads(offline.REGISTRATION.read_text())
    assert actual == frozen
    assert actual["case_order"] == list(CASE_ORDER)
    assert actual["target_call_cap"] == 4
    assert actual["auxiliary_call_cap"] == 0
    assert actual["local_input_tokens"] == 1410
    assert actual["local_input_plus_requested_ceiling"] == 9602
    requests = cast(list[dict[str, object]], actual["requests"])
    assert [item["prompt_sha256"] for item in requests] == [
        "0f9591b95d56cfaa5b3557dda73ded67fbdc85f7c2cd4a90f5635adf19564e6d",
        "3e72557ecb758ab60e1171a3a2148194644a44177077413e4f21757fcadc2b39",
        "d8115e3126f400243f790f07f6dd8d1d780d744afa35d8c924a29219277db930",
        "caf2edcdfae5a99d2bd6a067a546b9a51a07248084a2532b2394e0f32cd1f1b4",
    ]
    geometry = [cast(dict[str, object], item["local_template_geometry"]) for item in requests]
    assert [item["rendered_input_tokens"] for item in geometry] == [300, 306, 399, 405]
    assert all(item["span_status"] == "unique_later_query" for item in geometry)


def test_fake_chain_is_synthetic_and_refuses_registration_drift(tokenizer: ChatTokenizer) -> None:
    _require_historical_registry()
    frozen = json.loads(offline.REGISTRATION.read_text())
    result = offline.run_offline(
        SOURCE,
        R16_TASK,
        R17_TASK,
        profile=canary._profile(),
        tokenizer=tokenizer,
        registration=frozen,
    )
    assert result["status"] == "completed-synthetic-calibration"
    assert result["provider_evidence"] is False
    assert result["target_calls"] == 4 and result["auxiliary_calls"] == 0
    attempts = cast(list[dict[str, object]], result["attempts"])
    cases = cast(list[dict[str, object]], result["cases"])
    assert [item["status"] for item in attempts] == ["ok"] * 4
    membership = [
        item["rule_membership_correct"] for item in cases if "rule_membership_correct" in item
    ]
    assert membership == [
        False,
        True,
    ]
    assert [item["arithmetic_correct"] for item in cases if "arithmetic_correct" in item] == [
        None,
        False,
        None,
        True,
    ]
    forged = dict(frozen)
    forged["local_input_tokens"] = 1411
    with pytest.raises(ValueError, match="registration drifted"):
        offline.run_offline(
            SOURCE,
            R16_TASK,
            R17_TASK,
            profile=canary._profile(),
            tokenizer=tokenizer,
            registration=forged,
        )


def test_historical_registry_drift_refuses_offline_registration(tokenizer: ChatTokenizer) -> None:
    if _historical_registry_matches():
        pytest.skip("historical registry still matches")
    with pytest.raises(ValueError, match="source registry differs from pinned"):
        build_registration(
            SOURCE, R16_TASK, R17_TASK, profile=canary._profile(), tokenizer=tokenizer
        )


def test_evaluator_interpretation_uses_hidden_numeric_oracle() -> None:
    assert interpret_reply(
        "explicit-membership", "a_sidecar_m=0\nb_sidecar_m=300"
    )["rule_membership_correct"] is True
    assert interpret_reply(
        "explicit-numeric", "effective_cpu_m=800\nplan=admit-at-1000m"
    )["legal_plan"] is True
    assert interpret_reply(
        "explicit-numeric", "effective_cpu_m=800\nplan=hold-at-1000m"
    )["threshold_consistent"] is False
