"""Offline LongMemEval pack comparison without claiming an official score."""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from rsicontext.policy import (
    Artifact,
    Budget,
    ContextPack,
    DocumentChunk,
    LexicalPolicy,
    PolicySpecV1,
    PolicySpecV1Interpreter,
)


@dataclass(frozen=True, slots=True)
class OfflinePackComparison:
    policy_name: str
    question_id: str
    packed_chunks: int
    token_count: int
    answer_string_present: bool
    eval_function: str | None = None


def last_k_pack(artifact: Artifact, budget: Budget, *, k: int) -> ContextPack:
    if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
        raise ValueError("k must be a positive integer")
    tail = artifact.chunks[-k:]
    selected = _fit(tail, budget)
    return _pack(selected)


def random_trajectory_pack(
    artifact: Artifact, budget: Budget, *, seed: int, chunk_count: int
) -> ContextPack:
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError("seed must be an integer")
    if not isinstance(chunk_count, int) or isinstance(chunk_count, bool) or chunk_count <= 0:
        raise ValueError("chunk_count must be a positive integer")
    if not artifact.chunks:
        return ContextPack()
    count = min(chunk_count, len(artifact.chunks))
    chosen = random.Random(seed).sample(list(artifact.chunks), count)  # nosec B311
    selected = _fit(tuple(chosen), budget)
    return _pack(selected)


def lexical_pack(artifact: Artifact, query: str, budget: Budget) -> ContextPack:
    return LexicalPolicy().assemble(artifact, query, budget)


def spec_v1_pack(artifact: Artifact, query: str, budget: Budget, spec: PolicySpecV1) -> ContextPack:
    return PolicySpecV1Interpreter().materialize(spec).assemble(artifact, query, budget)


def full_trace_pack(artifact: Artifact) -> ContextPack:
    return _pack(artifact.chunks)


def answer_string_present(pack: ContextPack, answer: str) -> bool:
    if not isinstance(answer, str) or not answer:
        raise ValueError("answer must be a non-empty string")
    haystack = "\n".join(pack.ordered_text())
    return answer in haystack


def compare_offline_pack(
    *,
    policy_name: str,
    question_id: str,
    pack: ContextPack,
    answer: str,
    eval_function: str | None = None,
) -> OfflinePackComparison:
    return OfflinePackComparison(
        policy_name=policy_name,
        question_id=question_id,
        packed_chunks=len(pack.spans),
        token_count=pack.token_count,
        answer_string_present=answer_string_present(pack, answer),
        eval_function=eval_function,
    )


def eval_function_family(eval_function: str) -> str:
    """Return the official evaluator name, dropping LongMemEval parameter suffixes."""

    if not isinstance(eval_function, str) or not eval_function.strip():
        raise ValueError("eval_function must be a non-empty string")
    return eval_function.split("|", 1)[0]


def summarize_offline_pack_rates(
    rows: Sequence[OfflinePackComparison],
    *,
    deterministic_evaluators: frozenset[str],
    weak_evaluators: frozenset[str],
) -> dict[str, dict[str, dict[str, float | int]]]:
    """Aggregate answer-string presence by policy and evaluator stratum."""

    grouped: dict[str, dict[str, list[OfflinePackComparison]]] = {
        "deterministic": {},
        "weak": {},
        "all": {},
    }
    for row in rows:
        family = eval_function_family(row.eval_function or "")
        if family in deterministic_evaluators:
            stratum = "deterministic"
        elif family in weak_evaluators:
            stratum = "weak"
        else:
            raise ValueError(f"unknown LongMemEval eval_function: {row.eval_function!r}")
        grouped[stratum].setdefault(row.policy_name, []).append(row)
        grouped["all"].setdefault(row.policy_name, []).append(row)

    def _rate(policy_rows: Sequence[OfflinePackComparison]) -> dict[str, float | int]:
        present = sum(row.answer_string_present for row in policy_rows)
        return {
            "answer_string_present_count": present,
            "item_count": len(policy_rows),
            "rate": present / len(policy_rows) if policy_rows else 0.0,
        }

    return {
        stratum: {name: _rate(policy_rows) for name, policy_rows in policies.items()}
        for stratum, policies in grouped.items()
    }


def _fit(chunks: Sequence[DocumentChunk], budget: Budget) -> tuple[DocumentChunk, ...]:
    selected: list[DocumentChunk] = []
    remaining = budget.max_tokens
    for chunk in chunks:
        if budget.max_chunks is not None and len(selected) >= budget.max_chunks:
            break
        if chunk.token_count > remaining:
            continue
        selected.append(chunk)
        remaining -= chunk.token_count
    return tuple(selected)


def _pack(chunks: tuple[DocumentChunk, ...]) -> ContextPack:
    return ContextPack(
        spans=chunks,
        ordering=tuple(chunk.chunk_id for chunk in chunks),
        token_count=sum(chunk.token_count for chunk in chunks),
    )
