"""Behavioral admission checks for the versioned B/C development budget."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from qualify_r4_bc_budget import (
    CONTRACT,
    RESEARCHER_PROFILES,
    WORKER_PROFILES,
    _sha256,
    qualify_contract,
)

from rsicontext.experiment.api import APIProfile, load_api_profiles

ORIGINAL_ADMISSION_SHA = "a5bc9cb17802f74021babda70432f196e4cb41361888ddd04fb16da16a155ecb"


def _inputs() -> tuple[dict[str, Any], dict[str, Any], APIProfile, APIProfile]:
    contract: dict[str, Any] = json.loads(CONTRACT.read_text())
    contract["source_admission_sha256"] = "a" * 64
    contract["source_preflight_sha256"] = "b" * 64
    source: dict[str, Any] = {
        "status": "complete",
        "mode": "portable_projection_of_offline_admission",
        "original_admission_sha256": ORIGINAL_ADMISSION_SHA,
        "model_api_calls": 0,
        "preflight_sha256": "b" * 64,
        "run_identity_end": {"matches_start": True},
        "groups": {
            "B": {
                "baseline_scripted": {"worker_calls": 31},
                "synthetic_candidate": {"worker_calls": 35},
            },
            "C": {
                "baseline_scripted": {"worker_calls": 18},
                "synthetic_candidate": {"worker_calls": 20},
            },
        },
    }
    worker = load_api_profiles(WORKER_PROFILES).get("siflow-qwen3.6-27b-r4-dev-2048")
    researcher = load_api_profiles(RESEARCHER_PROFILES).get(
        "siflow-deepseek-v4.1-flash-r4-dev-8192"
    )
    return contract, source, worker, researcher


def _qualify(contract: dict[str, Any], source: dict[str, Any]) -> dict[str, object]:
    _, _, worker, researcher = _inputs()
    return qualify_contract(
        contract,
        source,
        source_sha256="a" * 64,
        worker_profile=worker,
        researcher_profile=researcher,
        worker_profile_sha256=_sha256(WORKER_PROFILES),
        researcher_profile_sha256=_sha256(RESEARCHER_PROFILES),
    )


def test_scripted_capacity_is_matched_and_not_live_authority() -> None:
    contract, source, worker, researcher = _inputs()
    result = qualify_contract(
        contract,
        source,
        source_sha256="a" * 64,
        worker_profile=worker,
        researcher_profile=researcher,
        worker_profile_sha256=_sha256(WORKER_PROFILES),
        researcher_profile_sha256=_sha256(RESEARCHER_PROFILES),
    )

    assert result["status"] == "scripted_capacity_admitted"
    assert result["worker_request_cap_per_full_dev_run"] == 40
    assert result["max_total_worker_requests_including_fixed_baselines"] == 240
    assert result["max_total_researcher_requests"] == 4
    assert result["groups"] == {
        "B": {
            "baseline_calls": 31,
            "candidate_calls": 35,
            "baseline_fits": True,
            "candidate_fits": True,
        },
        "C": {
            "baseline_calls": 18,
            "candidate_calls": 20,
            "baseline_fits": True,
            "candidate_fits": True,
        },
    }
    assert result["live_ready"] is False
    assert result["model_api_calls"] == 0
    assert result["provider_revision_observable"] is False


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("request_cap_per_full_dev_run", 39, "worker cap"),
        ("max_total_worker_requests_including_fixed_baselines", 80, "total worker cap"),
        ("max_output_tokens_per_request", 1024, "worker profile"),
    ],
)
def test_capacity_and_profile_drift_are_rejected(field: str, value: int, message: str) -> None:
    contract, source, _, _ = _inputs()
    contract["worker"][field] = value
    with pytest.raises(ValueError, match=message):
        _qualify(contract, source)


def test_source_usage_identity_and_call_drift_are_rejected() -> None:
    contract, source, _, _ = _inputs()
    source["groups"]["B"]["synthetic_candidate"]["worker_calls"] = 36
    with pytest.raises(ValueError, match="scripted full-run calls"):
        _qualify(contract, source)

    contract, source, _, _ = _inputs()
    source["model_api_calls"] = 1
    with pytest.raises(ValueError, match="zero-API"):
        _qualify(contract, source)

    contract, source, _, _ = _inputs()
    source["run_identity_end"]["matches_start"] = False
    with pytest.raises(ValueError, match="identity"):
        _qualify(contract, source)

    contract, source, _, _ = _inputs()
    contract["source_admission_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="source admission SHA256"):
        _qualify(contract, source)


def test_worker_profile_bytes_are_pinned() -> None:
    contract, source, worker, researcher = _inputs()
    with pytest.raises(ValueError, match="worker profile SHA256"):
        qualify_contract(
            contract,
            source,
            source_sha256="a" * 64,
            worker_profile=worker,
            researcher_profile=researcher,
            worker_profile_sha256="d" * 64,
            researcher_profile_sha256=_sha256(RESEARCHER_PROFILES),
        )


def test_researcher_profile_bytes_and_exact_request_cap_are_pinned() -> None:
    contract, source, worker, researcher = _inputs()
    with pytest.raises(ValueError, match="researcher profile SHA256"):
        qualify_contract(
            contract,
            source,
            source_sha256="a" * 64,
            worker_profile=worker,
            researcher_profile=researcher,
            worker_profile_sha256=_sha256(WORKER_PROFILES),
            researcher_profile_sha256="e" * 64,
        )
    contract["researcher"]["max_output_tokens_per_request"] = 16384
    with pytest.raises(ValueError, match="researcher profile and output"):
        _qualify(contract, source)


def test_live_enablement_and_extra_researcher_attempt_are_rejected() -> None:
    contract, source, _, _ = _inputs()
    contract["live_enabled"] = True
    with pytest.raises(ValueError, match="cannot select or enable live"):
        _qualify(contract, source)

    contract, source, _, _ = _inputs()
    contract["researcher"]["http_attempts_per_draw"] = 2
    with pytest.raises(ValueError, match="researcher opportunity"):
        _qualify(contract, source)


def test_source_call_count_boolean_is_rejected() -> None:
    contract, source, _, _ = _inputs()
    changed = copy.deepcopy(source)
    changed["groups"]["C"]["baseline_scripted"]["worker_calls"] = True
    with pytest.raises(ValueError, match="positive integers"):
        _qualify(contract, changed)
