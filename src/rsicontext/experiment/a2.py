"""Pre-registered A2 factorial and nominal successful-call projection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

_MATCHED_CONTROLS = ("random-5", "sequential-search-5")
_STATIC_POLICIES = (
    "h0",
    "head-tail",
    "lexical",
    "hand-hybrid",
)
_DIAGNOSTIC_INSTRUMENTS = (
    "bounded-oracle",
    "full-context-unbudgeted-upper-bound",
    "gold-only",
    "no-context",
)
_PRIMARY_ESTIMAND = "gate_score_of_visible_selected_researcher_minus_visible_selected_control"


def _nonempty_pair(values: tuple[str, ...], field: str) -> tuple[str, str]:
    if len(values) != 2:
        raise ValueError(f"A2 requires exactly two {field}")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise TypeError(f"{field} must be non-empty strings")
    if len(set(values)) != len(values):
        raise ValueError(f"{field} must be unique")
    return values[0], values[1]


def _seed_pair(values: tuple[int, ...]) -> tuple[int, int]:
    if len(values) != 2:
        raise ValueError("A2 requires exactly two seeds")
    if any(not isinstance(value, int) or isinstance(value, bool) for value in values):
        raise TypeError("seeds must be integers")
    if any(value < 0 for value in values):
        raise ValueError("seeds must be non-negative")
    if len(set(values)) != len(values):
        raise ValueError("seeds must be unique")
    return values[0], values[1]


@dataclass(frozen=True, slots=True)
class A2Cell:
    researcher: str
    task_profile: str
    research_seed: int
    rounds: int
    cell_id: str


@dataclass(frozen=True, slots=True)
class A2TargetCallProjection:
    """Nominal successful calls; retries, failures, audits, and preflight are excluded."""

    researcher_visible: int
    researcher_gate: int
    matched_control_visible: int
    matched_control_gate: int
    reference_visible: int
    reference_gate: int
    replay: int

    @property
    def total_nominal(self) -> int:
        return sum(asdict(self).values())


@dataclass(frozen=True, slots=True)
class A2PilotPlan:
    cells: tuple[A2Cell, ...]
    researchers: tuple[str, str]
    task_profiles: tuple[str, str]
    research_seeds: tuple[int, int]
    rounds: int
    items_per_split: int
    replay_repetitions: int
    matched_controls: tuple[str, ...]
    static_policies: tuple[str, ...]
    diagnostic_instruments: tuple[str, ...]
    qualification_only: bool = True

    @property
    def researcher_turns(self) -> int:
        return len(self.cells) * self.rounds

    @property
    def prediction_triples(self) -> int:
        return self.researcher_turns * self.items_per_split

    @property
    def primary_estimand(self) -> str:
        return _PRIMARY_ESTIMAND

    @property
    def selection_rule(self) -> str:
        return "visible_historical_best"

    @property
    def target_call_projection(self) -> A2TargetCallProjection:
        profile_seed_cells = len(self.task_profiles) * len(self.research_seeds)
        researcher_candidates = len(self.cells) * (1 + self.rounds)
        control_candidates = profile_seed_cells * len(self.matched_controls) * self.rounds
        references = profile_seed_cells * (
            len(self.static_policies) + len(self.diagnostic_instruments)
        )
        replay_calls = (
            (len(self.cells) * 2 + profile_seed_cells)
            * self.replay_repetitions
            * self.items_per_split
        )
        return A2TargetCallProjection(
            researcher_visible=researcher_candidates * self.items_per_split,
            researcher_gate=len(self.cells) * self.items_per_split,
            matched_control_visible=control_candidates * self.items_per_split,
            matched_control_gate=(
                profile_seed_cells * len(self.matched_controls) * self.items_per_split
            ),
            reference_visible=references * self.items_per_split,
            reference_gate=references * self.items_per_split,
            replay=replay_calls,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "qualification_only": self.qualification_only,
            "primary_estimand": self.primary_estimand,
            "cells": [asdict(cell) for cell in self.cells],
            "researchers": list(self.researchers),
            "task_profiles": list(self.task_profiles),
            "research_seeds": list(self.research_seeds),
            "rounds": self.rounds,
            "items_per_split": self.items_per_split,
            "replay_repetitions": self.replay_repetitions,
            "matched_controls": list(self.matched_controls),
            "static_policies": list(self.static_policies),
            "diagnostic_instruments": list(self.diagnostic_instruments),
            "selection_rule": self.selection_rule,
            "gate_evaluations_per_arm": 1,
            "researcher_turns": self.researcher_turns,
            "prediction_triples": self.prediction_triples,
            "target_call_projection": {
                **asdict(self.target_call_projection),
                "total_nominal": self.target_call_projection.total_nominal,
            },
        }

    @property
    def plan_sha256(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


def build_a2_pilot_plan(
    *,
    researchers: tuple[str, ...],
    task_profiles: tuple[str, ...],
    seeds: tuple[int, ...],
    rounds: int = 5,
    items_per_split: int = 40,
    replay_repetitions: int = 5,
) -> A2PilotPlan:
    """Build the fixed 2x2x2x5 A2 screen before any scored execution."""
    researcher_pair = _nonempty_pair(researchers, "researchers")
    profile_pair = _nonempty_pair(task_profiles, "task profiles")
    seed_values = _seed_pair(seeds)
    if not isinstance(rounds, int) or isinstance(rounds, bool):
        raise TypeError("rounds must be an integer")
    if rounds != 5:
        raise ValueError("the pre-registered A2 pilot requires exactly five rounds")
    for field, value in (
        ("items_per_split", items_per_split),
        ("replay_repetitions", replay_repetitions),
    ):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{field} must be an integer")
        if value <= 0:
            raise ValueError(f"{field} must be positive")

    cells = tuple(
        A2Cell(
            researcher=researcher,
            task_profile=profile,
            research_seed=seed,
            rounds=rounds,
            cell_id=hashlib.sha256(
                f"a2\x00{researcher}\x00{profile}\x00{seed}\x00{rounds}".encode()
            ).hexdigest()[:20],
        )
        for researcher in researcher_pair
        for profile in profile_pair
        for seed in seed_values
    )
    return A2PilotPlan(
        cells=cells,
        researchers=researcher_pair,
        task_profiles=profile_pair,
        research_seeds=seed_values,
        rounds=rounds,
        items_per_split=items_per_split,
        replay_repetitions=replay_repetitions,
        matched_controls=_MATCHED_CONTROLS,
        static_policies=_STATIC_POLICIES,
        diagnostic_instruments=_DIAGNOSTIC_INSTRUMENTS,
    )
