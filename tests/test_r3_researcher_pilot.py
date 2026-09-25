"""Behavioral checks for the live pilot's metering and request cap."""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path
from typing import cast

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import r3_researcher_pilot as pilot
from r2a_compare import (
    READER_MODEL,
    RESEARCHER_MODEL,
    _live_responder_factory,
    _offline_responder,
    _provider_usage_totals,
    _reported_usage,
    _researcher_unassisted_round,
    _run_arm,
)
from r3_compare import _canonical_sha256
from r3_researcher_pilot import (
    WORKER_REQUEST_CAP_PER_DRAW,
    WorkerRequestCap,
    _audit_candidate,
    _classify,
    _identity_still_frozen,
    _persist_candidate,
    _researcher_readiness,
    _run_identity,
    _worker_summary,
)

from rsicontext.lifecycle.material_v4_dossier import build_research_v4_dossier
from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text


def test_missing_provider_usage_is_not_presented_as_real_tokens() -> None:
    missing = _reported_usage({"prompt_tokens": 10, "completion_tokens": 2})
    assert missing == {
        "prompt_tokens": 10,
        "completion_tokens": 2,
        "total_tokens": None,
        "usage_status": "missing",
    }
    assert _provider_usage_totals([missing], live=True) == {
        "usage_status": "incomplete",
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    }


