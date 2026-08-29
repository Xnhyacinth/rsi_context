"""Visible-only autonomous researcher adapter for the dynamic 32K micro pilot.

This module qualifies the real coding-researcher process path.  It is not a sealed
evaluation and the fresh policy process provides execution freshness, not OS-level
confidentiality.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self

from rsicontext.campaign.researcher import (
    CampaignConfig,
    CandidateEvaluationError,
    ResearchCampaignResult,
    ResearcherTurnError,
    ResearchRoundRequest,
    RoundEvaluation,
    run_researcher_campaign,
)
from rsicontext.datasets import (
    DynamicPrivateItem,
    generate_dynamic_long_context_dataset,
)
from rsicontext.eval import (
    AuditedPolicyBundle,
    EvaluationItem,
    FreshProcessPolicyFactory,
    FrozenReader,
    PolicyProcessError,
    ReaderOutput,
    Scorer,
    exact_match,
)
from rsicontext.policy import Budget, ContextPack
from rsicontext.researcher import (
    ClaudeCommandBuilder,
    CodexCommandBuilder,
    NormalizedEvent,
    ProcessLimits,
    ResearcherProcessError,
    ResearcherProcessResult,
    ResearcherRequest,
    TokenUsage,
    run_researcher_process,
)
from rsicontext.researcher.api import (
    APIResearcherCommandBuilder,
    api_researcher_system_prompt_hash,
)

if TYPE_CHECKING:
    from rsicontext.experiment import APIProfile
    from rsicontext.registry import ServingProfile

ResearcherKind = Literal["codex", "claude", "api"]
ArtifactDelivery = Literal["workspace", "api-json"]


@dataclass(frozen=True, slots=True)
class DynamicReaderIdentity:
    """Frozen reader fields required to interpret an autonomous trajectory."""

    profile_id: str
    profile_hash: str
    provider: str
    requested_model: str
    provider_revision: str | None
    max_model_len: int
    max_output_tokens: int
    seed: int
    temperature: float
    chat_template_enable_thinking: bool | None
    serving_profile_id: str | None
    serving_profile_hash: str | None

    @classmethod
    def from_profile(
        cls,
        profile: APIProfile,
        *,
        max_output_tokens: int,
        serving_profile: ServingProfile | None = None,
    ) -> Self:
        """Copy the frozen API and optional local-serving identity exactly once."""

        if not isinstance(max_output_tokens, int) or isinstance(max_output_tokens, bool):
            raise TypeError("reader output limit must be an integer")
        if max_output_tokens <= 0 or max_output_tokens > profile.max_output_tokens:
            raise ValueError("reader output limit must be within the API profile")
        return cls(
            profile_id=profile.id,
            profile_hash=profile.profile_hash,
            provider=profile.provider,
            requested_model=profile.model,
            provider_revision=profile.provider_revision,
            max_model_len=profile.evaluation_max_model_len,
            max_output_tokens=max_output_tokens,
            seed=profile.seed,
            temperature=profile.temperature,
            chat_template_enable_thinking=profile.chat_template_enable_thinking,
            serving_profile_id=None if serving_profile is None else serving_profile.id,
            serving_profile_hash=(
                None if serving_profile is None else serving_profile.profile_hash
            ),
        )


@dataclass(frozen=True, slots=True)
class VisibleGoldEvidence:
    chunk_id: str
    source_index: int
    token_count: int
    text: str


@dataclass(frozen=True, slots=True)
class VisibleItemFeedback:
    """One visible failure record that may be shown to a coding researcher."""

    item_id: str
    query: str
    reference_answer: str
    baseline_score: float
    baseline_prediction: str
    gold_evidence: tuple[VisibleGoldEvidence, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "baseline_score": self.baseline_score,
            "baseline_prediction": self.baseline_prediction,
            "gold_evidence": [asdict(evidence) for evidence in self.gold_evidence],
            "item_id": self.item_id,
            "query": self.query,
            "reference_answer": self.reference_answer,
        }


@dataclass(frozen=True, slots=True)
class DynamicEvaluationObservation:
    round_index: int
    score: float
    item_scores: tuple[tuple[str, float], ...]
    predictions: tuple[tuple[str, str], ...]
    reader_calls: int
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ResearcherPromptRecord:
    round_index: int
    parent_artifact_id: str
    prompt: str
    prompt_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ResearcherIdentity:
    kind: ResearcherKind
    model: str | None
    executable_path: str
    executable_sha256: str
    profile_id: str | None = None
    profile_hash: str | None = None
    system_prompt_sha256: str | None = None
    endpoint_sha256: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ResearcherProcessFailure:
    round_index: int
    parent_artifact_id: str
    error_type: str
    error_bytes: int
    error_sha256: str
    elapsed_seconds: float
    stdout_bytes: int | None = None
    stderr_bytes: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {**asdict(self), "usage": None}


@dataclass(slots=True)
class DynamicFreshEvaluator:
    """Evaluate an audited candidate with one fresh interpreter and reader call per item."""

    items: tuple[EvaluationItem, ...]
    reader: FrozenReader
    budget: Budget
    entrypoint: str = "policy.py"
    scorer: Scorer = exact_match
    timer: Callable[[], float] = time.perf_counter
    observations: list[DynamicEvaluationObservation] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.items = tuple(self.items)
        if not self.items:
            raise ValueError("dynamic evaluator items must be non-empty")
        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("dynamic evaluator item ids must be unique")

    def __call__(self, policy_directory: Path, *, round_index: int) -> RoundEvaluation:
        return self.evaluate_directory(policy_directory, round_index=round_index)

    def evaluate_directory(self, policy_directory: Path, *, round_index: int) -> RoundEvaluation:
        bundle = AuditedPolicyBundle.from_directory(
            policy_directory,
            entrypoint=self.entrypoint,
        )
        factory = FreshProcessPolicyFactory(bundle)
        contexts: list[tuple[EvaluationItem, ContextPack]] = []
        before = self.timer()
        try:
            for item in self.items:
                context = factory().assemble(item.artifact, item.query, self.budget)
                context.validate(item.artifact, self.budget)
                _require_single_reader_context(context)
                contexts.append((item, context))
        except (PolicyProcessError, ValueError) as exc:
            raise CandidateEvaluationError(
                f"candidate policy produced no ContextPack: {exc}"
            ) from exc

        item_scores: list[tuple[str, float]] = []
        predictions: list[tuple[str, str]] = []
        reader_input_tokens = 0
        reader_output_tokens = 0
        for item, context in contexts:
            output = self.reader.read(item.query, context)
            if not isinstance(output, ReaderOutput):
                raise TypeError("reader must return ReaderOutput")
            item_scores.append((item.item_id, self.scorer(output.answer, item.answer)))
            predictions.append((item.item_id, output.answer))
            reader_input_tokens += output.input_tokens
            reader_output_tokens += output.output_tokens
        elapsed = _elapsed(self.timer() - before)
        score = sum(score for _, score in item_scores) / len(item_scores)
        observation = DynamicEvaluationObservation(
            round_index=round_index,
            score=score,
            item_scores=tuple(item_scores),
            predictions=tuple(predictions),
            reader_calls=len(self.items),
            reader_input_tokens=reader_input_tokens,
            reader_output_tokens=reader_output_tokens,
            wall_seconds=elapsed,
        )
        self.observations.append(observation)
        return RoundEvaluation(
            score=score,
            item_scores=observation.item_scores,
            reader_input_tokens=reader_input_tokens,
            reader_output_tokens=reader_output_tokens,
            wall_seconds=elapsed,
        )


@dataclass(slots=True)
class DynamicResearcherCallback:
    """Turn a campaign request into one bounded coding-CLI or API process."""

    visible_feedback: tuple[VisibleItemFeedback, ...]
    researcher_kind: ResearcherKind
    researcher_executable: str
    process_limits: ProcessLimits
    researcher_model: str | None = None
    environment_allowlist: tuple[str, ...] = ()
    max_budget_usd: float | None = None
    api_profiles_path: Path | None = None
    api_profile_id: str | None = None
    evaluation_observations: list[DynamicEvaluationObservation] = field(default_factory=list)
    prompts: list[ResearcherPromptRecord] = field(default_factory=list, init=False)
    results: list[ResearcherProcessResult] = field(default_factory=list, init=False)
    process_failures: list[ResearcherProcessFailure] = field(default_factory=list, init=False)

    def __call__(self, request: ResearchRoundRequest) -> None:
        prior = self.evaluation_observations[-1] if self.evaluation_observations else None
        if prior is not None and prior.round_index != request.round_index - 1:
            raise ValueError("prior visible outcomes do not match the requested parent round")
        prompt = _build_research_prompt(
            request,
            self.visible_feedback,
            prior,
            artifact_delivery="api-json" if self.researcher_kind == "api" else "workspace",
        )
        self.prompts.append(
            ResearcherPromptRecord(
                round_index=request.round_index,
                parent_artifact_id=request.parent_artifact_id,
                prompt=prompt,
                prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
            )
        )
        researcher_request = ResearcherRequest(
            workspace=request.workspace,
            prompt=prompt,
            model=self.researcher_model,
            max_budget_usd=self.max_budget_usd,
        )
        if self.researcher_kind == "codex":
            spec = CodexCommandBuilder(executable=self.researcher_executable).build(
                researcher_request
            )
        elif self.researcher_kind == "claude":
            spec = ClaudeCommandBuilder(executable=self.researcher_executable).build(
                researcher_request
            )
        elif self.researcher_kind == "api":
            if self.api_profiles_path is None or self.api_profile_id is None:
                raise ValueError("API researcher requires a profiles path and profile id")
            spec = APIResearcherCommandBuilder(
                python_executable=Path(self.researcher_executable),
                profiles_path=self.api_profiles_path,
                profile_id=self.api_profile_id,
            ).build(researcher_request)
        else:
            raise ValueError(f"unsupported researcher kind: {self.researcher_kind}")
        process_started = time.perf_counter()
        try:
            result = run_researcher_process(
                spec,
                limits=self.process_limits,
                environment_allowlist=self.environment_allowlist,
            )
        except Exception as exc:
            error = str(exc).encode()
            stdout = getattr(exc, "stdout", b"") or b""
            stderr = getattr(exc, "stderr", b"") or b""
            self.process_failures.append(
                ResearcherProcessFailure(
                    round_index=request.round_index,
                    parent_artifact_id=request.parent_artifact_id,
                    error_type=type(exc).__name__,
                    error_bytes=len(error),
                    error_sha256=hashlib.sha256(error).hexdigest(),
                    elapsed_seconds=_elapsed(time.perf_counter() - process_started),
                    stdout_bytes=len(stdout) or None,
                    stderr_bytes=len(stderr) or None,
                )
            )
            if isinstance(exc, ResearcherProcessError):
                raise ResearcherTurnError(str(exc)) from exc
            raise
        self.results.append(result)
        _reject_visible_hardcoding(request.policy_directory, self.visible_feedback)


@dataclass(frozen=True, slots=True)
class AutonomousDynamicPilotResult:
    schema_version: int
    dataset_fingerprint: str
    split: str
    items_per_profile: int
    rounds: int
    baseline_score: float
    reader_calls: int
    reader_input_tokens: int
    reader_output_tokens: int
    researcher_usage: tuple[TokenUsage, ...]
    researcher_identity: ResearcherIdentity
    researcher_prompts: tuple[ResearcherPromptRecord, ...]
    researcher_processes: tuple[ResearcherProcessResult, ...]
    evaluation_observations: tuple[DynamicEvaluationObservation, ...]
    campaign: ResearchCampaignResult
    reader_identity: DynamicReaderIdentity | None
    qualification_only: bool = True
    autonomous_researcher: bool = True
    formal_sealed_isolation: bool = False
    process_failures: tuple[ResearcherProcessFailure, ...] = ()
    cost_accounting_complete: bool = True

    def to_dict(self) -> dict[str, Any]:
        artifact_summary = {
            "candidate_artifact_ids": [
                round_.candidate_artifact_id for round_ in self.campaign.rounds
            ],
            "evaluation_artifact_ids": [
                round_.evaluation_artifact_id for round_ in self.campaign.rounds
            ],
            "seed_artifact_id": self.campaign.seed_artifact_id,
            "selected_round": self.campaign.selected_round,
        }
        return {
            "artifact_summary": artifact_summary,
            "autonomous_researcher": self.autonomous_researcher,
            "baseline_score": self.baseline_score,
            "campaign": self.campaign.to_dict(),
            "cost_accounting_complete": self.cost_accounting_complete,
            "dataset_fingerprint": self.dataset_fingerprint,
            "formal_sealed_isolation": self.formal_sealed_isolation,
            "items_per_profile": self.items_per_profile,
            "process_failures": [failure.to_dict() for failure in self.process_failures],
            "qualification_only": self.qualification_only,
            "reader_calls": self.reader_calls,
            "reader_input_tokens": self.reader_input_tokens,
            "reader_output_tokens": self.reader_output_tokens,
            "reader_identity": (
                asdict(self.reader_identity) if self.reader_identity is not None else None
            ),
            "researcher_identity": self.researcher_identity.to_dict(),
            "researcher_traces": _researcher_traces(
                self.researcher_prompts,
                self.researcher_processes,
                self.process_failures,
            ),
            "researcher_usage": [asdict(usage) for usage in self.researcher_usage],
            "evaluation_observations": [
                observation.to_dict() for observation in self.evaluation_observations
            ],
            "rounds": self.rounds,
            "schema_version": self.schema_version,
            "split": self.split,
        }


def build_visible_feedback_from_items(
    items: Iterable[EvaluationItem],
    baseline: RoundEvaluation,
    *,
    baseline_predictions: tuple[tuple[str, str], ...],
) -> tuple[VisibleItemFeedback, ...]:
    """Join evaluator-owned visible gold evidence with a baseline score trace."""

    visible_items = tuple(items)
    scores = dict(baseline.item_scores)
    predictions = dict(baseline_predictions)
    expected_ids = {item.item_id for item in visible_items}
    if set(scores) != expected_ids or set(predictions) != expected_ids:
        raise ValueError("baseline feedback coverage does not match visible items")
    feedback: list[VisibleItemFeedback] = []
    for item in visible_items:
        evidence = tuple(
            VisibleGoldEvidence(
                chunk_id=chunk.chunk_id,
                source_index=index,
                token_count=chunk.token_count,
                text=chunk.text,
            )
            for index, chunk in enumerate(item.artifact.chunks)
            if chunk.chunk_id in item.gold_chunk_ids
        )
        feedback.append(
            VisibleItemFeedback(
                item_id=item.item_id,
                query=item.query,
                reference_answer=item.answer,
                baseline_score=scores[item.item_id],
                baseline_prediction=predictions[item.item_id],
                gold_evidence=evidence,
            )
        )
    return tuple(feedback)


def build_visible_feedback(
    private_items: Iterable[DynamicPrivateItem],
    baseline: RoundEvaluation,
    *,
    baseline_predictions: tuple[tuple[str, str], ...],
) -> tuple[VisibleItemFeedback, ...]:
    """Join homemade visible items with a baseline score trace."""

    return build_visible_feedback_from_items(
        (item.evaluation_item for item in private_items),
        baseline,
        baseline_predictions=baseline_predictions,
    )


def public_visible_items_fingerprint(
    *,
    cell_id: str,
    items: tuple[EvaluationItem, ...],
    pack_budget_tokens: int,
    scorer_name: str,
) -> str:
    """Bind public visible items without homemade generator metadata."""

    if not cell_id.strip():
        raise ValueError("cell_id must be a non-empty string")
    if not items:
        raise ValueError("public fingerprint items must be non-empty")
    payload = {
        "cell_id": cell_id,
        "items": [
            {
                "answer": item.answer,
                "chunks": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "sha256": hashlib.sha256(chunk.text.encode()).hexdigest(),
                        "token_count": chunk.token_count,
                    }
                    for chunk in item.artifact.chunks
                ],
                "gold_chunk_ids": sorted(item.gold_chunk_ids),
                "item_id": item.item_id,
                "query": item.query,
            }
            for item in items
        ],
        "pack_budget_tokens": pack_budget_tokens,
        "schema": "public-visible-v1",
        "scorer": scorer_name,
    }
    blob = json.dumps(payload, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def run_autonomous_dynamic_pilot(
    *,
    initial_policy_directory: str | Path,
    output_directory: str | Path,
    reader: FrozenReader,
    researcher_executable: str,
    researcher_kind: ResearcherKind = "codex",
    researcher_model: str | None = None,
    researcher_environment_allowlist: tuple[str, ...] = (),
    researcher_api_profiles_path: Path | None = None,
    researcher_api_profile_id: str | None = None,
    researcher_endpoint_sha256: str | None = None,
    max_budget_usd: float | None = None,
    dataset_seed: str = "autonomous-dynamic-visible-v1",
    items_per_profile: int = 2,
    rounds: int = 2,
    budget: Budget | None = None,
    process_limits: ProcessLimits | None = None,
    reader_identity: DynamicReaderIdentity | None = None,
    visible_items: tuple[EvaluationItem, ...] | None = None,
    dataset_fingerprint: str | None = None,
    scorer: Scorer = exact_match,
) -> AutonomousDynamicPilotResult:
    """Run a visible qualification with an actual researcher CLI process."""

    output = _create_new_output(output_directory)
    actual_budget = budget or Budget(8_192)
    actual_process_limits = process_limits or ProcessLimits()
    if visible_items is None:
        dataset = generate_dynamic_long_context_dataset(
            seed=dataset_seed,
            items_per_profile=items_per_profile,
        )
        items = tuple(item.evaluation_item for item in dataset.visible_items())
        fingerprint = dataset.fingerprint
    else:
        if dataset_fingerprint is None or not dataset_fingerprint.strip():
            raise ValueError("dataset_fingerprint is required when visible_items are supplied")
        items = visible_items
        fingerprint = dataset_fingerprint
        items_per_profile = len(items)
    if not items:
        raise ValueError("visible campaign items must be non-empty")
    baseline_evaluator = DynamicFreshEvaluator(
        items=items,
        reader=reader,
        budget=actual_budget,
        entrypoint="seed.py",
        scorer=scorer,
    )
    baseline = baseline_evaluator.evaluate_directory(
        Path(initial_policy_directory),
        round_index=-1,
    )
    feedback = build_visible_feedback_from_items(
        items,
        baseline,
        baseline_predictions=baseline_evaluator.observations[-1].predictions,
    )
    evaluator = DynamicFreshEvaluator(
        items=items,
        reader=reader,
        budget=actual_budget,
        scorer=scorer,
    )
    researcher = DynamicResearcherCallback(
        visible_feedback=feedback,
        researcher_kind=researcher_kind,
        researcher_executable=researcher_executable,
        process_limits=actual_process_limits,
        researcher_model=researcher_model,
        environment_allowlist=researcher_environment_allowlist,
        max_budget_usd=max_budget_usd,
        api_profiles_path=researcher_api_profiles_path,
        api_profile_id=researcher_api_profile_id,
        evaluation_observations=evaluator.observations,
    )
    researcher_identity = _researcher_identity(
        kind=researcher_kind,
        model=researcher_model,
        executable=researcher_executable,
        api_profiles_path=researcher_api_profiles_path,
        api_profile_id=researcher_api_profile_id,
        endpoint_sha256=researcher_endpoint_sha256,
    )
    try:
        campaign = run_researcher_campaign(
            initial_policy_directory=initial_policy_directory,
            output_directory=output / "campaign",
            researcher=researcher,
            evaluator=evaluator,
            initial_evaluation=baseline,
            config=CampaignConfig(
                rounds=rounds,
                prediction_item_ids=tuple(item.item_id for item in items),
            ),
        )
    except Exception as exc:
        error = str(exc).encode()
        _write_new_json(
            output / "failure.json",
            {
                "cost_accounting_complete": not researcher.process_failures,
                "dataset_fingerprint": fingerprint,
                "error_bytes": len(error),
                "error_sha256": hashlib.sha256(error).hexdigest(),
                "error_type": type(exc).__name__,
                "evaluation_observations": [
                    observation.to_dict()
                    for observation in (*baseline_evaluator.observations, *evaluator.observations)
                ],
                "processes": [_process_result_to_dict(process) for process in researcher.results],
                "process_failures": [failure.to_dict() for failure in researcher.process_failures],
                "reader_identity": (
                    asdict(reader_identity) if reader_identity is not None else None
                ),
                "researcher_identity": researcher_identity.to_dict(),
                "researcher_prompts": [prompt.to_dict() for prompt in researcher.prompts],
                "schema_version": 3,
                "split": "visible",
                "status": "failed",
            },
        )
        raise
    all_observations = (*baseline_evaluator.observations, *evaluator.observations)
    result = AutonomousDynamicPilotResult(
        schema_version=3,
        dataset_fingerprint=fingerprint,
        split="visible",
        items_per_profile=items_per_profile,
        rounds=rounds,
        baseline_score=baseline.score,
        reader_calls=sum(observation.reader_calls for observation in all_observations),
        reader_input_tokens=sum(
            observation.reader_input_tokens for observation in all_observations
        ),
        reader_output_tokens=sum(
            observation.reader_output_tokens for observation in all_observations
        ),
        researcher_usage=tuple(process.usage for process in researcher.results),
        researcher_identity=researcher_identity,
        researcher_prompts=tuple(researcher.prompts),
        researcher_processes=tuple(researcher.results),
        evaluation_observations=all_observations,
        campaign=campaign,
        reader_identity=reader_identity,
        process_failures=tuple(researcher.process_failures),
        cost_accounting_complete=not researcher.process_failures,
    )
    _write_new_json(output / "pilot_summary.json", result.to_dict())
    return result


def _require_single_reader_context(context: ContextPack) -> None:
    if context.abstain or context.request_reread is not None:
        raise ValueError("dynamic single-reader pilot requires exactly one target-model call")


def _build_research_prompt(
    request: ResearchRoundRequest,
    feedback: tuple[VisibleItemFeedback, ...],
    prior: DynamicEvaluationObservation | None,
    *,
    artifact_delivery: ArtifactDelivery = "workspace",
) -> str:
    item_ids = tuple(item.item_id for item in feedback)
    if item_ids != request.prediction_item_ids:
        raise ValueError("research prompt item order does not match the campaign contract")
    manifest = _manifest_template(request, item_ids)
    feedback_payload = [item.to_dict() for item in feedback]
    prior_payload: list[dict[str, object]] = []
    if prior is not None:
        prior_scores = dict(prior.item_scores)
        prior_predictions = dict(prior.predictions)
        if set(prior_scores) != set(item_ids) or set(prior_predictions) != set(item_ids):
            raise ValueError("prior visible outcome coverage does not match the campaign")
        prior_payload = [
            {
                "item_id": item_id,
                "prediction": prior_predictions[item_id],
                "score": prior_scores[item_id],
            }
            for item_id in item_ids
        ]
    if artifact_delivery == "workspace":
        delivery = (
            "Work only inside this workspace. Modify only policy/*.py and create "
            "manifest.json.\n"
            "Do not create notes, tests, caches, or any other files. Do not call any model or "
            "API.\n"
        )
        finish = (
            "Finish only after policy/*.py and manifest.json are complete. Do not answer the "
            "visible questions in your response.\n"
        )
    elif artifact_delivery == "api-json":
        parent_policy = {
            path.relative_to(request.policy_directory).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(request.policy_directory.rglob("*.py"))
        }
        if not parent_policy:
            raise ValueError("API researcher parent policy is empty")
        delivery = (
            "Do not modify the workspace or call tools. Return exactly one JSON artifact with "
            "schema_version=1, policy_source containing the complete policy/policy.py source, "
            "and manifest containing the complete manifest object. The exact parent policy is "
            "included below; preserve it unless your stated hypothesis requires a change.\n"
            "PARENT_POLICY_BEGIN\n"
            + json.dumps(parent_policy, ensure_ascii=False, indent=2, sort_keys=True)
            + "\nPARENT_POLICY_END\n"
        )
        finish = (
            "Return only that JSON artifact. Do not answer the visible questions or include "
            "Markdown fences.\n"
        )
    else:
        raise ValueError(f"unsupported artifact delivery: {artifact_delivery}")
    return (
        "You are the context-policy researcher, not the question-answering reader.\n"
        "The reader, decoding, metric, 8192-token budget, and item labels are frozen.\n"
        "You choose the next hypothesis for compiler H: select, order, cover, abstain, "
        "and format of packed evidence. You do not choose extra reader calls; the evaluator "
        "returns one score per candidate. Put the hypothesis in mechanisms[0].description. "
        "The next round starts from your last attempt even if it regressed; historical-best "
        "keeps the peak.\n" + delivery + "Implement policy/policy.py with public class Policy and "
        "assemble(artifact, query, budget).\n"
        "The runtime passes rsicontext.policy.Artifact and Budget objects, not dictionaries: "
        "read artifact.chunks; each DocumentChunk has chunk_id, document_id, start, end, text, "
        "token_count, and role attributes; read budget.max_tokens. You must return a ContextPack, "
        "not a string or dictionary. Prefer composing the public policy dataclasses or existing "
        "TruncationPolicy and LexicalPolicy implementations from rsicontext.policy.\n"
        "There is no rsicontext.policy.Policy symbol. A direct pack has the form "
        "ContextPack(spans=tuple(selected_chunks), ordering=tuple(chunk.chunk_id for chunk in "
        "selected_chunks), token_count=sum(chunk.token_count for chunk in selected_chunks)).\n"
        "The policy must pass a fail-closed AST audit. Do not use from __future__ imports. "
        "Allowed imports are collections, dataclasses, functools, heapq, itertools, json, "
        "math, operator, re, statistics, string, typing, and rsicontext.policy. "
        "Keep module/class constants to immutable literals or tuples; construct regexes, "
        "sets, counters, and other containers inside functions. Builtin compile, eval, "
        "exec, and getattr are forbidden; re.compile and re.findall inside functions are "
        "allowed. Do not use file I/O, subprocesses, or network access.\n"
        "Do not run mypy, pytest, or any command that creates caches in the workspace.\n"
        "Return only source chunks already present in artifact and obey ContextPack provenance.\n"
        "Do not put item ids, chunk ids, queries, reference answers, or per-item lookup tables in "
        "policy code. The policy must generalize from query and chunk content.\n"
        "The evidence below is from the visible split only. No gate or sealed item is exposed.\n"
        f"Round: {request.round_index}\n"
        f"Exact parent_artifact_id: {request.parent_artifact_id}\n"
        f"Previous aggregate score: {request.previous_score}\n"
        f"Historical-best aggregate score: {request.incumbent_score}\n"
        "LAST_INVALID_SUBMISSION_BEGIN\n"
        + json.dumps(request.last_invalid_reason, ensure_ascii=False)
        + "\nLAST_INVALID_SUBMISSION_END\n"
        "VISIBLE_FEEDBACK_BEGIN\n"
        + json.dumps(feedback_payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\nVISIBLE_FEEDBACK_END\n"
        "PRIOR_CANDIDATE_VISIBLE_OUTCOMES_BEGIN\n"
        + json.dumps(prior_payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\nPRIOR_CANDIDATE_VISIBLE_OUTCOMES_END\n"
        "The manifest must cover exactly these item ids in this order: "
        + json.dumps(item_ids)
        + "\nEdit the probabilities, claims, cost estimates, and recommendation so they state "
        "your pre-evaluation prediction. The maximum regression probability in promotion must "
        "equal the maximum prediction regress value. Every mechanism policy path must exist.\n"
        "MANIFEST_TEMPLATE_BEGIN\n"
        + json.dumps(manifest, indent=2, sort_keys=True)
        + "\nMANIFEST_TEMPLATE_END\n"
        + finish
    )


def _manifest_template(
    request: ResearchRoundRequest, item_ids: tuple[str, ...]
) -> dict[str, object]:
    return {
        "candidate_name": f"dynamic-visible-r{request.round_index}",
        "cost": {
            "evaluation_input_tokens": 0,
            "evaluation_output_tokens": 0,
            "gpu_seconds": 0.0,
            "researcher_input_tokens": 0,
            "researcher_output_tokens": 0,
            "wall_seconds": 0.0,
        },
        "evidence": [
            {
                "claim": "Visible baseline failures and gold spans motivate the proposed policy.",
                "evidence_id": "visible-baseline",
                "kind": "visible-item-trace",
                "reference": "VISIBLE_FEEDBACK_BEGIN",
            }
        ],
        "mechanisms": [
            {
                "description": "Replace this with the hypothesized general policy mechanism.",
                "mechanism_id": "policy-mechanism",
                "policy_paths": ["policy/policy.py"],
            }
        ],
        "parent_artifact_id": request.parent_artifact_id,
        "predictions": [
            {
                "evidence_ids": ["visible-baseline"],
                "item_id": item_id,
                "mechanism_ids": ["policy-mechanism"],
                "probabilities": {"improve": 0.5, "regress": 0.1, "unchanged": 0.4},
            }
            for item_id in item_ids
        ],
        "promotion": {
            "decision": "hold",
            "expected_score_delta": 0.0,
            "max_regression_probability": 0.1,
            "rationale": "Replace with a pre-evaluation recommendation.",
        },
        "schema_version": 1,
    }


def _reject_visible_hardcoding(
    policy_directory: Path,
    feedback: tuple[VisibleItemFeedback, ...],
) -> None:
    forbidden = {
        value
        for item in feedback
        for value in (
            item.item_id,
            item.query,
            *(evidence.chunk_id for evidence in item.gold_evidence),
            *((item.reference_answer,) if len(item.reference_answer.strip()) >= 24 else ()),
        )
    }
    for path in policy_directory.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if any(value in source for value in forbidden):
            raise ValueError(f"candidate policy appears to hardcode visible data: {path.name}")


def _create_new_output(raw_output: str | Path) -> Path:
    output = Path(raw_output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"pilot output already exists: {output}")
    output.mkdir(parents=True)
    return output.resolve()


def _write_new_json(path: Path, value: object) -> None:
    payload = json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="utf-8") as handle:
        handle.write(payload)


def _researcher_identity(
    *,
    kind: ResearcherKind,
    model: str | None,
    executable: str,
    api_profiles_path: Path | None = None,
    api_profile_id: str | None = None,
    endpoint_sha256: str | None = None,
) -> ResearcherIdentity:
    resolved = shutil.which(executable)
    if resolved is None:
        raise FileNotFoundError(f"researcher executable was not found: {executable}")
    path = Path(resolved).absolute()
    if not path.is_file():
        raise FileNotFoundError(f"researcher executable is not a file: {path}")
    profile_id = None
    profile_hash = None
    system_prompt_sha256 = None
    if kind == "api":
        if api_profiles_path is None or api_profile_id is None:
            raise ValueError("API researcher requires a profiles path and profile id")
        from rsicontext.experiment import load_api_profiles

        profile = load_api_profiles(api_profiles_path).get(api_profile_id)
        if model is not None and model != profile.model:
            raise ValueError("researcher model does not match the API profile")
        model = profile.model
        profile_id = profile.id
        profile_hash = profile.profile_hash
        system_prompt_sha256 = api_researcher_system_prompt_hash()
    elif any(value is not None for value in (api_profiles_path, api_profile_id, endpoint_sha256)):
        raise ValueError("API researcher identity fields require researcher kind api")
    return ResearcherIdentity(
        kind=kind,
        model=model,
        executable_path=str(path),
        executable_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        profile_id=profile_id,
        profile_hash=profile_hash,
        system_prompt_sha256=system_prompt_sha256,
        endpoint_sha256=endpoint_sha256,
    )


def _process_result_to_dict(result: ResearcherProcessResult) -> dict[str, object]:
    return {
        "elapsed_seconds": result.elapsed_seconds,
        "events": [_event_to_dict(event) for event in result.events],
        "returncode": result.returncode,
        "stderr_bytes": result.stderr_bytes,
        "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
        "stdout_bytes": result.stdout_bytes,
        "usage": asdict(result.usage),
    }


def _event_to_dict(event: NormalizedEvent) -> dict[str, object]:
    payload = json.dumps(
        dict(event.payload),
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return {
        "kind": event.kind,
        "payload_bytes": len(payload),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "session_id_sha256": _optional_text_digest(event.session_id),
        "source": event.source,
        "text_bytes": len(event.text.encode()) if event.text is not None else 0,
        "text_sha256": _optional_text_digest(event.text),
        "tool_name_sha256": _optional_text_digest(event.tool_name),
        "usage": asdict(event.usage) if event.usage is not None else None,
    }


def _optional_text_digest(value: str | None) -> str | None:
    return hashlib.sha256(value.encode()).hexdigest() if value is not None else None


def _researcher_traces(
    prompts: tuple[ResearcherPromptRecord, ...],
    processes: tuple[ResearcherProcessResult, ...],
    failures: tuple[ResearcherProcessFailure, ...] = (),
) -> list[dict[str, object]]:
    failures_by_round = {failure.round_index: failure for failure in failures}
    process_iter = iter(processes)
    traces: list[dict[str, object]] = []
    for prompt in prompts:
        failure = failures_by_round.get(prompt.round_index)
        if failure is not None:
            traces.append({**prompt.to_dict(), "failure": failure.to_dict(), "process": None})
            continue
        process = next(process_iter, None)
        if process is None:
            raise ValueError("successful pilot has incomplete researcher trace records")
        traces.append({**prompt.to_dict(), "process": _process_result_to_dict(process)})
    if next(process_iter, None) is not None:
        raise ValueError("successful pilot has unmatched researcher process records")
    return traces


def _elapsed(value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise RuntimeError("dynamic evaluator timer returned an invalid duration")
    return value
