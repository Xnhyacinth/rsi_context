from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "hy3_popqa_frozen_landscape.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("hy3_popqa_frozen_landscape_script", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen landscape script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_landscape_script_records_missing_credentials(
    monkeypatch, tmp_path: Path
) -> None:
    script = _load_script()
    output = tmp_path / "landscape.json"
    monkeypatch.delenv("COPILOT_API_KEY", raising=False)
    monkeypatch.delenv("COPILOT_BASE_URL", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        ["hy3_popqa_frozen_landscape.py", "--output", str(output)],
    )
    assert script.main() == 0
    payload = output.read_text(encoding="utf-8")
    assert "credentials_missing" in payload
    assert "rsi_launch_eligible" in payload