def test_provider_usage_counts_all_calls_in_a_cell() -> None:
    calls = [
        _reported_usage({"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}),
        _reported_usage({"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}),
    ]
    assert _provider_usage_totals(calls, live=True) == {
        "usage_status": "reported",
        "prompt_tokens": 17,
        "completion_tokens": 5,
        "total_tokens": 22,
    }


def test_worker_cap_rejects_next_request_before_network_call() -> None:
    requests: list[str] = []

    def fake(prompt: str) -> str:
        requests.append(prompt)
        return "answer"

    fake.usage_state = lambda: []  # type: ignore[attr-defined]
    fake.channel_state = lambda: []  # type: ignore[attr-defined]
    capped = WorkerRequestCap(fake, limit=2)
    assert capped("first") == "answer"
    assert capped("second") == "answer"
    with pytest.raises(RuntimeError, match="request cap 2 reached"):
        capped("third")
    assert requests == ["first", "second"]
    next_draw = WorkerRequestCap(fake, limit=2)
    assert next_draw("next draw") == "answer"
    assert requests == ["first", "second", "next draw"]
    assert WORKER_REQUEST_CAP_PER_DRAW == 16


def test_classification_counts_truncation_and_actual_exercise() -> None:
    policy = "def on_turn(turn):\n    return None\n"
    ready_record = {
        "finish_reason": "stop",
        "model_echo": RESEARCHER_MODEL,
        "usage_status": "reported",
        "input_tokens": 2,
        "output_tokens": 3,
        "total_tokens": 5,
        "candidate_audit": {"safe": True},
        "candidate_loadable": True,
    }
    reported_call = {
        "outcome": "ok",
        "model_echo": READER_MODEL,
        "usage_status": "reported",
        "finish_reason": "stop",
        "prompt_tokens": 1,
        "completion_tokens": 1,
        "total_tokens": 2,
    }
    assert _classify(policy, "different", {"finish_reason": "length"}, None) == "truncated"
    assert _classify(policy, "different", {"finish_reason": None}, None) == "unverified_finish"
    assert (
        _classify("not python", "different", {**ready_record, "candidate_loadable": False}, None)
        == "invalid"
    )
    assert _classify(policy, policy, ready_record, None) == "loadable-unchanged"
    assert (
        _classify(
            policy,
            "different",
            ready_record,
            {"model_calls": 1, "provider_usage_calls": [reported_call], "policy_errors": []},
        )
        == "changed-and-exercised"
    )
    assert (
        _classify(
            policy,
            "different",
            ready_record,
            {
                "model_calls": 1,
                "provider_usage_calls": [reported_call],
                "policy_errors": ["failed"],
            },
        )
        == "runtime-failed"
    )
    assert (
        _classify(
            policy,
            "different",
            ready_record,
            {
                "model_calls": 1,
                "provider_usage_calls": [reported_call],
                "policy_errors": [],
                "model_transcript": [{"ok": False, "cause": "pilot worker request cap 32 reached"}],
            },
        )
        == "budget-exhausted"
    )
    assert (
        _classify(
            policy,
            "different",
            ready_record,
            {
                "model_calls": 1,
                "provider_usage_calls": [{"outcome": "request_error"}],
                "policy_errors": [],
            },
        )
        == "worker-call-failed"
    )
    for changed_field, expected in (
        ({"model_echo": "different-model"}, "worker-model-mismatch"),
        ({"usage_status": "missing"}, "worker-usage-unverified"),
        ({"total_tokens": None}, "worker-usage-unverified"),
        ({"finish_reason": "length"}, "worker-truncated"),
        ({"finish_reason": None}, "unverified_finish"),
    ):
        assert (
            _classify(
                policy,
                "different",
                ready_record,
                {
                    "model_calls": 1,
                    "provider_usage_calls": [{**reported_call, **changed_field}],
                    "policy_errors": [],
                },
            )
            == expected
        )


def test_researcher_verification_blocks_worker_spend() -> None:
    ready = {
        "finish_reason": "stop",
        "model_echo": RESEARCHER_MODEL,
        "usage_status": "reported",
        "input_tokens": 2,
        "output_tokens": 3,
        "total_tokens": 5,
        "candidate_audit": {"safe": True},
    }
    assert _researcher_readiness(ready) is None
    for changed_field, expected in (
        ({"finish_reason": None}, "unverified_finish"),
        ({"model_echo": "wrong-model"}, "researcher-model-mismatch"),
        ({"usage_status": "missing"}, "researcher-usage-unverified"),
        ({"total_tokens": None}, "researcher-usage-unverified"),
    ):
        record = {**ready, **changed_field}
        assert _researcher_readiness(record) == expected
        assert (
            _classify("def on_turn(turn):\n    return None\n", "different", record, None)
            == expected
        )


def test_worker_summary_uses_audit_hash_without_raw_prompt() -> None:
    run: dict[str, object] = {
        "instance_id": "dev",
        "passed": False,
        "decisions": {},
        "failures": [],
        "policy_errors": [],
        "model_calls": 1,
        "model_tokens_source": "word_estimate",
        "provider_usage_calls": [],
        "provider_usage_totals": {},
        "tool_ledger": {},
        "wall_seconds": 1.0,
        "model_transcript": [{"prompt_sha256": "abc", "stage_id": "s1", "prompt_head": "private"}],
    }
    summary = _worker_summary(run)
    assert summary is not None
    assert summary["worker_prompt_sha256"] == ["abc"]
    assert summary["worker_call_stage_ids"] == ["s1"]
    assert "private" not in str(summary)
    run["model_transcript"] = [{"stage_id": "s2"}]
    missing = _worker_summary(run)
    assert missing is not None
    assert missing["worker_prompt_sha256"] == ["missing"]


def test_worker_summary_accepts_real_model_transcript_schema() -> None:
    run = _run_arm(
        strong_model_fixed_policy_text(),
        build_research_v4_dossier(),
        _offline_responder,
    )
    summary = _worker_summary(run)
    assert summary is not None
    assert len(cast(list[object], summary["worker_prompt_sha256"])) == run["model_calls"]
    assert "prompt_head" not in str(summary)


def test_candidate_bytes_are_saved_in_python_only_directory(tmp_path: Path) -> None:
    output = tmp_path / "pilot-v3.json"
    output.with_suffix("").mkdir()
    policy = "def on_turn(turn):\n    return None\n"
    record = _persist_candidate(output, 0, policy)
    candidate = Path(str(record["policy_path"]))
    assert candidate.read_text(encoding="utf-8") == policy
    assert record["policy_sha256"] == hashlib.sha256(policy.encode()).hexdigest()
    assert list(candidate.parent.iterdir()) == [candidate]
    assert _audit_candidate(record["candidate_dir"], policy)["safe"] is True
    with pytest.raises(FileExistsError):
        _persist_candidate(output, 0, policy)


def test_second_draw_audit_is_independent_of_first_rejection(tmp_path: Path) -> None:
    output = tmp_path / "pilot-v4.json"
    output.with_suffix("").mkdir()
    unsafe_text = "def on_turn(turn):\n    turn.state.write('x')\n    return None\n"
    safe_text = "def on_turn(turn):\n    return None\n"
    unsafe = _persist_candidate(output, 0, unsafe_text)
    safe = _persist_candidate(output, 1, safe_text)
    assert _audit_candidate(unsafe["candidate_dir"], unsafe_text)["safe"] is False
    assert _audit_candidate(safe["candidate_dir"], safe_text)["safe"] is True
    for candidate in (unsafe, safe):
        directory = Path(str(candidate["candidate_dir"]))
        assert [path.name for path in directory.iterdir()] == ["policy.py"]


def test_candidate_audit_checks_memory_and_disk_bytes(tmp_path: Path) -> None:
    output = tmp_path / "pilot-v4.json"
    output.with_suffix("").mkdir()
    safe_text = "def on_turn(turn):\n    return None\n"
    malicious_text = (
        "import json\njson._rsi_audit_probe_marker = True\ndef on_turn(turn):\n    return None\n"
    )
    saved = _persist_candidate(output, 0, safe_text)
    audit = _audit_candidate(saved["candidate_dir"], malicious_text)
    assert audit["safe"] is False
    assert audit["hashes_match"] is False
    violations = cast(list[dict[str, object]], audit["violations"])
    assert {v["code"] for v in violations} == {"STATE_MUTABLE"}
    assert audit["memory_sha256"] != audit["disk_sha256"]
    swapped = Path(str(saved["policy_path"]))
    swapped.write_text(malicious_text, encoding="utf-8")
    audit = _audit_candidate(saved["candidate_dir"], safe_text)
    assert audit["safe"] is False
    assert audit["hashes_match"] is False
    violations = cast(list[dict[str, object]], audit["violations"])
    assert any(v["source"] == "tree" for v in violations)


def test_each_candidate_has_independent_audit_and_rejection_keeps_denominator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "dev.json"
    source.write_text(
        json.dumps(
            {
                "groups": {
                    "A": {
                        "arms": {
                            "baseline": {
                                "dev": {
                                    "instance_id": build_research_v4_dossier().instance_id,
                                    "decisions": {},
                                    "failures": [],
                                    "passed": False,
                                }
                            }
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pilot, "DEV_SOURCE", source)
    # This test exercises the static audit path with fake provider responses;
    # the live entry itself remains closed until an isolated executor exists.
    monkeypatch.setattr(pilot, "require_isolated_policy_executor", lambda: None)
    monkeypatch.setattr(pilot, "_available_models", lambda: {READER_MODEL, RESEARCHER_MODEL})

    class FakeResponder:
        def usage_state(self) -> list[dict[str, object]]:
            return []

    monkeypatch.setattr(pilot, "_live_responder_factory", lambda **kwargs: FakeResponder())
    monkeypatch.setattr(pilot, "_identity_still_frozen", lambda identity: True)
    monkeypatch.setattr(json, "_rsi_audit_probe_marker", False, raising=False)
    unsafe = (
        "import json\njson._rsi_audit_probe_marker = True\ndef on_turn(turn):\n    return None\n"
    )
    record = {
        "finish_reason": "stop",
        "model_echo": RESEARCHER_MODEL,
        "usage_status": "reported",
        "input_tokens": 1,
        "output_tokens": 2,
        "total_tokens": 3,
    }
    monkeypatch.setattr(
        pilot, "_researcher_unassisted_round", lambda *args, **kwargs: (unsafe, dict(record))
    )

    def fail_worker(*args: object, **kwargs: object) -> None:
        raise AssertionError("audit-rejected candidate reached worker")

    monkeypatch.setattr(pilot, "_run_arm", fail_worker)
    result = pilot.run(tmp_path / "v4.json")
    draws = cast(list[dict[str, object]], result["draws"])
    assert result["valid_update_rate"] == {"numerator": 0, "denominator": 2}
    assert [draw["outcome"] for draw in draws] == ["audit-rejected"] * 2
    assert result["worker_requests_attempted"] == 0
    assert json._rsi_audit_probe_marker is False  # type: ignore[attr-defined]
    assert all(cast(dict[str, object], draw["candidate_audit"])["violations"] for draw in draws)
    assert all(Path(str(draw["candidate_dir"])).joinpath("policy.py").is_file() for draw in draws)


def test_run_identity_hashes_full_dev_world_and_detects_source_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _run_identity(strong_model_fixed_policy_text(), {"failures": []})
    materials = cast(dict[str, object], identity["materials"])
    assert materials["a_dev_full_sha256"] == _canonical_sha256(
        build_research_v4_dossier().to_dict()
    )
    assert "answer_norm" not in str(identity)
    monkeypatch.setattr("r3_researcher_pilot._git_identity", lambda: identity["git"])
    monkeypatch.setattr("r3_researcher_pilot._source_sha256", lambda: identity["source_sha256"])
    assert _identity_still_frozen(identity)
    monkeypatch.setattr("r3_researcher_pilot._source_sha256", lambda: "changed")
    assert not _identity_still_frozen(identity)


def test_non_thinking_flags_are_opt_in_and_usage_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Fake HTTP exercises request encoding only; real live entry remains closed.
    monkeypatch.setattr("r2a_compare.require_isolated_policy_executor", lambda: None)
    bodies: list[dict[str, object]] = []

    def fake_urlopen(request: object, timeout: int) -> io.BytesIO:
        assert timeout in (300, 600)
        body = json.loads(request.data)  # type: ignore[attr-defined]
        bodies.append(body)
        response = {
            "model": body["model"],
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": "```python\ndef on_turn(turn):\n    return None\n```"},
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
        }
        return io.BytesIO(json.dumps(response).encode())

    monkeypatch.setenv("SIFLOW_API_KEY", "test-only")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    default = _live_responder_factory()
    default("hello")
    direct = _live_responder_factory(enable_thinking=False)
    direct("hello")
    assert "chat_template_kwargs" not in bodies[0]
    assert bodies[1]["chat_template_kwargs"] == {"enable_thinking": False}
    assert direct.usage_state()[0]["total_tokens"] == 8
    policy, record = _researcher_unassisted_round(
        "def on_turn(turn):\n    return None\n",
        {},
        live=True,
        max_output_tokens=12288,
        max_attempts=1,
        thinking=False,
    )
    assert "def on_turn" in policy
    assert bodies[2]["thinking"] == {"type": "disabled"}
    assert bodies[2]["max_tokens"] == 12288
    assert record["total_tokens"] == 8


def test_malformed_response_preserves_provider_usage_as_protocol_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("r2a_compare.require_isolated_policy_executor", lambda: None)

    def fake_urlopen(request: object, timeout: int) -> io.BytesIO:
        del request, timeout
        return io.BytesIO(
            json.dumps(
                {
                    "model": READER_MODEL,
                    "choices": [{"finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
                }
            ).encode()
        )

    monkeypatch.setenv("SIFLOW_API_KEY", "test-only")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    responder = _live_responder_factory()
    with pytest.raises(KeyError, match="message"):
        responder("hello")
    assert responder.usage_state()[0] == {
        "model": READER_MODEL,
        "model_echo": READER_MODEL,
        "system_fingerprint": None,
        "outcome": "protocol_error",
        "finish_reason": None,
        "error_type": "KeyError",
        "prompt_tokens": 3,
        "completion_tokens": 5,
        "total_tokens": 8,
        "usage_status": "reported",
    }
    policy, record = _researcher_unassisted_round(
        "def on_turn(turn):\n    return None\n", {}, True, max_attempts=1
    )
    assert policy == ""
    assert record["round_outcome"] == "failed: protocol_error"
    assert record["total_tokens"] == 8
