from pathlib import Path

import pytest

from rsicontext.artifacts import (
    ArtifactError,
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    ArtifactStore,
)


def test_content_addressing_is_deterministic_and_includes_lineage(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    root = store.put_files(
        {"policy/select.py": "def select():\n    return []\n"},
        metadata={"researcher": "seed"},
    )
    replay = store.put_files(
        {"policy/select.py": "def select():\n    return []\n"},
        metadata={"researcher": "seed"},
    )
    child = store.put_files(
        {"policy/select.py": "def select():\n    return [1]\n"},
        parents=(root.artifact_id,),
        metadata={"researcher": "codex"},
    )

    assert replay.artifact_id == root.artifact_id
    assert child.artifact_id != root.artifact_id
    assert tuple(record.artifact_id for record in store.lineage(child.artifact_id)) == (
        root.artifact_id,
        child.artifact_id,
    )
    assert store.read_files(child.artifact_id)["policy/select.py"].endswith(b"[1]\n")
    assert not list((tmp_path / "artifacts").rglob(".artifact-*"))


def test_missing_parent_and_unsafe_bundle_paths_are_rejected(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    with pytest.raises(ArtifactNotFoundError, match="parent"):
        store.put_text("candidate", kind="policy", parents=("0" * 64,))
    for unsafe in ("../escape.py", "/absolute.py", "policy/../escape.py", ""):
        with pytest.raises(ArtifactError, match="path"):
            store.put_files({unsafe: "pass\n"})


def test_read_detects_content_tampering(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    record = store.put_text("immutable", kind="trace")
    content_path = (
        tmp_path
        / "artifacts"
        / "objects"
        / "sha256"
        / record.artifact_id[:2]
        / record.artifact_id
        / "content"
    )
    content_path.write_bytes(b"tampered")

    with pytest.raises(ArtifactIntegrityError, match="integrity"):
        store.read_bytes(record.artifact_id)


def test_same_content_with_different_metadata_has_distinct_address(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    first = store.put_text("same", kind="policy", metadata={"round": "1"})
    second = store.put_text("same", kind="policy", metadata={"round": "2"})
    assert first.content_sha256 == second.content_sha256
    assert first.artifact_id != second.artifact_id
    with pytest.raises(TypeError):
        first.metadata["round"] = "changed"  # type: ignore[index]
