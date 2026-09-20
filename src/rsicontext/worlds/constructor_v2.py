"""Research-v2 worlds: the leak-closed family on the worlds discipline.

Spec: ``docs/dependency-probes-20260920.md`` §Consequences — the revised
family builds on the worlds constructor (independence by world, layered
randomization) with ``lifecycle/material_v2.py`` instances (stage-5 carries
no documents and an instruction that never names the answer; answer-bearing
evidence appears only in stage 1; stage 4 carries a verification check that
discriminates candidates without containing them).

Reuses the v1 worlds package's types (``TaskWorld``, ``WorldSpec``) and its
loader discipline (dedup by row id AND entity, world-level dev/holdout
splits, per-world seeded shuffle) but constructs v2 instances through
``build_research_v2_instance`` and gates rows through ``gold_sane_v2``
(the subject-mention conjunction).
"""

from __future__ import annotations

import json
import random
from collections.abc import Mapping
from pathlib import Path

from rsicontext.lifecycle.material_v2 import (
    build_research_v2_instance,
    gold_sane_v2,
)
from rsicontext.worlds.constructor import (
    _ASPECTS,
    _MAX_DOCS_PER_VARIANT,
    _MAX_INSTANCES_PER_WORLD,
    _MIN_INSTANCES_PER_WORLD,
    _MIN_NOISE_DOCS,
    TaskWorld,
    WorldSpec,
    _ctx_body,
    _ctx_has_answer,
    _optional_entity_key,
    _optional_row_id,
    _require_int,
    _require_str,
)

_FAMILY_TEMPLATE_ID = "research-v2"


def build_world_v2(row: Mapping[str, object], world_id: str) -> TaskWorld:
    """Build one research-v2 world (2-4 leak-closed instances) from a row.

    Same slicing discipline as the v1 constructor: disjoint per-variant
    noise slices (round-robin over retrieval order), gold passages shared
    by every variant's stage-1 survey. The instances themselves are
    research-v2 (see ``lifecycle/material_v2.py``): no stage after 1
    shows answer-bearing text, and stage 5 shows nothing.
    """

    _require_str(world_id, "world_id")
    row_id = _optional_row_id(row)
    if row_id is None:
        raise ValueError("world construction requires a row id")
    raw_ctxs = row.get("ctxs")
    if not isinstance(raw_ctxs, list) or not raw_ctxs:
        raise ValueError("ctxs must be a non-empty list")
    ctxs: list[Mapping[str, object]] = [ctx for ctx in raw_ctxs if isinstance(ctx, Mapping)]
    gold_positions = [
        position for position, ctx in enumerate(ctxs) if _ctx_has_answer(ctx) and _ctx_body(ctx)
    ]
    noise_positions = [
        position for position, ctx in enumerate(ctxs) if not _ctx_has_answer(ctx) and _ctx_body(ctx)
    ]
    if not gold_positions:
        raise ValueError("world construction requires at least one usable gold ctx")
    if len(noise_positions) < _MIN_NOISE_DOCS:
        raise ValueError(
            f"world construction requires at least {_MIN_NOISE_DOCS} usable non-gold ctxs"
        )
    n_variants = min(
        _MAX_INSTANCES_PER_WORLD,
        max(_MIN_INSTANCES_PER_WORLD, len(noise_positions) // 2),
    )
    slice_positions_per_variant = [
        noise_positions[variant::n_variants][:_MAX_DOCS_PER_VARIANT]
        for variant in range(n_variants)
    ]
    instances = []
    variant_notes: list[str] = []
    for variant in range(n_variants):
        aspect_label, _frame = _ASPECTS[variant]
        slice_positions = slice_positions_per_variant[variant]
        instances.append(
            build_research_v2_instance(
                row,
                world_id=world_id,
                variant_label=aspect_label,
                noise_positions=list(slice_positions),
            )
        )
        variant_notes.append(
            f"{aspect_label}: {len(slice_positions)}-doc noise slice; "
            "answer-bearing gold visible only at stage 1"
        )
    return TaskWorld(
        spec=WorldSpec(
            world_id=world_id,
            template_id=_FAMILY_TEMPLATE_ID,
            entity_seed=(row_id,),
            variant_notes=tuple(variant_notes),
        ),
        instances=tuple(instances),
    )


def load_worlds_v2(
    popqa_path: str | Path, n_worlds: int, *, dev_worlds: int, seed: int = 0
) -> tuple[list[TaskWorld], list[TaskWorld]]:
    """Load research-v2 worlds with the v1 loader discipline, v2 gates.

    Streams the PopQA KILT JSONL; keeps the first occurrence of each
    distinct row id, at most one world per entity (``subj_id``), and only
    rows passing ``gold_sane_v2`` (answer alias AND subject mention in a
    gold passage — the conjunction that rejects wrong-entity retrieval).
    Splits dev/holdout by world after a seeded shuffle.
    """

    _require_int(n_worlds, "n_worlds", minimum=2)
    _require_int(dev_worlds, "dev_worlds", minimum=1)
    if dev_worlds >= n_worlds:
        raise ValueError("dev_worlds must leave at least one holdout world")
    _require_int(seed, "seed", minimum=0)
    worlds: list[TaskWorld] = []
    seen_row_ids: set[str] = set()
    seen_entities: set[str] = set()
    with Path(popqa_path).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row: object = json.loads(line)
            if not isinstance(row, Mapping):
                raise ValueError("corpus lines must be JSON objects")
            row_id = _optional_row_id(row)
            if row_id is None or row_id in seen_row_ids:
                continue
            seen_row_ids.add(row_id)
            entity_key = _optional_entity_key(row)
            if entity_key is not None and entity_key in seen_entities:
                continue
            if not gold_sane_v2(row):
                continue
            try:
                world = build_world_v2(row, f"world-{row_id}")
            except ValueError:
                continue
            if entity_key is not None:
                seen_entities.add(entity_key)
            worlds.append(world)
            if len(worlds) == n_worlds:
                break
    if len(worlds) < n_worlds:
        raise ValueError(f"corpus yielded {len(worlds)} gold-sane-v2 worlds; {n_worlds} requested")
    order = list(range(len(worlds)))
    random.Random(seed).shuffle(order)
    shuffled = [worlds[index] for index in order]
    return shuffled[:dev_worlds], shuffled[dev_worlds:]


__all__ = [
    "build_world_v2",
    "load_worlds_v2",
]
