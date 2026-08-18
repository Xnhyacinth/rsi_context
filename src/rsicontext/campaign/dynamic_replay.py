"""Replay one frozen policy snapshot on the visible dynamic qualification panel."""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from rsicontext.campaign.autonomous_dynamic import (
    DynamicFreshEvaluator,
    DynamicReaderIdentity,
)
from rsicontext.datasets import DYNAMIC_CONTEXT_TOKENS, generate_dynamic_long_context_dataset
from rsicontext.eval import AuditedPolicyBundle, FrozenReader
from rsicontext.policy import Budget


@dataclass(frozen=True, slots=True)
class DynamicReplayObservation:
    repeat_index: int
    score: float
    item_scores: tuple[tuple[str, float], ...]
    predictions: tuple[tuple[str, str], ...]
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float

    def to_dict(self) -> dict[str, object]:
        return {
            "item_scores": dict(self.item_scores),
            "predictions": dict(self.predictions),
            "reader_input_tokens": self.reader_input_tokens,
            "reader_output_tokens": self.reader_output_tokens,
            "repeat_index": self.repeat_index,
            "score": self.score,
            "wall_seconds": self.wall_seconds,
        }


@dataclass(frozen=True, slots=True)
class DynamicCandidateReplayResult:
    schema_version: int
    candidate_sha256: str
    candidate_files: tuple[str, ...]
    entrypoint: str
    dataset_fingerprint: str
    split: str
    source_tokens: int
    policy_budget_tokens: int
    items_per_profile: int
    repeats: int
    reader_calls: int
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float
    observations: tuple[DynamicReplayObservation, ...]
    qualification_only: bool = True
    reader_identity: DynamicReaderIdentity | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_files": list(self.candidate_files),
            "candidate_sha256": self.candidate_sha256,
            "dataset_fingerprint": self.dataset_fingerprint,
            "entrypoint": self.entrypoint,
            "items_per_profile": self.items_per_profile,
            "observations": [observation.to_dict() for observation in self.observations],
            "policy_budget_tokens": self.policy_budget_tokens,
            "qualification_only": self.qualification_only,
            "reader_calls": self.reader_calls,
            "reader_input_tokens": self.reader_input_tokens,
            "reader_identity": (
                None if self.reader_identity is None else asdict(self.reader_identity)
            ),
            "reader_output_tokens": self.reader_output_tokens,
            "repeats": self.repeats,
            "schema_version": self.schema_version,
            "source_tokens": self.source_tokens,
            "split": self.split,
            "wall_seconds": self.wall_seconds,
        }


def run_dynamic_candidate_replay(
    *,
    candidate_policy_directory: str | Path,
    reader: FrozenReader,
    dataset_seed: str = "autonomous-dynamic-visible-v1",
    items_per_profile: int = 2,
    repeats: int = 5,
    budget: Budget | None = None,
    reader_identity: DynamicReaderIdentity | None = None,
    entrypoint: str = "policy.py",
) -> DynamicCandidateReplayResult:
    """Replay exact audited bytes; later source-directory mutations cannot enter the run."""

    if isinstance(repeats, bool) or not isinstance(repeats, int):
        raise TypeError("repeats must be an integer")
    if repeats < 1:
        raise ValueError("repeats must be positive")
    actual_budget = budget or Budget(8_192)
    bundle = AuditedPolicyBundle.from_directory(
        candidate_policy_directory,
        entrypoint=entrypoint,
    )
    candidate_sha256 = _bundle_sha256(bundle)
    dataset = generate_dynamic_long_context_dataset(
        seed=dataset_seed,
        items_per_profile=items_per_profile,
    )
    evaluator = DynamicFreshEvaluator(
        items=tuple(item.evaluation_item for item in dataset.visible_items()),
        reader=reader,
        budget=actual_budget,
        entrypoint=entrypoint,
    )
    with tempfile.TemporaryDirectory(prefix="rsicontext-replay-") as raw_snapshot:
        snapshot = Path(raw_snapshot)
        _materialize_bundle(bundle, snapshot)
        for repeat_index in range(repeats):
            evaluator.evaluate_directory(snapshot, round_index=repeat_index)
    observations = tuple(
        DynamicReplayObservation(
            repeat_index=observation.round_index,
            score=observation.score,
            item_scores=observation.item_scores,
            predictions=observation.predictions,
            reader_input_tokens=observation.reader_input_tokens,
            reader_output_tokens=observation.reader_output_tokens,
            wall_seconds=observation.wall_seconds,
        )
        for observation in evaluator.observations
    )
    return DynamicCandidateReplayResult(
        schema_version=2,
        candidate_sha256=candidate_sha256,
        candidate_files=tuple(path for path, _ in bundle.files),
        entrypoint=entrypoint,
        dataset_fingerprint=dataset.fingerprint,
        split="visible",
        source_tokens=DYNAMIC_CONTEXT_TOKENS,
        policy_budget_tokens=actual_budget.max_tokens,
        items_per_profile=items_per_profile,
        repeats=repeats,
        reader_calls=len(dataset.visible_items()) * repeats,
        reader_input_tokens=sum(observation.reader_input_tokens for observation in observations),
        reader_output_tokens=sum(observation.reader_output_tokens for observation in observations),
        wall_seconds=sum(observation.wall_seconds for observation in observations),
        observations=observations,
        reader_identity=reader_identity,
    )


def write_dynamic_candidate_replay(
    result: DynamicCandidateReplayResult,
    path: str | Path,
) -> None:
    """Persist one immutable replay record without replacing prior evidence."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result.to_dict(), handle, allow_nan=False, indent=2, sort_keys=True)
        handle.write("\n")


def _bundle_sha256(bundle: AuditedPolicyBundle) -> str:
    """Hash exact paths and bytes with length framing to avoid concatenation ambiguity."""

    digest = hashlib.sha256()
    digest.update(b"rsicontext-candidate-v1\x00")
    for relative, content in bundle.files:
        path_bytes = relative.encode("utf-8")
        digest.update(len(path_bytes).to_bytes(8, "big"))
        digest.update(path_bytes)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _materialize_bundle(bundle: AuditedPolicyBundle, root: Path) -> None:
    for relative, content in bundle.files:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
