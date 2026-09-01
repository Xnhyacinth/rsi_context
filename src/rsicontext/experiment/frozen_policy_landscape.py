"""Frozen multi-policy landscape with interleaved reader calls. Qualification only."""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from rsicontext.eval import EvaluationItem, ReaderOutput
from rsicontext.eval.core import FrozenReader, PolicyFactory, Scorer
from rsicontext.policy import Budget, ContextPack

Schedule = tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class FrozenArmSummary:
    policy_name: str
    score: float
    gold_recall: float
    reader_calls: int
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "gold_recall": self.gold_recall,
            "policy_name": self.policy_name,
            "reader_calls": self.reader_calls,
            "reader_input_tokens": self.reader_input_tokens,
            "reader_output_tokens": self.reader_output_tokens,
            "score": self.score,
            "wall_seconds": self.wall_seconds,
        }


@dataclass(frozen=True, slots=True)
class FrozenLandscapeResult:
    item_count: int
    schedule_sha256: str
    reader_calls: int
    arms: tuple[FrozenArmSummary, ...]
    qualification_only: bool = True
    rsi_launch_eligible: bool = False
    official_helmet_score: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "arms": [arm.to_dict() for arm in self.arms],
            "item_count": self.item_count,
            "official_helmet_score": self.official_helmet_score,
            "qualification_only": self.qualification_only,
            "reader_calls": self.reader_calls,
            "rsi_launch_eligible": self.rsi_launch_eligible,
            "schedule_sha256": self.schedule_sha256,
        }


def build_interleaved_schedule(
    item_ids: tuple[str, ...],
    policy_names: tuple[str, ...],
    *,
    seed: int,
) -> Schedule:
    """Shuffle policy order independently for each item from a frozen seed."""

    if not item_ids:
        raise ValueError("item_ids must be non-empty")
    if not policy_names:
        raise ValueError("policy_names must be non-empty")
    if len(policy_names) != len(set(policy_names)):
        raise ValueError("policy_names must be unique")
    if any(not name for name in policy_names):
        raise ValueError("policy names must be non-empty")
    rng = random.Random(seed)
    schedule: list[tuple[str, str]] = []
    for item_id in item_ids:
        names = list(policy_names)
        rng.shuffle(names)
        schedule.extend((item_id, name) for name in names)
    return tuple(schedule)


def schedule_sha256(schedule: Schedule) -> str:
    payload = json.dumps([list(pair) for pair in schedule], separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def gold_recall(pack: ContextPack, item: EvaluationItem) -> float:
    """Fraction of gold chunk ids present in the packed spans."""

    if not item.gold_chunk_ids:
        return 0.0
    packed = {span.chunk_id for span in pack.spans}
    return len(item.gold_chunk_ids & packed) / len(item.gold_chunk_ids)


def run_frozen_policy_landscape(
    *,
    items: tuple[EvaluationItem, ...],
    factories: Mapping[str, PolicyFactory],
    reader: FrozenReader,
    scorer: Scorer,
    budget: Budget,
    schedule: Schedule,
    timer: Callable[[], float] = time.perf_counter,
) -> FrozenLandscapeResult:
    """Score each (item, policy) pair once. Missing calls never become zeros."""

    if not items:
        raise ValueError("items must be non-empty")
    item_by_id = {item.item_id: item for item in items}
    if len(item_by_id) != len(items):
        raise ValueError("item ids must be unique")
    expected = {(item.item_id, name) for item in items for name in factories}
    observed = set(schedule)
    if observed != expected:
        raise ValueError("schedule must contain each item-policy pair exactly once")
    if len(schedule) != len(expected):
        raise ValueError("schedule must not repeat item-policy pairs")

    totals: dict[str, list[float]] = {name: [] for name in factories}
    recalls: dict[str, list[float]] = {name: [] for name in factories}
    input_tokens = {name: 0 for name in factories}
    output_tokens = {name: 0 for name in factories}
    walls = {name: 0.0 for name in factories}
    calls = 0
    for item_id, policy_name in schedule:
        item = item_by_id[item_id]
        started = timer()
        pack = factories[policy_name]().assemble(item.artifact, item.query, budget)
        pack.validate(item.artifact, budget)
        if pack.abstain or pack.request_reread is not None:
            raise ValueError("frozen landscape requires exactly one target-model call")
        output = reader.read(item.query, pack)
        if not isinstance(output, ReaderOutput):
            raise TypeError("reader must return ReaderOutput")
        score = scorer(output.answer, item.answer)
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
        ):
            raise TypeError("scorer must return a finite number")
        elapsed = timer() - started
        totals[policy_name].append(float(score))
        recalls[policy_name].append(gold_recall(pack, item))
        input_tokens[policy_name] += output.input_tokens
        output_tokens[policy_name] += output.output_tokens
        walls[policy_name] += elapsed
        calls += 1
    if calls != len(schedule):
        raise RuntimeError("frozen landscape ended with an incomplete schedule")
    arms = tuple(
        FrozenArmSummary(
            policy_name=name,
            score=sum(totals[name]) / len(totals[name]),
            gold_recall=sum(recalls[name]) / len(recalls[name]),
            reader_calls=len(totals[name]),
            reader_input_tokens=input_tokens[name],
            reader_output_tokens=output_tokens[name],
            wall_seconds=walls[name],
        )
        for name in factories
    )
    return FrozenLandscapeResult(
        item_count=len(items),
        schedule_sha256=schedule_sha256(schedule),
        reader_calls=calls,
        arms=arms,
    )
