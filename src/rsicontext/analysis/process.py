"""Round-to-round H diffs for RSI process curves.

Scores include H0 when a seed evaluation exists. Historical-best selection is
separate from the last-attempt parent used for the next edit.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from rsicontext.analysis.metrics import trajectory_metrics
from rsicontext.artifacts import ArtifactStore

_DOCSTRING = re.compile(r'\A\s*"""(.*?)"""', re.DOTALL)


@dataclass(frozen=True, slots=True)
class RoundPolicyDiff:
    round_index: int
    policy_sha256: str
    parent_sha256: str
    changed_paths: tuple[str, ...]
    headline: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CampaignProcessTrace:
    h0_score: float | None
    scores: tuple[float, ...]
    selected_round: int | None
    selected_score: float | None
    first_score: float
    peak_score: float
    last_score: float
    peak_round: int
    discovery_gain: float
    last_minus_peak: float
    post_peak_regression: bool
    round_diffs: tuple[RoundPolicyDiff, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["round_diffs"] = [diff.to_dict() for diff in self.round_diffs]
        return payload


def policy_digest(files: Mapping[str, bytes]) -> str:
    hasher = hashlib.sha256()
    for path in sorted(files):
        hasher.update(path.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(files[path])
        hasher.update(b"\0")
    return hasher.hexdigest()


def changed_paths(parent: Mapping[str, bytes], child: Mapping[str, bytes]) -> tuple[str, ...]:
    keys = sorted(set(parent) | set(child))
    return tuple(path for path in keys if parent.get(path) != child.get(path))


def policy_headline(files: Mapping[str, bytes]) -> str:
    blob = files.get("policy/policy.py")
    if blob is None:
        blob = files[sorted(files)[0]]
    text = blob.decode("utf-8")
    match = _DOCSTRING.match(text)
    if match is not None:
        first = match.group(1).strip().splitlines()[0].strip()
        if first:
            return first[:160]
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:160]
    return ""


def campaign_process_trace(
    *,
    h0_score: float | None,
    round_scores: Sequence[float],
    selected_round: int | None,
    snapshots: Sequence[Mapping[str, bytes]],
) -> CampaignProcessTrace:
    """Build the RSI process curve from H0 plus each submitted policy snapshot."""

    if len(snapshots) != len(round_scores) + 1:
        raise ValueError("snapshots must be seed plus one mapping per round")
    if selected_round is not None and not 0 <= selected_round < len(round_scores):
        raise ValueError("selected_round must index a completed round or be null")
    if not round_scores:
        if h0_score is None:
            raise ValueError("at least one round score is required")
        h0_only = (float(h0_score),)
        metrics = trajectory_metrics(h0_only)
        return CampaignProcessTrace(
            h0_score=float(h0_score),
            scores=h0_only,
            selected_round=None,
            selected_score=float(h0_score),
            first_score=metrics.first_score,
            peak_score=metrics.peak_score,
            last_score=metrics.last_score,
            peak_round=metrics.peak_round,
            discovery_gain=metrics.discovery_gain,
            last_minus_peak=metrics.last_minus_peak,
            post_peak_regression=metrics.post_peak_regression,
            round_diffs=(),
        )

    scores: tuple[float, ...] = ((float(h0_score),) if h0_score is not None else ()) + tuple(
        float(score) for score in round_scores
    )
    metrics = trajectory_metrics(scores)
    if selected_round is None:
        selected_score = None if h0_score is None else float(h0_score)
    else:
        selected_score = float(round_scores[selected_round])

    diffs: list[RoundPolicyDiff] = []
    for index, child in enumerate(snapshots[1:]):
        parent = snapshots[index]
        diffs.append(
            RoundPolicyDiff(
                round_index=index,
                policy_sha256=policy_digest(child),
                parent_sha256=policy_digest(parent),
                changed_paths=changed_paths(parent, child),
                headline=policy_headline(child),
            )
        )
    return CampaignProcessTrace(
        h0_score=None if h0_score is None else float(h0_score),
        scores=scores,
        selected_round=selected_round,
        selected_score=selected_score,
        first_score=metrics.first_score,
        peak_score=metrics.peak_score,
        last_score=metrics.last_score,
        peak_round=metrics.peak_round,
        discovery_gain=metrics.discovery_gain,
        last_minus_peak=metrics.last_minus_peak,
        post_peak_regression=metrics.post_peak_regression,
        round_diffs=tuple(diffs),
    )


def process_from_campaign_directory(output: str | Path) -> CampaignProcessTrace:
    """Reconstruct a process trace from an existing campaign store."""

    root = Path(output)
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    store = ArtifactStore(root / "store")
    snapshots: list[dict[str, bytes]] = [store.read_files(summary["seed_artifact_id"])]
    h0_score: float | None = None
    seed_eval_id = summary.get("seed_evaluation_artifact_id")
    if seed_eval_id:
        payload = json.loads(store.read_text(seed_eval_id))
        h0_score = float(payload["score"])
    round_scores: list[float] = []
    valid_indexes: list[int] = []
    for round_row in summary["rounds"]:
        if round_row.get("valid", True) is False:
            continue
        snapshots.append(store.read_files(round_row["candidate_artifact_id"]))
        round_scores.append(float(round_row["score"]))
        valid_indexes.append(int(round_row["round_index"]))
    selected = summary["selected_round"]
    selected_in_valid = None if selected is None else valid_indexes.index(selected)
    return campaign_process_trace(
        h0_score=h0_score,
        round_scores=tuple(round_scores),
        selected_round=selected_in_valid,
        snapshots=tuple(snapshots),
    )
