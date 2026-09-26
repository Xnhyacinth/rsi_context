"""R16 KEP admission checks use local SSE only; no paid test transport."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import urllib.request
from pathlib import Path
from typing import cast

import pytest

from rsicontext.analysis.chat_geometry import ChatTokenizer
from rsicontext.analysis.k8s_fixed_reader_r16 import (
    case_materials,
    make_synthetic_transport,
    transplant_conservative_rule,
)
from rsicontext.eval.openai_compatible import Transport
from rsicontext.experiment.api import APIProfile
from rsicontext.lifecycle.material_k8s_r14 import build_k8s_resource_order_sessions

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

import r15_exact_profile_canary as canary  # noqa: E402
import r16_kep_paid_runner as runner  # noqa: E402

_SOURCE = Path(
    os.environ.get(
        "RSICONTEXT_K8S_SOURCE_ROOT",
        "/volume/pt-dev/qjiu/rsi_context_external/data/kubernetes-enhancements-kep753",
    )
)
_TOKENIZER = Path(
    os.environ.get(
        "RSICONTEXT_QWEN_TOKENIZER_ROOT",
        "/volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b",
    )
)
_SECRET = "do-not-persist-r16-kep-secret"


def _historical_registry_matches() -> bool:
    launch = json.loads(runner._LAUNCH_PATH.read_text())
    current = hashlib.sha256((_ROOT / "configs/registry.json").read_bytes()).hexdigest()
    expected = launch["bound_file_sha256"]["configs/registry.json"]
    return isinstance(expected, str) and expected == current


def _require_historical_registry() -> None:
    if not _historical_registry_matches():
        pytest.skip("R16 synthetic chain requires its original registry-bound launch")


@pytest.fixture(scope="module")
def tokenizer() -> ChatTokenizer:
    if not _SOURCE.is_dir() or not _TOKENIZER.is_dir():
        pytest.skip("pinned KEP source or tokenizer unavailable")
    try:
        return canary._tokenizer(_TOKENIZER)
    except (ImportError, canary.CanaryRefusal):
        pytest.skip("pinned optional tokenizer runtime unavailable")


def _fake(
    profile: APIProfile, tokenizer: ChatTokenizer, calls: list[str], *, fail_full: bool = False
) -> Transport:
    canary_fake = canary._fake_transport(profile, tokenizer)
    task_fake = make_synthetic_transport(tokenizer, profile)

    def route(request: urllib.request.Request, timeout: float) -> bytes:
        assert isinstance(request.data, bytes)
        assert _SECRET not in str(request.header_items())
        body = json.loads(request.data)
        prompt = body["messages"][1]["content"]
        calls.append("canary" if prompt == canary.PROMPT else "task")
        if prompt == canary.PROMPT:
            return canary_fake(request, timeout)
        raw = task_fake(request, timeout)
        if fail_full and len(calls) == 4:
            return raw.replace(b"plan=admit-at-1000m", b"plan=hold-at-1000m")
        return raw

    return route


def test_frozen_geometry_has_exact_budget_and_decisive_rule_spans(
    tokenizer: ChatTokenizer,
) -> None:
    actual = runner._build_geometry(_SOURCE, tokenizer)
    frozen = json.loads(runner._GEOMETRY_PATH.read_text())
    assert actual == frozen
    assert actual["task_call_cap"] == 15
    assert actual["task_local_worst_case_input_tokens"] == 66558
    assert actual["task_local_plus_requested_ceiling"] == 97278
    assert isinstance(actual["registered_requests"], list)
    assert len(actual["registered_requests"]) == 14
    source_rule = cast(list[dict[str, object]], actual["source_rule_geometry"])
    assert [item["case"] for item in source_rule] == [
        "full-source",
        "source-free",
        "identity-only",
        "both-order-rules-neutralized",
        "same-identity-conservative-rule",
    ]
    full = cast(list[dict[str, object]], source_rule[0]["blocks"])
    withheld = cast(list[dict[str, object]], source_rule[1]["blocks"])
    identity = cast(list[dict[str, object]], source_rule[2]["blocks"])
    removed = cast(list[dict[str, object]], source_rule[3]["blocks"])
    counterfactual = cast(list[dict[str, object]], source_rule[4]["blocks"])
    assert [item["final_chat_token_interval"] for item in full] == [
        [8897, 8954],
        [8954, 9057],
        [9437, 9585],
    ]
    assert all(
        item["status"] == "source-withheld" and item["final_chat_token_interval"] is None
        for item in withheld
    )
    assert all(
        item["status"] == "identity-only" and item["final_chat_token_interval"] is None
        for item in identity
    )
    assert [item["status"] for item in removed] == [
        "intact",
        "explicit-rule-removed",
        "explicit-rule-removed",
    ]
    assert [item["final_chat_token_interval"] for item in removed] == [
        [8897, 8954],
        [8954, 8965],
        [9345, 9357],
    ]
    assert [item["final_chat_token_interval"] for item in counterfactual] == [
        [8897, 8943],
        [8943, 9003],
        [9383, 9482],
    ]


def test_constructed_rule_flips_only_second_private_legal_plan() -> None:
    if not _SOURCE.is_dir():
        pytest.skip("pinned KEP source checkout unavailable")
    sessions = build_k8s_resource_order_sessions(_SOURCE)
    cases = dict(case_materials(sessions))
    full = cases["full-source"]
    source_free = cases["source-free"]
    identity = cases["identity-only"]
    counterfactual = cases["same-identity-conservative-rule"]
    assert full[0].stages[0].documents[0].title == sessions[0].stages[0].documents[0].title
    assert full[0].stages[0].documents[0].source_url == (
        sessions[0].stages[0].documents[0].source_url
    )
    assert "KEP" not in source_free[0].stages[0].documents[0].text
    assert "KEP" not in source_free[0].stages[1].documents[0].text
    assert "KEP" not in source_free[1].stages[1].documents[0].text
    assert "KEP-753" in identity[0].stages[0].documents[0].text
    assert "formula" not in identity[0].stages[0].documents[0].text
    assert source_free[0].stages[0].documents[0].text.endswith("[SOURCE WITHHELD]")
    assert identity[0].stages[0].documents[0].text.endswith("[SOURCE WITHHELD]")
    assert full[0].stages[1].documents == counterfactual[0].stages[1].documents
    assert full[1].stages[1].documents == counterfactual[1].stages[1].documents
    full_s1 = full[0].stages[2].commit_precondition
    full_s2 = full[1].stages[2].commit_precondition
    constructed_s1 = counterfactual[0].stages[2].commit_precondition
    constructed_s2 = counterfactual[1].stages[2].commit_precondition
    assert full_s1 is not None and full_s1["legal_plans"] == ["hold-at-1000m"]
    assert full_s2 is not None and full_s2["legal_plans"] == ["admit-at-1000m"]
    assert constructed_s1 is not None and constructed_s1["legal_plans"] == ["hold-at-1000m"]
    assert constructed_s2 is not None and constructed_s2["legal_plans"] == ["hold-at-1000m"]
    assert counterfactual[0].stages[0].documents[0].source_url.startswith("benchmark:constructed/")
    changed, ledger = transplant_conservative_rule(full[0].stages[0].documents[0].text)
    assert changed == counterfactual[0].stages[0].documents[0].text
    assert ledger["untouched_bytes_exact"] is True
    assert isinstance(ledger["spans"], list)
    assert len(ledger["spans"]) == 3
    assert "sidecar containers with index < i" not in changed
    assert "Constructed benchmark rule" not in changed
    assert "Under this constructed rule" not in changed


def test_synthetic_full_chain_is_private_and_counts_all_calls(
    tokenizer: ChatTokenizer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _require_historical_registry()
    monkeypatch.setenv("SIFLOW_API_KEY", _SECRET)
    monkeypatch.delenv("SIFLOW_BASE_URL", raising=False)
    monkeypatch.setattr(
        runner,
        "resolve_api_endpoint",
        lambda *_args, **_kwargs: pytest.fail("injected transport resolved real credential"),
    )
    calls: list[str] = []
    profile = canary._profile()
    run_dir = tmp_path / "full"
    result = runner.run_guarded(
        source_root=_SOURCE,
        tokenizer_path=_TOKENIZER,
        run_dir=run_dir,
        transport_override=_fake(profile, tokenizer, calls),
    )
    assert result["status"] == "completed-synthetic-screen"
    assert result["provider_block_valid"] is False
    assert result["qualified_parent"] is False
    assert result["task_provider_usage_total"] is None
    assert result["attempted_http_calls"] == len(calls) == 17
    assert result["task_http_calls"] == 15
    assert result["canary_http_calls"] == 2
    task = json.loads((run_dir / "task.json").read_text())
    assert task["status"] == "completed-offline-screen"
    assert [case["session_passed"] for case in task["cases"]] == [
        [True, True],
        [True, False],
        [True, False],
        [True, False],
        [True, True],
    ]
    assert stat.S_IMODE(run_dir.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in run_dir.iterdir())
    contents = "".join(path.read_text() for path in run_dir.iterdir())
    assert _SECRET not in contents
    assert "Authorization" not in contents


def test_failed_full_source_stops_before_controls_and_post_canary(
    tokenizer: ChatTokenizer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _require_historical_registry()
    monkeypatch.delenv("SIFLOW_BASE_URL", raising=False)
    calls: list[str] = []
    run_dir = tmp_path / "failed-full"
    result = runner.run_guarded(
        source_root=_SOURCE,
        tokenizer_path=_TOKENIZER,
        run_dir=run_dir,
        transport_override=_fake(canary._profile(), tokenizer, calls, fail_full=True),
    )
    assert result["status"] == "stopped-on-full-task-failure"
    assert calls == ["canary", "task", "task", "task"]
    assert result["task_http_calls"] == 3
    assert result["canary_http_calls"] == 1
    assert not (run_dir / "post_canary.json").exists()
    assert (run_dir / "final.json").exists()


def test_forged_launch_refuses_before_credential_or_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forged = tmp_path / "forged-launch.json"
    forged.write_text(runner._LAUNCH_PATH.read_text().replace("97278", "97300"))
    monkeypatch.setattr(runner, "_LAUNCH_PATH", forged)
    monkeypatch.setattr(
        runner,
        "resolve_api_endpoint",
        lambda *_args, **_kwargs: pytest.fail("credential must not be resolved"),
    )
    calls: list[str] = []

    def fake(_request: urllib.request.Request, _timeout: float) -> bytes:
        calls.append("called")
        return b""

    result = runner.run_guarded(
        source_root=_SOURCE,
        tokenizer_path=_TOKENIZER,
        run_dir=tmp_path / "forged-run",
        transport_override=fake,
    )
    assert result["status"] == "refused-or-interrupted"
    assert result["failure_type"] == "ValueError"
    assert calls == []
    assert (tmp_path / "forged-run/final.json").exists()


def test_current_registry_drift_refuses_before_credentials_or_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if _historical_registry_matches():
        pytest.skip("current registry still matches the historical R16 launch")
    with pytest.raises(ValueError, match=r"configs/registry\.json"):
        runner._read_launch()
    monkeypatch.setattr(
        runner,
        "resolve_api_endpoint",
        lambda *_args, **_kwargs: pytest.fail("registry drift looked up credentials"),
    )
    calls: list[str] = []

    def fake(_request: urllib.request.Request, _timeout: float) -> bytes:
        calls.append("called")
        return b""

    run_dir = tmp_path / "registry-drift"
    result = runner.run_guarded(
        source_root=_SOURCE,
        tokenizer_path=_TOKENIZER,
        run_dir=run_dir,
        transport_override=fake,
    )
    assert result["status"] == "refused-or-interrupted"
    assert result["failure_type"] == "ValueError"
    assert result.get("attempted_http_calls", 0) == 0
    assert calls == []
    assert not (run_dir / "pre_canary.json").exists()
    assert (run_dir / "final.json").exists()
