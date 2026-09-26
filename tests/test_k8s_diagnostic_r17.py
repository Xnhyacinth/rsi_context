"""R17 KEP diagnostic contracts; all worker calls use a local fake transport."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import cast

import pytest

from rsicontext.analysis.chat_geometry import ChatTokenizer
from rsicontext.analysis.k8s_diagnostic_r17 import (
    CASE_ORDER,
    R16_LATER_PROMPT_SHA256,
    R16_TASK_SHA256,
    amendment_text,
    build_registration,
    interpret_reply,
    prompts,
    require_r16_observation,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import r15_exact_profile_canary as canary  # noqa: E402
import r17_kep_diagnostic_offline as runner  # noqa: E402

SOURCE = Path(
    os.environ.get(
        "RSICONTEXT_K8S_SOURCE_ROOT",
        "/volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753",
    )
)
TASK = Path(
    os.environ.get(
        "RSICONTEXT_R16_KEP_TASK",
        "/volume/pt-dev/qjiu/rsi_context_external/r16-paid-runs/kep-development-v1/task.json",
    )
)
TOKENIZER = Path(
    os.environ.get(
        "RSICONTEXT_QWEN_TOKENIZER_ROOT",
        "/volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b",
    )
)


@pytest.fixture(scope="module")
def tokenizer() -> ChatTokenizer:
    if not SOURCE.is_dir() or not TASK.is_file() or not TOKENIZER.is_dir():
        pytest.skip("pinned KEP source, R16 observation or tokenizer unavailable")
    try:
        return canary._tokenizer(TOKENIZER)
    except (ImportError, canary.CanaryRefusal):
        pytest.skip("pinned optional tokenizer runtime unavailable")


def test_r16_failure_is_immutable_condition_not_reinterpreted(tmp_path: Path) -> None:
    if not TASK.is_file():
        pytest.skip("R16 paid task artifact unavailable")
    observed = require_r16_observation(TASK)
    assert observed["r16_task_sha256"] == R16_TASK_SHA256
    assert observed["observed_formula"] == "formula=prefix"
    assert observed["observed_later_plan"] == "hold-at-1000m"
    altered = tmp_path / "task.json"
    altered.write_bytes(TASK.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="differs from the reviewed observation"):
        require_r16_observation(altered)


def test_registration_replays_exact_amendment_and_counts_every_target(
    tokenizer: ChatTokenizer,
) -> None:
    actual = build_registration(SOURCE, TASK, profile=canary._profile(), tokenizer=tokenizer)
    frozen = json.loads(runner.REGISTRATION.read_text())
    assert actual == frozen
    assert actual["call_order"] == list(CASE_ORDER)
    assert actual["target_call_cap"] == 4
    assert actual["auxiliary_call_cap"] == 0
    assert actual["local_input_tokens"] == 1206
    assert actual["local_input_plus_requested_ceiling"] == 9398
    registered = cast(list[dict[str, object]], actual["requests"])
    assert [item["prompt_sha256"] for item in registered] == [
        R16_LATER_PROMPT_SHA256,
        "4f87cc1be796bdf806d0d24d6a094dec87320cb1ff7a6955d5d1f53f0b2d822b",
        "3c5369fe49955123c07f619d4da0cb5d39806a2746eecb3bd0d4a79ffd24e637",
        "712e5cdb7c6335bf94f2d98fe8813fad8b24977a56ae12d513459c4abd578c95",
    ]
    rendered = prompts(amendment_text(SOURCE))
    assert all("effective_cpu_m=800" not in prompt for prompt in rendered.values())
    assert all("Choose admit-at-1000m only" in prompt for prompt in rendered.values())
    assert "Prior decision: hold-at-1000m" in rendered["numeric-with-prior"]
    assert "Prior decision:" not in rendered["numeric-without-prior"]
    assert "Prior decision:" not in rendered["rule-membership"]
    assert rendered["numeric-with-prior"].replace(
        "\nPrior decision: hold-at-1000m", ""
    ) == rendered["numeric-without-prior"]


def test_fake_chain_preserves_registration_and_reports_only_synthetic_usage(
    tokenizer: ChatTokenizer,
) -> None:
    profile = canary._profile()
    frozen = json.loads(runner.REGISTRATION.read_text())
    result = runner.run_offline(
        SOURCE, TASK, tokenizer=tokenizer, profile=profile, registration=frozen
    )
    assert result["status"] == "completed-synthetic-diagnostic"
    assert result["provider_evidence"] is False
    assert result["target_calls"] == 4
    assert result["auxiliary_calls"] == 0
    attempts = cast(list[dict[str, object]], result["attempts"])
    cases = cast(list[dict[str, object]], result["cases"])
    assert [item["status"] for item in attempts] == ["ok"] * 4
    assert cases[1]["rule_membership_correct"] is True
    assert [item["arithmetic_correct"] for item in cases] == [
        None,
        None,
        False,
        True,
    ]
    forged = dict(frozen)
    forged["local_input_tokens"] = 906
    with pytest.raises(ValueError, match="registration drifted"):
        runner.run_offline(
            SOURCE, TASK, tokenizer=tokenizer, profile=profile, registration=forged
        )


def test_diagnostic_interpretation_separates_arithmetic_threshold_and_plan() -> None:
    wrong_arithmetic = interpret_reply(
        "numeric-with-prior", "effective_cpu_m=1100\nplan=hold-at-1000m"
    )
    wrong_threshold = interpret_reply(
        "numeric-with-prior", "effective_cpu_m=800\nplan=hold-at-1000m"
    )
    correct = interpret_reply(
        "numeric-without-prior", "effective_cpu_m=800\nplan=admit-at-1000m"
    )
    assert wrong_arithmetic["arithmetic_correct"] is False
    assert wrong_arithmetic["threshold_consistent"] is True
    assert wrong_threshold["arithmetic_correct"] is True
    assert wrong_threshold["threshold_consistent"] is False
    assert correct["arithmetic_correct"] is True and correct["legal_plan"] is True
    assert interpret_reply("numeric-with-prior", "800m admit")["valid_format"] is False
    assert interpret_reply(
        "rule-membership", "a_sidecar_m=0\nb_sidecar_m=300"
    )["rule_membership_correct"] is True
    assert interpret_reply(
        "rule-membership", "a_sidecar_m=300\nb_sidecar_m=300"
    )["rule_membership_correct"] is False
