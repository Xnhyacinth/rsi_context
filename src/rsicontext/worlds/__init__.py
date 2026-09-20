"""Independent task worlds for RSIBench-Context v2 (review step 4).

Implements the world layer over the research-v1 lifecycle family: one world
is one corpus entity and its whole retrieval base, yielding several project
instances that legitimately share the world's document base while differing
in aspect. Dev/holdout splits happen by world — never by instance — so no
corpus row feeds both sides. See ``constructor.py`` for the world model and
``manifest.py`` for the audit surface.
"""

from .constructor import (
    TaskWorld,
    WorldSpec,
    build_world,
    gold_sane,
    load_worlds,
)
from .manifest import (
    WorldManifest,
    WorldRecord,
    build_world_manifest,
    read_manifest,
    write_manifest,
)

__all__ = [
    "TaskWorld",
    "WorldManifest",
    "WorldRecord",
    "WorldSpec",
    "build_world",
    "build_world_manifest",
    "gold_sane",
    "load_worlds",
    "read_manifest",
    "write_manifest",
]
