"""Portable identity checks for the pinned R7 source intake."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parent.parent
SOURCES: dict[str, tuple[Path, str, frozenset[str], str]] = {
    "pep": (
        ROOT / "configs/r7_pep_source_manifest_v1.json",
        "python-pep-process",
        frozenset({"peps/pep-0001.rst", "peps/pep-0621.rst", "peps/pep-0639.rst"}),
        "RSICONTEXT_PEP_SOURCE_ROOT",
    ),
    "postgresql": (
        ROOT / "configs/r7_postgresql_source_manifest_v1.json",
        "postgresql-rel-17-0",
        frozenset(
            {
                "COPYRIGHT",
                "doc/src/sgml/logical-replication.sgml",
                "doc/src/sgml/ref/create_subscription.sgml",
            }
        ),
        "RSICONTEXT_POSTGRESQL_SOURCE_ROOT",
    ),
}


def _source_manifest(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("source_name", tuple(SOURCES))
def test_source_manifest_matches_registry_without_host_paths(source_name: str) -> None:
    manifest_path, registry_id, expected_files, _ = SOURCES[source_name]
    manifest = _source_manifest(manifest_path)
    registry = json.loads((ROOT / "configs/registry.json").read_text(encoding="utf-8"))
    entry = next(row for row in registry["entries"] if row["id"] == registry_id)
    assert manifest["schema_version"] == 1
    assert manifest["status"] == "source_acquired_task_unqualified"
    assert manifest["registry_id"] == registry_id
    assert manifest["source_revision"] == entry["revision"] == entry["checksum"]["value"]
    assert "/volume/" not in json.dumps(manifest)
    assert set(manifest["selected_files"]) == expected_files
    for relative, identity in manifest["selected_files"].items():
        path = Path(relative)
        assert not path.is_absolute() and ".." not in path.parts
        assert len(identity["git_blob"]) == 40
        assert len(identity["sha256"]) == 64
        for span in identity["spans"].values():
            assert 1 <= span["start_line"] <= span["end_line"]
            assert 0 <= span["start_byte"] < span["end_byte"] <= identity["size_bytes"]
            assert len(span["sha256"]) == 64


@pytest.mark.parametrize("source_name", tuple(SOURCES))
def test_pinned_checkout_matches_file_and_span_hashes(source_name: str) -> None:
    manifest_path, _, _, env_var = SOURCES[source_name]
    configured = os.environ.get(env_var)
    if not configured:
        pytest.skip(f"set {env_var} to the detached pinned source checkout")
    checkout = Path(configured)
    manifest = _source_manifest(manifest_path)
    head = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert head == manifest["source_revision"]
    status = subprocess.run(
        ["git", "-C", str(checkout), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert not status
    for relative, identity in manifest["selected_files"].items():
        content = (checkout / relative).read_bytes()
        assert len(content) == identity["size_bytes"]
        assert hashlib.sha256(content).hexdigest() == identity["sha256"]
        blob = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", f"HEAD:{relative}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert blob == identity["git_blob"]
        lines = content.splitlines(keepends=True)
        for span in identity["spans"].values():
            start = sum(len(line) for line in lines[: span["start_line"] - 1])
            excerpt = b"".join(lines[span["start_line"] - 1 : span["end_line"]])
            assert (start, start + len(excerpt)) == (span["start_byte"], span["end_byte"])
            assert hashlib.sha256(excerpt).hexdigest() == span["sha256"]
