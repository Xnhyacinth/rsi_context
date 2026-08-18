"""Deterministic end-to-end campaign used to qualify the benchmark harness."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from rsicontext.analysis import ReplaySummary as ProcessReplaySummary
from rsicontext.analysis import TrajectoryMetrics, replay_summary, trajectory_metrics
from rsicontext.artifacts import (
    ArtifactStore,
    CostEstimate,
    EvidenceClaim,
    FlipProbabilities,
    Manifest,
    MechanismClaim,
    PromotionRecommendation,
    QuestionPrediction,
    write_manifest_atomic,
)
from rsicontext.eval import EvaluationItem, ToyFrozenReader, evaluate, replay
from rsicontext.policy import (
    Artifact,
    Budget,
    ContextPolicy,
    DocumentChunk,
    LexicalPolicy,
    TruncationPolicy,
)


@dataclass(frozen=True, slots=True)
class ToyRound:
    round_index: int
    policy_name: str
    artifact_id: str
    score: float
    promoted: bool
    reader_input_tokens: int
    reader_output_tokens: int


@dataclass(frozen=True, slots=True)
class ToyCampaignResult:
    """A known-shape trajectory: fail, discover, then regress."""

    rounds: tuple[ToyRound, ...]
    selected_round: int
    last_round: int
    metrics: TrajectoryMetrics
    replay: ProcessReplaySummary

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _chunk(document_id: str, index: int, text: str) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=f"{document_id}-c{index}",
        document_id=document_id,
        start=index * 100,
        end=index * 100 + len(text),
        text=text,
        token_count=len(text.split()),
    )


def _items() -> tuple[EvaluationItem, ...]:
    facts = (
        ("orion", "amber"),
        ("lyra", "violet"),
        ("cygnus", "silver"),
    )
    items: list[EvaluationItem] = []
    for name, answer in facts:
        chunks = (
            _chunk(name, 0, "Unrelated archival material with no marked answer."),
            _chunk(name, 1, f"The {name} access color is recorded here.\nANSWER: {answer}"),
            _chunk(name, 2, "Unrelated closing material with no marked answer."),
        )
        items.append(
            EvaluationItem(
                item_id=f"toy-{name}",
                query=f"What is the {name} access color?",
                answer=answer,
                artifact=Artifact(name, chunks),
                gold_chunk_ids=frozenset({chunks[1].chunk_id}),
            )
        )
    return tuple(items)


def _manifest(
    *,
    round_index: int,
    policy_name: str,
    parent_artifact_id: str | None,
    item_ids: tuple[str, ...],
    evaluation_input_tokens: int,
    evaluation_output_tokens: int,
) -> Manifest:
    probability_by_round = {
        0: FlipProbabilities(0.05, 0.90, 0.05),
        1: FlipProbabilities(0.90, 0.05, 0.05),
        2: FlipProbabilities(0.05, 0.05, 0.90),
    }
    decision_by_round: dict[int, Literal["promote", "hold", "reject"]] = {
        0: "hold",
        1: "promote",
        2: "reject",
    }
    delta_by_round = {0: 0.0, 1: 1.0, 2: -1.0}
    mechanism_id = f"toy-mechanism-{round_index}"
    evidence_id = f"toy-evidence-{round_index}"
    return Manifest(
        candidate_name=policy_name,
        parent_artifact_id=parent_artifact_id,
        predictions=tuple(
            QuestionPrediction(
                item_id=item_id,
                probabilities=probability_by_round[round_index],
                mechanism_ids=(mechanism_id,),
                evidence_ids=(evidence_id,),
            )
            for item_id in item_ids
        ),
        mechanisms=(
            MechanismClaim(
                mechanism_id=mechanism_id,
                description="Exercise deterministic evidence selection in the toy harness.",
                policy_paths=("policy/config.json",),
            ),
        ),
        evidence=(
            EvidenceClaim(
                evidence_id=evidence_id,
                kind="toy-visible-trace",
                reference=f"round-{round_index}",
                claim="The visible toy items identify whether the selected chunk contains gold.",
            ),
        ),
        cost=CostEstimate(
            researcher_input_tokens=0,
            researcher_output_tokens=0,
            evaluation_input_tokens=evaluation_input_tokens,
            evaluation_output_tokens=evaluation_output_tokens,
            gpu_seconds=0.0,
            wall_seconds=0.0,
        ),
        promotion=PromotionRecommendation(
            decision=decision_by_round[round_index],
            expected_score_delta=delta_by_round[round_index],
            max_regression_probability=probability_by_round[round_index].regress,
            rationale="Known toy recommendation used only to test the protocol.",
        ),
    )


def run_toy_campaign(output: str | Path) -> ToyCampaignResult:
    """Run a zero-model harness qualification campaign and persist its lineage."""

    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    store = ArtifactStore(output_path / "store")
    reader = ToyFrozenReader()
    budget = Budget(max_tokens=9, max_free_text_tokens=0, max_chunks=1)
    items = _items()
    candidates: tuple[tuple[str, Callable[[], ContextPolicy], dict[str, str]], ...] = (
        ("head-truncation", lambda: TruncationPolicy("head"), {"mode": "head"}),
        ("lexical", LexicalPolicy, {"mode": "lexical"}),
        ("tail-truncation", lambda: TruncationPolicy("tail"), {"mode": "tail"}),
    )

    rounds: list[ToyRound] = []
    parent_id: str | None = None
    selected_score = float("-inf")
    selected_round = 0
    for round_index, (policy_name, policy_factory, config) in enumerate(candidates):
        parents = () if parent_id is None else (parent_id,)
        record = store.put_files(
            {"policy/config.json": json.dumps(config, sort_keys=True) + "\n"},
            kind="policy",
            parents=parents,
            metadata={"policy_name": policy_name, "round": str(round_index)},
        )
        result = evaluate(policy_factory, items, reader, budget)
        promoted = result.score > selected_score
        if promoted:
            selected_score = result.score
            selected_round = round_index
        rounds.append(
            ToyRound(
                round_index=round_index,
                policy_name=policy_name,
                artifact_id=record.artifact_id,
                score=result.score,
                promoted=promoted,
                reader_input_tokens=sum(result.reader_input_tokens),
                reader_output_tokens=sum(result.reader_output_tokens),
            )
        )
        manifest = _manifest(
            round_index=round_index,
            policy_name=policy_name,
            parent_artifact_id=parent_id,
            item_ids=tuple(item.item_id for item in items),
            evaluation_input_tokens=sum(result.reader_input_tokens),
            evaluation_output_tokens=sum(result.reader_output_tokens),
        )
        manifest.validate_for_items(tuple(item.item_id for item in items))
        write_manifest_atomic(output_path / f"round-{round_index:02d}-manifest.json", manifest)
        parent_id = record.artifact_id

    selected_policy_factory = candidates[selected_round][1]
    fixed_replay = replay(selected_policy_factory, items, reader, budget, repeats=5)
    scores = tuple(round_.score for round_ in rounds)
    campaign = ToyCampaignResult(
        rounds=tuple(rounds),
        selected_round=selected_round,
        last_round=len(rounds) - 1,
        metrics=trajectory_metrics(scores),
        replay=replay_summary(fixed_replay.scores),
    )
    (output_path / "summary.json").write_text(
        json.dumps(campaign.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return campaign
