from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from rsicontext.registry import (
    build_download_plan,
    load_registry,
    load_serving_profiles,
    run_preflight,
)
from rsicontext.registry.schema import Checksum, RegistryEntry, RegistryError

ROOT = Path(__file__).parents[1]
REGISTRY_PATH = ROOT / "configs" / "registry.json"
PROFILES_PATH = ROOT / "configs" / "serving_profiles.json"


def test_loader_reports_unreadable_and_invalid_json(tmp_path: Path) -> None:
    with pytest.raises(RegistryError, match="cannot read"):
        load_registry(tmp_path / "missing.json")
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    with pytest.raises(RegistryError, match="invalid JSON"):
        load_registry(invalid)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("id", "../escape", "unsafe registry id"),
        ("url", "http://example.test/model", "must use HTTPS"),
        ("revision", "--option", "unsafe revision"),
        ("size_bytes", -1, "non-negative"),
        ("kind", "other", "unsupported entry kind"),
        ("integration", "other", "unsupported integration mode"),
        ("access", "other", "unsupported access type"),
    ],
)
def test_entry_schema_rejects_unsafe_values(field: str, value: object, message: str) -> None:
    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["entries"][0]
    raw[field] = value

    with pytest.raises(RegistryError, match=message):
        RegistryEntry.from_dict(raw)


def test_checksum_schema_rejects_inconsistent_values() -> None:
    with pytest.raises(RegistryError, match="checksum must be"):
        Checksum.from_dict(None)
    with pytest.raises(RegistryError, match="unsupported checksum"):
        Checksum.from_dict({"algorithm": "md5", "value": "x", "verified": False})
    with pytest.raises(RegistryError, match="null value"):
        Checksum.from_dict({"algorithm": "unavailable", "value": "x", "verified": False})


def test_entry_schema_requires_matching_verified_revision() -> None:
    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["entries"][0]
    raw["checksum"]["value"] = "0" * 40
    with pytest.raises(RegistryError, match="differ"):
        RegistryEntry.from_dict(raw)

    raw["revision"] = "main"
    raw["checksum"]["value"] = "main"
    with pytest.raises(RegistryError, match="commit SHA"):
        RegistryEntry.from_dict(raw)


def test_citation_plan_is_warning_only(tmp_path: Path) -> None:
    citation = RegistryEntry.from_dict(
        {
            "id": "paper-only",
            "name": "Paper only",
            "kind": "baseline",
            "integration": "cite-only",
            "source_type": "citation",
            "url": "https://example.test/paper",
            "revision": None,
            "license": "unknown",
            "size_bytes": None,
            "access": "manual",
            "checksum": {"algorithm": "unavailable", "value": None, "verified": False},
            "notes": "Citation fixture.",
        }
    )

    artifact = build_download_plan((citation,), tmp_path).artifacts[0]

    assert artifact.acquire_command is None
    assert any("Manual access" in warning for warning in artifact.warnings)
    assert any("No upstream checksum" in warning for warning in artifact.warnings)


def test_preflight_reports_unavailable_host_resources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def disk_failure(_: object) -> object:
        raise OSError("disk unavailable")

    monkeypatch.setattr("rsicontext.registry.preflight.shutil.disk_usage", disk_failure)
    monkeypatch.setattr("rsicontext.registry.preflight.shutil.which", lambda _: None)
    monkeypatch.setattr("rsicontext.registry.preflight.Path.home", lambda: tmp_path)
    monkeypatch.delenv("HF_TOKEN", raising=False)

    report = run_preflight(
        tmp_path, required_bytes=0, expected_gpus=1, hold_wrapper=tmp_path / "missing.sh"
    )

    statuses = {check.name: check.status for check in report.checks}
    assert statuses == {"disk": "fail", "gpu": "fail", "hf_auth": "warn", "gpu_hold": "fail"}


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("dtype", "float16", "must use BF16"),
        ("gpu_memory_utilization", 1.0, "between zero and one"),
        ("enable_chunked_prefill", "yes", "must be booleans"),
        ("seed", 1.5, "must be an integer"),
        ("reasoning_parser", 4, "string or null"),
    ],
)
def test_serving_profile_schema_rejects_invalid_values(
    field: str, value: object, message: str, tmp_path: Path
) -> None:
    registry = load_registry(REGISTRY_PATH)
    raw = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    raw["profiles"] = [copy.deepcopy(raw["profiles"][0])]
    raw["profiles"][0][field] = value
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(RegistryError, match=message):
        load_serving_profiles(path, registry)


def test_serving_profile_rejects_unknown_model_and_profile(tmp_path: Path) -> None:
    registry = load_registry(REGISTRY_PATH)
    raw = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    raw["profiles"] = [copy.deepcopy(raw["profiles"][0])]
    raw["profiles"][0]["model_id"] = "missing-model"
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(RegistryError, match="unknown model"):
        load_serving_profiles(path, registry)
    profiles = load_serving_profiles(PROFILES_PATH, registry)
    with pytest.raises(RegistryError, match="unknown serving profile"):
        profiles.get("missing-profile")
