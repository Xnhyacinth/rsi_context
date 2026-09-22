"""Research-v3 world "zephyr": the first Option-2 independent-material world.

DELEGATES to ``lifecycle/material_v3_segment.py`` (the shared Option-2
builder) — the world's definition lives in that module's ``WORLD_DEFS``
under the "zephyr" key; the frozen task card is
``docs/task-card-research-v3-zephyr.md``. This module keeps the
historical import surface (``build_research_v3_zephyr``,
``_CANDIDATES``) for the existing tests and callers.
"""

from __future__ import annotations

from rsicontext.lifecycle.material_v3_segment import (
    WORLD_DEFS,
    build_option2_world,
)
from rsicontext.lifecycle.spec import LifecycleInstance

_CANDIDATES = WORLD_DEFS["zephyr"]["candidates"]


def build_research_v3_zephyr(
    *, instance_id: str = "research-v3-zephyr-0001"
) -> LifecycleInstance:
    """Build the zephyr world (real-document segment material)."""

    return build_option2_world("zephyr", instance_id=instance_id)


__all__ = [
    "build_research_v3_zephyr",
]
