"""The v1 budget loader (spec Part 1.5) — one source of truth.

Hardcoded limits scattered across scripts were the 8013d6f review's
finding; this module loads ``configs/budget_v1.json`` once and exposes
it. Constants that stay in code (e.g. the variance ceiling) remain
co-located with their consumers, but every NUMERIC resource limit the
arms share lives here.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_BUDGET_FILE = _REPO_ROOT / "configs" / "budget_v1.json"


@lru_cache(maxsize=1)
def budget_v1() -> dict:
    """The frozen v1 budget pack (parsed JSON; cached per process)."""

    with _BUDGET_FILE.open(encoding="utf-8") as handle:
        return json.load(handle)


def worker_reader_limits() -> dict:
    return dict(budget_v1()["worker_reader"])


def researcher_limits() -> dict:
    return dict(budget_v1()["researcher"])


def tool_overheads() -> dict:
    return dict(budget_v1()["tools"])


def state_limits() -> dict:
    return dict(budget_v1()["state"])


def policy_modules() -> tuple[str, ...]:
    return tuple(budget_v1()["policy"]["allowed_modules"])
