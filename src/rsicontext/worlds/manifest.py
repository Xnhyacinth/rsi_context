"""World manifest — the review step-4 audit surface.

The review's deliverable quote: "clearly list the number of independent
worlds, the number of templates/structures, the number of sub-tasks per
world, the number of repetitions, and which data has already been used for
development." ``WorldManifest`` records exactly that, plus the per-world
provenance (template, entity seed, variant notes, instance ids) and the
discipline invariants that make the record trustworthy:

- dev and holdout world sets are disjoint and partition all worlds (splits
  are by world, never by instance);
- no corpus row id feeds two worlds (world independence at the source);
- instance ids are globally unique;
- every world's ``used_for_development`` flag agrees with the split;
- each world carries 2-4 instances with one variant note per instance.

Round-trips through sorted-key JSON (``write_manifest`` / ``read_manifest``).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from rsicontext.worlds.constructor import TaskWorld

_MIN_INSTANCES_PER_WORLD = 2
_MAX_INSTANCES_PER_WORLD = 4


def _require_str(value: object, field: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if not value:
        raise ValueError(f"{field} must not be empty")


def _require_bool(value: object, field: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{field} must be a boolean")


def _require_str_tuple(value: object, field: str) -> tuple[str, ...]:
    """Validate a JSON list or Python tuple of non-empty strings."""

    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{field} must be a list")
    entries: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            raise TypeError(f"{field} entries must be strings")
        if not entry:
            raise ValueError(f"{field} entries must not be empty")
        entries.append(entry)
    if not entries:
        raise ValueError(f"{field} must not be empty")
    return tuple(entries)


@dataclass(frozen=True, slots=True)
class WorldRecord:
    """Per-world manifest entry — what the world is and where it came from."""

    world_id: str
    template_id: str
    entity_seed: tuple[str, ...]
    variant_notes: tuple[str, ...]
    instance_ids: tuple[str, ...]
    used_for_development: bool

    def __post_init__(self) -> None:
        _require_str(self.world_id, "world_id")
        _require_str(self.template_id, "template_id")
        object.__setattr__(self, "entity_seed", _require_str_tuple(self.entity_seed, "entity_seed"))
        object.__setattr__(
            self, "variant_notes", _require_str_tuple(self.variant_notes, "variant_notes")
        )
        object.__setattr__(
            self, "instance_ids", _require_str_tuple(self.instance_ids, "instance_ids")
        )
        _require_bool(self.used_for_development, "used_for_development")
        if len(self.variant_notes) != len(self.instance_ids):
            raise ValueError("variant_notes must carry one note per instance")

    def to_dict(self) -> dict[str, object]:
        return {
            "world_id": self.world_id,
            "template_id": self.template_id,
            "entity_seed": list(self.entity_seed),
            "variant_notes": list(self.variant_notes),
            "instance_ids": list(self.instance_ids),
            "used_for_development": self.used_for_development,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> WorldRecord:
        if not isinstance(raw, Mapping):
            raise TypeError("world record must be a mapping")
        _require_fields(
            raw,
            {
                "entity_seed",
                "instance_ids",
                "template_id",
                "used_for_development",
                "variant_notes",
                "world_id",
            },
            field="world record",
        )
        used = raw["used_for_development"]
        if not isinstance(used, bool):
            raise TypeError("used_for_development must be a boolean")
        return cls(
            world_id=_load_str(raw, "world_id"),
            template_id=_load_str(raw, "template_id"),
            entity_seed=_require_str_tuple(raw["entity_seed"], "entity_seed"),
            variant_notes=_require_str_tuple(raw["variant_notes"], "variant_notes"),
            instance_ids=_require_str_tuple(raw["instance_ids"], "instance_ids"),
            used_for_development=used,
        )


@dataclass(frozen=True, slots=True)
class WorldManifest:
    """The review's deliverable record for one world-structured panel.

    ``worlds_total`` independent worlds; ``templates_used`` distinct family
    templates; ``instances_per_world`` sub-task count per world (aligned
    with ``worlds``); ``repetitions`` how many times each instance is
    replayed; ``dev_world_ids`` / ``holdout_world_ids`` the by-world split;
    ``data_sources`` the corpus path followed by every row id used; and
    ``worlds`` the per-world records with a ``used_for_development`` flag
    each.
    """

    worlds_total: int
    templates_used: int
    instances_per_world: tuple[int, ...]
    repetitions: int
    dev_world_ids: frozenset[str]
    holdout_world_ids: frozenset[str]
    data_sources: tuple[str, ...]
    worlds: tuple[WorldRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.worlds_total, int) or isinstance(self.worlds_total, bool):
            raise TypeError("worlds_total must be an integer")
        if not isinstance(self.templates_used, int) or isinstance(self.templates_used, bool):
            raise TypeError("templates_used must be an integer")
        if not isinstance(self.repetitions, int) or isinstance(self.repetitions, bool):
            raise TypeError("repetitions must be an integer")
        object.__setattr__(self, "instances_per_world", tuple(self.instances_per_world))
        object.__setattr__(self, "dev_world_ids", frozenset(self.dev_world_ids))
        object.__setattr__(self, "holdout_world_ids", frozenset(self.holdout_world_ids))
        object.__setattr__(self, "data_sources", tuple(self.data_sources))
        object.__setattr__(self, "worlds", tuple(self.worlds))
        records = self.worlds
        if any(not isinstance(record, WorldRecord) for record in records):
            raise TypeError("worlds must be WorldRecord values")
        if self.worlds_total != len(records) or self.worlds_total < 2:
            raise ValueError("worlds_total must match the number of world records (>= 2)")
        world_ids = [record.world_id for record in records]
        if len(world_ids) != len(set(world_ids)):
            raise ValueError("world ids must be unique")
        dev = self.dev_world_ids
        holdout = self.holdout_world_ids
        if not dev or not holdout:
            raise ValueError("both dev and holdout world sets must be non-empty")
        if dev & holdout:
            raise ValueError("dev and holdout world sets must be disjoint")
        if dev | holdout != frozenset(world_ids):
            raise ValueError("dev and holdout world sets must partition all worlds")
        for world_id in (*dev, *holdout):
            _require_str(world_id, "world id entry")
        for record in records:
            if record.used_for_development != (record.world_id in dev):
                raise ValueError(
                    f"used_for_development must agree with the split for world {record.world_id!r}"
                )
        templates = {record.template_id for record in records}
        if self.templates_used != len(templates) or self.templates_used < 1:
            raise ValueError("templates_used must equal the distinct template count (>= 1)")
        if len(self.instances_per_world) != len(records):
            raise ValueError("instances_per_world must carry one entry per world")
        for count, record in zip(self.instances_per_world, records, strict=True):
            if not isinstance(count, int) or isinstance(count, bool):
                raise TypeError("instances_per_world entries must be integers")
            if count != len(record.instance_ids):
                raise ValueError("instances_per_world entries must match each world's instances")
            if not _MIN_INSTANCES_PER_WORLD <= count <= _MAX_INSTANCES_PER_WORLD:
                raise ValueError(
                    f"a world carries {_MIN_INSTANCES_PER_WORLD}-{_MAX_INSTANCES_PER_WORLD} "
                    f"instances; got {count}"
                )
        if self.repetitions < 1:
            raise ValueError("repetitions must be at least 1")
        if len(self.data_sources) < 2:
            raise ValueError("data_sources must carry the corpus path plus at least one row id")
        for entry in self.data_sources:
            _require_str(entry, "data_sources entry")
        row_ids = self.data_sources[1:]
        if len(row_ids) != len(set(row_ids)):
            raise ValueError("data_sources row ids must be unique")
        seeded = [row_id for record in records for row_id in record.entity_seed]
        if len(seeded) != len(set(seeded)):
            raise ValueError("a corpus row id may not feed two worlds")
        if set(row_ids) != frozenset(seeded):
            raise ValueError("data_sources row ids must match the worlds' entity seeds")
        instance_ids = [instance_id for record in records for instance_id in record.instance_ids]
        if len(instance_ids) != len(set(instance_ids)):
            raise ValueError("instance ids must be globally unique across worlds")

    def to_dict(self) -> dict[str, object]:
        return {
            "worlds_total": self.worlds_total,
            "templates_used": self.templates_used,
            "instances_per_world": list(self.instances_per_world),
            "repetitions": self.repetitions,
            "dev_world_ids": sorted(self.dev_world_ids),
            "holdout_world_ids": sorted(self.holdout_world_ids),
            "data_sources": list(self.data_sources),
            "worlds": [record.to_dict() for record in self.worlds],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> WorldManifest:
        if not isinstance(raw, Mapping):
            raise TypeError("manifest payload must be a mapping")
        _require_fields(
            raw,
            {
                "data_sources",
                "dev_world_ids",
                "holdout_world_ids",
                "instances_per_world",
                "repetitions",
                "templates_used",
                "worlds",
                "worlds_total",
            },
            field="world manifest",
        )
        worlds_raw = raw["worlds"]
        if not isinstance(worlds_raw, list):
            raise TypeError("worlds must be a list")
        worlds = tuple(
            WorldRecord.from_dict(entry) if isinstance(entry, Mapping) else _reject_entry(entry)
            for entry in worlds_raw
        )
        return cls(
            worlds_total=_load_int(raw, "worlds_total"),
            templates_used=_load_int(raw, "templates_used"),
            instances_per_world=_load_int_tuple(raw["instances_per_world"], "instances_per_world"),
            repetitions=_load_int(raw, "repetitions"),
            dev_world_ids=frozenset(_require_str_tuple(raw["dev_world_ids"], "dev_world_ids")),
            holdout_world_ids=frozenset(
                _require_str_tuple(raw["holdout_world_ids"], "holdout_world_ids")
            ),
            data_sources=_require_str_tuple(raw["data_sources"], "data_sources"),
            worlds=worlds,
        )


def build_world_manifest(
    dev_worlds: Sequence[TaskWorld],
    holdout_worlds: Sequence[TaskWorld],
    *,
    corpus_path: str,
    repetitions: int,
) -> WorldManifest:
    """Assemble the manifest from a world-level dev/holdout split.

    ``corpus_path`` is the PopQA KILT file the worlds were loaded from and
    ``repetitions`` how many times each instance is replayed per run. World
    records are ordered dev-first; world ids must be unique across both
    sides and every world must carry 2-4 instances (enforced by
    ``TaskWorld``; re-validated here at the manifest level).
    """

    _require_str(corpus_path, "corpus_path")
    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions < 1:
        raise ValueError("repetitions must be an integer >= 1")
    dev = tuple(dev_worlds)
    holdout = tuple(holdout_worlds)
    if not dev or not holdout:
        raise ValueError("both dev and holdout world lists must be non-empty")
    if any(not isinstance(world, TaskWorld) for world in (*dev, *holdout)):
        raise TypeError("dev/holdout entries must be TaskWorld values")
    worlds = (*dev, *holdout)
    world_ids = [world.world_id for world in worlds]
    if len(world_ids) != len(set(world_ids)):
        raise ValueError("world ids must be unique across dev and holdout")
    records = tuple(
        WorldRecord(
            world_id=world.world_id,
            template_id=world.spec.template_id,
            entity_seed=world.spec.entity_seed,
            variant_notes=world.spec.variant_notes,
            instance_ids=tuple(instance.instance_id for instance in world.instances),
            used_for_development=index < len(dev),
        )
        for index, world in enumerate(worlds)
    )
    row_ids = sorted({row_id for world in worlds for row_id in world.spec.entity_seed})
    return WorldManifest(
        worlds_total=len(worlds),
        templates_used=len({world.spec.template_id for world in worlds}),
        instances_per_world=tuple(len(world.instances) for world in worlds),
        repetitions=repetitions,
        dev_world_ids=frozenset(world.world_id for world in dev),
        holdout_world_ids=frozenset(world.world_id for world in holdout),
        data_sources=(corpus_path, *row_ids),
        worlds=records,
    )


def write_manifest(path: str | Path, manifest: WorldManifest) -> None:
    """Write the canonical sorted-key JSON form (trailing newline)."""

    payload = (
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)


def read_manifest(path: str | Path) -> WorldManifest:
    """Read a manifest, rejecting non-object roots and malformed fields."""

    raw: object = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("manifest root must be a JSON object")
    return WorldManifest.from_dict(raw)


def _reject_entry(entry: object) -> WorldRecord:
    raise TypeError(f"each world record must be a mapping; got {type(entry).__name__}")


def _require_fields(raw: Mapping[str, object], expected: set[str], *, field: str) -> None:
    actual = set(raw)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{field} fields mismatch; missing={missing}, extra={extra}")


def _load_str(raw: Mapping[str, object], key: str) -> str:
    value = raw[key]
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    if not value:
        raise ValueError(f"{key} must not be empty")
    return value


def _load_int(raw: Mapping[str, object], key: str) -> int:
    value = raw[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{key} must be an integer")
    return value


def _load_int_tuple(value: object, field: str) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise TypeError(f"{field} must be a list")
    entries: list[int] = []
    for entry in value:
        if not isinstance(entry, int) or isinstance(entry, bool):
            raise TypeError(f"{field} entries must be integers")
        entries.append(entry)
    if not entries:
        raise ValueError(f"{field} must not be empty")
    return tuple(entries)
