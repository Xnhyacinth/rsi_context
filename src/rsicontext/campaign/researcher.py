"""Callback-only orchestration contract for a bounded researcher campaign.

This module deliberately does not invoke a researcher CLI and does not import or
execute candidate policy code. Production adapters must run both operations in
separate, fresh processes. The callbacks here qualify campaign bookkeeping; by
themselves they are not evidence of autonomous policy discovery or formal process
isolation.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from rsicontext.analysis.process import CampaignProcessTrace, campaign_process_trace
from rsicontext.artifacts import ArtifactStore, Manifest, load_manifest
from rsicontext.security import PolicyAuditor, PolicySecurityError


class CampaignError(ValueError):
    """Raised when researcher-campaign boundaries are violated."""


class ResearcherTurnError(RuntimeError):
    """Raised when a researcher turn fails before a scorable candidate exists."""


@dataclass(frozen=True, slots=True)
class CampaignConfig:
    """Benchmark-owned controls for one callback campaign."""

    prediction_item_ids: tuple[str, ...]
    rounds: int = 5
    promotion_margin: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.rounds, int) or isinstance(self.rounds, bool) or self.rounds < 1:
            raise CampaignError("rounds must be a positive integer")
        if not self.prediction_item_ids:
            raise CampaignError("prediction_item_ids must be non-empty")
        if len(self.prediction_item_ids) != len(set(self.prediction_item_ids)):
            raise CampaignError("prediction_item_ids must be unique")
        if any(
            not isinstance(item_id, str) or not item_id.strip()
            for item_id in self.prediction_item_ids
        ):
            raise CampaignError("prediction_item_ids must contain non-empty strings")
        if (
            isinstance(self.promotion_margin, bool)
            or not isinstance(self.promotion_margin, (int, float))
            or not math.isfinite(self.promotion_margin)
            or self.promotion_margin < 0
        ):
            raise CampaignError("promotion_margin must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ResearchRoundRequest:
    """Paths and prior aggregate feedback exposed to a researcher callback."""

    round_index: int
    workspace: Path
    policy_directory: Path
    manifest_path: Path
    parent_artifact_id: str
    incumbent_artifact_id: str | None
    previous_score: float | None
    incumbent_score: float | None
    prediction_item_ids: tuple[str, ...]
    last_invalid_reason: str | None = None


class ResearcherCallback(Protocol):
    """Testable adapter boundary; implementations edit policy and manifest only."""

    def __call__(self, request: ResearchRoundRequest) -> None: ...


@dataclass(frozen=True, slots=True)
class RoundEvaluation:
    """Evaluator-owned observation returned after isolated candidate execution."""

    score: float
    item_scores: tuple[tuple[str, float], ...]
    reader_input_tokens: int
    reader_output_tokens: int
    wall_seconds: float

    def __post_init__(self) -> None:
        _score(self.score, field="score")
        item_ids: list[str] = []
        for item_id, item_score in self.item_scores:
            if not isinstance(item_id, str) or not item_id.strip():
                raise CampaignError("evaluation item ids must be non-empty strings")
            _score(item_score, field=f"item_scores[{item_id!r}]")
            item_ids.append(item_id)
        if len(item_ids) != len(set(item_ids)):
            raise CampaignError("evaluation item ids must be unique")
        for field_name, value in (
            ("reader_input_tokens", self.reader_input_tokens),
            ("reader_output_tokens", self.reader_output_tokens),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise CampaignError(f"{field_name} must be a non-negative integer")
        if (
            isinstance(self.wall_seconds, bool)
            or not isinstance(self.wall_seconds, (int, float))
            or not math.isfinite(self.wall_seconds)
            or self.wall_seconds < 0
        ):
            raise CampaignError("wall_seconds must be finite and non-negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "item_scores": dict(self.item_scores),
            "reader_input_tokens": self.reader_input_tokens,
            "reader_output_tokens": self.reader_output_tokens,
            "score": self.score,
            "wall_seconds": self.wall_seconds,
        }


class IsolatedEvaluatorCallback(Protocol):
    """Boundary to an evaluator that owns fresh-process candidate execution.

    The campaign runner cannot prove that a callback is isolated. A production
    adapter is responsible for process creation and must return only this record.
    """

    def __call__(self, policy_directory: Path, *, round_index: int) -> RoundEvaluation: ...


@dataclass(frozen=True, slots=True)
class ResearchCampaignRound:
    round_index: int
    candidate_name: str
    parent_artifact_id: str
    candidate_artifact_id: str
    manifest_artifact_id: str
    evaluation_artifact_id: str
    promotion_artifact_id: str
    score: float
    promoted: bool
    incumbent_artifact_id: str
    researcher_recommendation: str
    valid: bool = True
    invalid_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ResearchCampaignResult:
    """Immutable identifiers and outcomes from a callback campaign."""

    seed_artifact_id: str
    rounds: tuple[ResearchCampaignRound, ...]
    selected_round: int | None
    seed_evaluation_artifact_id: str | None = None
    callback_only: bool = True
    formal_process_isolation: bool = False
    process: CampaignProcessTrace | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def run_researcher_campaign(
    *,
    initial_policy_directory: str | Path,
    output_directory: str | Path,
    researcher: ResearcherCallback,
    evaluator: IsolatedEvaluatorCallback,
    config: CampaignConfig,
    initial_evaluation: RoundEvaluation | None = None,
) -> ResearchCampaignResult:
    """Run an audited callback loop and preserve every candidate and decision.

    Historical-best promotion is benchmark-controlled, while the next research
    round starts from the previous attempt. This preserves regressions in the
    trajectory without losing the selected peak. A researcher turn that fails
    before a scorable H exists is recorded as invalid, keeps the last valid
    parent, and does not call the frozen reader.
    """

    if not callable(researcher) or not callable(evaluator):
        raise TypeError("researcher and evaluator must be callable")
    output = _prepare_output(output_directory)
    store = ArtifactStore(output / "store")
    auditor = PolicyAuditor()
    seed_policy = Path(initial_policy_directory)
    seed_files = _audited_policy_files(seed_policy, auditor)
    seed_record = store.put_files(seed_files, kind="seed-policy", metadata={"role": "seed"})

    parent_artifact_id = seed_record.artifact_id
    snapshots: list[dict[str, bytes]] = [seed_files]
    seed_evaluation_artifact_id: str | None = None
    incumbent_artifact_id: str | None = None
    incumbent_score: float | None = None
    previous_score: float | None = None
    selected_round: int | None = None
    h0_score: float | None = None
    if initial_evaluation is not None:
        if not isinstance(initial_evaluation, RoundEvaluation):
            raise TypeError("initial_evaluation must be a RoundEvaluation or null")
        _validate_evaluation_coverage(initial_evaluation, config.prediction_item_ids)
        seed_evaluation_record = store.put_text(
            _json_text(initial_evaluation.to_dict()),
            kind="seed-evaluation",
            parents=(seed_record.artifact_id,),
            metadata={"role": "seed"},
        )
        seed_evaluation_artifact_id = seed_evaluation_record.artifact_id
        incumbent_artifact_id = seed_record.artifact_id
        incumbent_score = initial_evaluation.score
        previous_score = initial_evaluation.score
        selected_round = None
        h0_score = initial_evaluation.score
    rounds: list[ResearchCampaignRound] = []
    last_invalid_reason: str | None = None

    for round_index in range(config.rounds):
        workspace = output / "workspaces" / f"round-{round_index:02d}"
        policy_directory = _materialize_clean_workspace(store, parent_artifact_id, workspace)
        manifest_path = workspace / "manifest.json"
        request = ResearchRoundRequest(
            round_index=round_index,
            workspace=workspace,
            policy_directory=policy_directory,
            manifest_path=manifest_path,
            parent_artifact_id=parent_artifact_id,
            incumbent_artifact_id=incumbent_artifact_id,
            previous_score=previous_score,
            incumbent_score=incumbent_score,
            prediction_item_ids=config.prediction_item_ids,
            last_invalid_reason=last_invalid_reason,
        )
        try:
            researcher(request)
        except ResearcherTurnError as exc:
            rounds.append(
                _record_invalid_submission(
                    store,
                    policy_directory=policy_directory,
                    manifest_path=manifest_path,
                    parent_artifact_id=parent_artifact_id,
                    incumbent_artifact_id=incumbent_artifact_id,
                    round_index=round_index,
                    reason=str(exc),
                )
            )
            last_invalid_reason = str(exc)
            continue
        _require_submission_shape(workspace, manifest_path)
        try:
            auditor.audit_tree(policy_directory).require_safe()
        except PolicySecurityError as exc:
            rounds.append(
                _record_invalid_submission(
                    store,
                    policy_directory=policy_directory,
                    manifest_path=manifest_path,
                    parent_artifact_id=parent_artifact_id,
                    incumbent_artifact_id=incumbent_artifact_id,
                    round_index=round_index,
                    reason=str(exc),
                )
            )
            last_invalid_reason = str(exc)
            continue
        last_invalid_reason = None
        candidate_files = _snapshot_and_reaudit_policy(policy_directory, auditor)
        manifest = load_manifest(manifest_path)
        manifest.validate_for_items(config.prediction_item_ids)
        if manifest.parent_artifact_id != parent_artifact_id:
            raise CampaignError("manifest parent_artifact_id does not match the research parent")
        _validate_claimed_policy_paths(manifest, candidate_files)

        snapshots.append(candidate_files)
        candidate_record = store.put_files(
            candidate_files,
            kind="policy",
            parents=(parent_artifact_id,),
            metadata={"candidate_name": manifest.candidate_name, "round": str(round_index)},
        )
        manifest_record = store.put_text(
            _json_text(manifest.to_dict()),
            kind="research-manifest",
            parents=(candidate_record.artifact_id,),
            metadata={"round": str(round_index)},
        )
        evaluation_workspace = output / "evaluation-workspaces" / f"round-{round_index:02d}"
        evaluation_policy_directory = _materialize_clean_workspace(
            store, candidate_record.artifact_id, evaluation_workspace
        )
        evaluation = evaluator(evaluation_policy_directory, round_index=round_index)
        if not isinstance(evaluation, RoundEvaluation):
            raise TypeError("evaluator callback must return RoundEvaluation")
        if _policy_snapshot(evaluation_policy_directory) != candidate_files:
            raise CampaignError("evaluator modified the candidate snapshot")
        _validate_evaluation_coverage(evaluation, config.prediction_item_ids)
        evaluation_record = store.put_text(
            _json_text(evaluation.to_dict()),
            kind="evaluation",
            parents=(candidate_record.artifact_id,),
            metadata={"round": str(round_index)},
        )

        promoted = incumbent_score is None or evaluation.score > (
            incumbent_score + config.promotion_margin
        )
        prior_incumbent_id = incumbent_artifact_id
        prior_incumbent_score = incumbent_score
        if promoted:
            incumbent_artifact_id = candidate_record.artifact_id
            incumbent_score = evaluation.score
            selected_round = round_index
        if incumbent_artifact_id is None:  # Defensive: the first valid candidate is promoted.
            raise RuntimeError("campaign has no incumbent after evaluation")
        promotion_payload = {
            "candidate_artifact_id": candidate_record.artifact_id,
            "candidate_score": evaluation.score,
            "incumbent_artifact_id_after": incumbent_artifact_id,
            "incumbent_artifact_id_before": prior_incumbent_id,
            "incumbent_score_after": incumbent_score,
            "incumbent_score_before": prior_incumbent_score,
            "promoted": promoted,
            "promotion_margin": config.promotion_margin,
            "researcher_recommendation": manifest.promotion.decision,
            "round_index": round_index,
            "rule": "strict-historical-best",
        }
        promotion_record = store.put_text(
            _json_text(promotion_payload),
            kind="promotion",
            parents=(
                candidate_record.artifact_id,
                manifest_record.artifact_id,
                evaluation_record.artifact_id,
            ),
            metadata={"round": str(round_index)},
        )
        rounds.append(
            ResearchCampaignRound(
                round_index=round_index,
                candidate_name=manifest.candidate_name,
                parent_artifact_id=parent_artifact_id,
                candidate_artifact_id=candidate_record.artifact_id,
                manifest_artifact_id=manifest_record.artifact_id,
                evaluation_artifact_id=evaluation_record.artifact_id,
                promotion_artifact_id=promotion_record.artifact_id,
                score=evaluation.score,
                promoted=promoted,
                incumbent_artifact_id=incumbent_artifact_id,
                researcher_recommendation=manifest.promotion.decision,
            )
        )
        parent_artifact_id = candidate_record.artifact_id
        previous_score = evaluation.score

    valid_rounds = tuple(round_ for round_ in rounds if round_.valid)
    process: CampaignProcessTrace | None
    if h0_score is None and not valid_rounds:
        process = None
    else:
        selected_in_valid: int | None = None
        if selected_round is not None:
            valid_indexes = [round_.round_index for round_ in valid_rounds]
            selected_in_valid = valid_indexes.index(selected_round)
        process = campaign_process_trace(
            h0_score=h0_score,
            round_scores=tuple(round_.score for round_ in valid_rounds),
            selected_round=selected_in_valid,
            snapshots=tuple(snapshots),
        )
    result = ResearchCampaignResult(
        seed_artifact_id=seed_record.artifact_id,
        rounds=tuple(rounds),
        selected_round=selected_round,
        seed_evaluation_artifact_id=seed_evaluation_artifact_id,
        process=process,
    )
    (output / "summary.json").write_text(_json_text(result.to_dict()), encoding="utf-8")
    return result


def _record_invalid_submission(
    store: ArtifactStore,
    *,
    policy_directory: Path,
    manifest_path: Path,
    parent_artifact_id: str,
    incumbent_artifact_id: str | None,
    round_index: int,
    reason: str,
) -> ResearchCampaignRound:
    """Keep an illegal H on the trajectory without calling the frozen reader."""

    rejected_files = _policy_snapshot(policy_directory)
    if manifest_path.is_file():
        manifest = load_manifest(manifest_path)
        candidate_name = manifest.candidate_name
        researcher_recommendation = manifest.promotion.decision
        manifest_payload = manifest.to_dict()
    else:
        candidate_name = f"missing-submission-r{round_index}"
        researcher_recommendation = "hold"
        manifest_payload = {
            "candidate_name": candidate_name,
            "parent_artifact_id": parent_artifact_id,
            "reason": reason,
            "round_index": round_index,
            "status": "missing-manifest",
        }
    candidate_record = store.put_files(
        rejected_files,
        kind="rejected-policy",
        parents=(parent_artifact_id,),
        metadata={"round": str(round_index), "status": "invalid"},
    )
    manifest_record = store.put_text(
        _json_text(manifest_payload),
        kind="research-manifest",
        parents=(candidate_record.artifact_id,),
        metadata={"round": str(round_index), "status": "invalid"},
    )
    evaluation_record = store.put_text(
        _json_text({"reason": reason, "round_index": round_index, "valid": False}),
        kind="invalid-submission",
        parents=(candidate_record.artifact_id,),
        metadata={"round": str(round_index)},
    )
    held_incumbent = incumbent_artifact_id or parent_artifact_id
    promotion_record = store.put_text(
        _json_text(
            {
                "candidate_artifact_id": candidate_record.artifact_id,
                "candidate_score": None,
                "incumbent_artifact_id_after": held_incumbent,
                "incumbent_artifact_id_before": incumbent_artifact_id,
                "promoted": False,
                "reason": reason,
                "round_index": round_index,
                "rule": "invalid-submission-not-selectable",
            }
        ),
        kind="promotion",
        parents=(
            candidate_record.artifact_id,
            manifest_record.artifact_id,
            evaluation_record.artifact_id,
        ),
        metadata={"round": str(round_index)},
    )
    return ResearchCampaignRound(
        round_index=round_index,
        candidate_name=candidate_name,
        parent_artifact_id=parent_artifact_id,
        candidate_artifact_id=candidate_record.artifact_id,
        manifest_artifact_id=manifest_record.artifact_id,
        evaluation_artifact_id=evaluation_record.artifact_id,
        promotion_artifact_id=promotion_record.artifact_id,
        score=0.0,
        promoted=False,
        incumbent_artifact_id=held_incumbent,
        researcher_recommendation=researcher_recommendation,
        valid=False,
        invalid_reason=reason,
    )


def _prepare_output(raw_output: str | Path) -> Path:
    output = Path(raw_output)
    if output.is_symlink():
        raise CampaignError("output directory cannot be a symlink")
    if output.exists():
        if not output.is_dir():
            raise CampaignError("output path must be a directory")
        if any(output.iterdir()):
            raise CampaignError("output directory must be empty")
    else:
        output.mkdir(parents=True)
    return output.resolve()


def _audited_policy_files(root: Path, auditor: PolicyAuditor) -> dict[str, bytes]:
    auditor.audit_tree(root).require_safe()
    return _snapshot_and_reaudit_policy(root, auditor)


def _snapshot_and_reaudit_policy(root: Path, auditor: PolicyAuditor) -> dict[str, bytes]:
    files = _policy_snapshot(root)
    if not files:
        raise CampaignError("candidate policy must contain at least one Python file")
    if len(files) > auditor.capabilities.max_files:
        raise CampaignError("candidate policy exceeds the audited file limit")
    resolved_root = root.resolve(strict=True)
    for bundle_path, content in files.items():
        if len(content) > auditor.capabilities.max_file_bytes:
            raise CampaignError("candidate policy exceeds the audited file-size limit")
        relative = bundle_path.removeprefix("policy/")
        try:
            source = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CampaignError(f"candidate policy is not UTF-8: {relative}") from exc
        auditor.audit_source(source, filename=str(resolved_root / relative)).require_safe()
    return files


def _policy_snapshot(root: Path) -> dict[str, bytes]:
    if root.is_symlink():
        raise CampaignError("policy root cannot be a symlink")
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise CampaignError("policy root does not exist") from exc
    if not resolved_root.is_dir():
        raise CampaignError("policy root must be a directory")
    files: dict[str, bytes] = {}
    for entry in sorted(resolved_root.rglob("*")):
        relative = entry.relative_to(resolved_root)
        if entry.is_symlink():
            raise CampaignError(f"policy snapshot contains a symlink: {relative.as_posix()}")
        if entry.is_dir():
            continue
        if not entry.is_file() or entry.suffix != ".py":
            raise CampaignError(
                f"policy snapshot contains a non-Python file: {relative.as_posix()}"
            )
        files[f"policy/{relative.as_posix()}"] = entry.read_bytes()
    return files


def _materialize_clean_workspace(
    store: ArtifactStore, parent_artifact_id: str, workspace: Path
) -> Path:
    workspace.mkdir(parents=True, exist_ok=False)
    policy_directory = workspace / "policy"
    policy_directory.mkdir()
    for bundle_path, content in store.read_files(parent_artifact_id).items():
        if not bundle_path.startswith("policy/"):
            raise CampaignError("parent policy artifact contains an unexpected bundle path")
        relative = Path(bundle_path.removeprefix("policy/"))
        destination = policy_directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    return policy_directory


def _require_submission_shape(workspace: Path, manifest_path: Path) -> None:
    entries = {entry.name for entry in workspace.iterdir()}
    if entries != {"policy", "manifest.json"}:
        raise CampaignError(f"unexpected workspace entries after research: {sorted(entries)}")
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise CampaignError("manifest.json must be a regular file")


def _validate_claimed_policy_paths(
    manifest: Manifest, candidate_files: Mapping[str, bytes]
) -> None:
    known_paths = set(candidate_files)
    missing = sorted(
        path
        for mechanism in manifest.mechanisms
        for path in mechanism.policy_paths
        if path not in known_paths
    )
    if missing:
        raise CampaignError(f"manifest references missing policy paths: {missing}")


def _validate_evaluation_coverage(
    evaluation: RoundEvaluation, expected_item_ids: tuple[str, ...]
) -> None:
    actual = {item_id for item_id, _ in evaluation.item_scores}
    expected = set(expected_item_ids)
    if actual != expected:
        raise CampaignError(
            "evaluation coverage mismatch; "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )


def _score(value: object, *, field: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise CampaignError(f"{field} must be finite and within [0, 1]")


def _json_text(value: object) -> str:
    return json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n"
