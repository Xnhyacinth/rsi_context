"""Portable source pins for independent R4 development candidates."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parent.parent
SOURCES = Path("/volume/pt-dev/qjiu/rsi_context_external/data")


def _manifest() -> dict[str, Any]:
    return cast(
        dict[str, Any], json.loads((ROOT / "configs/r4_parent_source_manifest_v1.json").read_text())
    )


def test_source_manifest_is_pinned_to_registry_and_contains_no_local_paths() -> None:
    manifest = _manifest()
    registry = json.loads((ROOT / "configs/registry.json").read_text())
    entries = {entry["id"]: entry for entry in registry["entries"]}
    assert manifest["schema_version"] == 1
    assert manifest["status"] == "development_candidates_only"
    assert {source["id"] for source in manifest["sources"]} == {
        "otel-semconv-v1.43.0",
        "kubernetes-enhancements-kep753",
    }
    assert "/volume/" not in json.dumps(manifest)
    for source in manifest["sources"]:
        registered = entries[source["id"]]
        assert source["url"] == registered["url"]
        assert source["revision"] == registered["revision"]
        assert source["revision"] == registered["checksum"]["value"]
        assert source["license"] == registered["license"] == "Apache-2.0"
        assert source["selected_files"]
        for relative, identity in source["selected_files"].items():
            assert not Path(relative).is_absolute()
            assert ".." not in Path(relative).parts
            assert len(identity["git_blob"]) == 40
            assert len(identity["sha256"]) == 64


@pytest.mark.parametrize("source_id", ["otel-semconv-v1.43.0", "kubernetes-enhancements-kep753"])
def test_checked_out_source_files_match_manifest_when_available(source_id: str) -> None:
    checkout = SOURCES / source_id
    if not checkout.exists():
        pytest.skip("external pinned source checkout unavailable")
    source = next(row for row in _manifest()["sources"] if row["id"] == source_id)
    head = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert head == source["revision"]
    for relative, identity in source["selected_files"].items():
        path = checkout / relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == identity["sha256"]
        blob = subprocess.run(
            ["git", "-C", str(checkout), "hash-object", relative],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert blob == identity["git_blob"]
