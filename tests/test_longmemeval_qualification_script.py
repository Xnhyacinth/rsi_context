from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "longmemeval_offline_qualification.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "longmemeval_qualification_script_test", SCRIPT_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load LongMemEval qualification script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT = _load_script()


def test_released_checksums_select_the_requested_haystack() -> None:
    small = dict(SCRIPT._released_checksums("small"))
    medium = dict(SCRIPT._released_checksums("medium"))

    assert "haystacks/lme_v2_small.json" in small
    assert "haystacks/lme_v2_medium.json" not in small
    assert "haystacks/lme_v2_medium.json" in medium
    assert small["questions.jsonl"] == medium["questions.jsonl"]


def test_cli_refuses_to_overwrite_an_existing_qualification(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "existing.json"
    output.write_text("immutable\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["longmemeval_offline_qualification.py", "--output", str(output)],
    )

    with pytest.raises(FileExistsError, match="already exists"):
        SCRIPT.main()

    assert output.read_text(encoding="utf-8") == "immutable\n"
