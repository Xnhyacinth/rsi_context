from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from rsicontext.experiment.offline_provenance import (
    producer_attestation,
    require_clean_producer,
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test User")
    (root / "producer.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "add", "producer.py")
    _git(root, "commit", "-q", "-m", "initial")
    return root


def test_producer_attestation_accepts_committed_bytes(tmp_path: Path) -> None:
    root = _repository(tmp_path)

    attestation = producer_attestation(root, (Path("producer.py"),))

    assert attestation["repository_root_matches"] is True
    assert attestation["producer_files_match_head"] is True
    require_clean_producer(attestation)


def test_producer_attestation_rejects_assume_unchanged_bytes(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    _git(root, "update-index", "--assume-unchanged", "producer.py")
    (root / "producer.py").write_text("VALUE = 2\n", encoding="utf-8")

    attestation = producer_attestation(root, (Path("producer.py"),))

    assert attestation["worktree_dirty"] is False
    assert attestation["producer_files_match_head"] is False
    with pytest.raises(RuntimeError, match="HEAD"):
        require_clean_producer(attestation)


def test_producer_attestation_rejects_ignored_untracked_producer(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    (root / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    _git(root, "add", ".gitignore")
    _git(root, "commit", "-q", "-m", "ignore generated file")
    (root / "ignored.py").write_text("VALUE = 3\n", encoding="utf-8")

    attestation = producer_attestation(root, (Path("ignored.py"),))

    assert attestation["worktree_dirty"] is False
    assert attestation["producer_files_match_head"] is False
    with pytest.raises(RuntimeError, match="HEAD"):
        require_clean_producer(attestation)
