"""Load registry manifests without importing optional dependencies."""

from __future__ import annotations

import json
from pathlib import Path

from rsicontext.registry.schema import Registry, RegistryError


def load_registry(path: str | Path) -> Registry:
    """Load and validate a JSON registry manifest."""
    manifest_path = Path(path)
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise RegistryError(f"cannot read registry {manifest_path}: {error}") from error
    except json.JSONDecodeError as error:
        raise RegistryError(f"invalid JSON in registry {manifest_path}: {error}") from error
    return Registry.from_dict(raw)
