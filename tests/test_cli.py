from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

from rsicontext.cli import main


def test_cli_toy_campaign(tmp_path: Path, capsys: object) -> None:
    exit_code = main(["toy-campaign", "--output", str(tmp_path)])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert output["selected_round"] == 1


def test_cli_registry_plan_is_dry_run(capsys: object) -> None:
    exit_code = main(
        [
            "registry-plan",
            "qwen3.6-27b",
            "--registry",
            "configs/registry.json",
            "--destination",
            "/tmp/rsicontext-dry-run",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert output["dry_run"] is True
    assert output["artifacts"][0]["id"] == "qwen3.6-27b"


def test_module_entrypoint_propagates_main_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rsicontext.cli.main", lambda: 7)

    with pytest.raises(SystemExit) as raised:
        runpy.run_module("rsicontext", run_name="__main__")

    assert raised.value.code == 7
