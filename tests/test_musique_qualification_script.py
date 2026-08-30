from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "musique_offline_qualification.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("musique_qualification_script_test", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load MuSiQue qualification script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT = _load_script()


def test_producer_attestation_requires_clean_and_stable_state() -> None:
    clean = {
        "git_revision": "a" * 40,
        "worktree_dirty": False,
        "repository_root_matches": True,
        "producer_files_match_head": True,
    }

    SCRIPT._require_clean_producer(clean)
    SCRIPT._require_stable_attestation(clean, dict(clean))

    with pytest.raises(RuntimeError, match="clean producer worktree"):
        SCRIPT._require_clean_producer({**clean, "worktree_dirty": True})
    with pytest.raises(RuntimeError, match="changed during execution"):
        SCRIPT._require_stable_attestation(clean, {**clean, "git_revision": "b" * 40})


def test_source_attestation_rejects_execution_time_drift(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    source.write_bytes(b"before")
    expected = hashlib.sha256(b"before").hexdigest()

    SCRIPT._require_unchanged_source(source, expected)
    source.write_bytes(b"after")

    with pytest.raises(RuntimeError, match="source changed during execution"):
        SCRIPT._require_unchanged_source(source, expected)


def test_cli_rejects_an_existing_output_before_computation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "existing.json"
    output.write_text("immutable\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["musique_offline_qualification.py", "--output", str(output)])

    with pytest.raises(FileExistsError, match="already exists"):
        SCRIPT.main()

    assert output.read_text(encoding="utf-8") == "immutable\n"
