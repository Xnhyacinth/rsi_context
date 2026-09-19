"""Owner-wired bridge: participant arms over the real campaign harness.

Contract status: implements participant-interface-v1.md §Implementation
anchors (frozen 2026-09-19) — the open-S arm's ``run_round`` callable is
realized over ``campaign/researcher.py``'s duck-typed
``ResearcherCallback`` surface. This module lives in
``participant/`` but is the ONE place allowed to import campaign
machinery: it adapts ``ImprovementRoundInput`` into a
``ResearchRoundRequest``-shaped call and reads the resulting
workspace/manifest back as changed agent files.

The campaign runner owns the loop, workspace materialization, and
invalid-submission accounting (campaign/researcher.py:249-300); the
participant protocol owns registration, state, and usage accounting
(participant-interface §arms). The bridge composes them without modifying
either: the callback is executed against a round request built here, and
the changed-file map is derived by comparing the post-round policy tree
against its pre-round bytes.

Usage accounting for the open-S arm is supplied by the caller (the
researcher streams' TokenUsage events are consumed by the campaign layer;
the bridge accepts an injected ``usage_report`` hook mirroring
``OpenSClIResearcherImprover.usage_report``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from rsicontext.participant.arms import OpenSClIResearcherImprover
from rsicontext.participant.registration import (
    ImprovementRoundInput,
    ImprovementRoundOutput,
)
from rsicontext.participant.usage import UsageReport

RoundRunner = Callable[[ImprovementRoundInput], dict[str, str]]


class CampaignBridgeError(RuntimeError):
    """Raised when the campaign↔participant bridge cannot adapt a round."""


@dataclass(frozen=True, slots=True)
class _CampaignRequestShape:
    """The subset of ResearchRoundRequest fields the bridge constructs.

    The real dataclass is frozen and validated by the campaign runner; the
    bridge builds the keyword set the runner's callback consumes, verified
    by tests against the live import.
    """

    round_index: int
    workspace: Path
    policy_directory: Path
    manifest_path: Path
    previous_score: float | None
    incumbent_score: float | None
    prediction_item_ids: tuple[str, ...]
    last_invalid_reason: str | None


def _policy_tree_files(policy_directory: Path) -> dict[str, bytes]:
    """Snapshot the policy tree (relative path → bytes) for change detection."""

    snapshot: dict[str, bytes] = {}
    for path in sorted(policy_directory.rglob("*.py")):
        relative = path.relative_to(policy_directory).as_posix()
        snapshot[relative] = path.read_bytes()
    return snapshot


def make_campaign_run_round(
    callback: Callable[[object], None],
    workspace_root: Path,
    *,
    prediction_item_ids: tuple[str, ...],
    feedback_bytes_to_scores: Callable[[bytes], tuple[float | None, float | None]],
    last_invalid_reason: str | None = None,
    usage_report: Callable[[], UsageReport] | None = None,
) -> RoundRunner:
    """Build the ``run_round`` callable that adapts a round to the callback.

    ``callback`` is any ``ResearcherCallback``-compatible callable (it
    receives the round request and performs its side effects on the
    workspace). ``feedback_bytes_to_scores`` converts the participant
    layer's restricted feedback bytes into the (previous, incumbent)
    score view the campaign prompt exposes — the participant layer keeps
    its own F-schema, the bridge only adapts the numeric view.
    """

    def run_round(round_input: ImprovementRoundInput) -> dict[str, str]:
        workspace = workspace_root / f"round-{round_input.round_index:02d}"
        policy_directory = workspace / "policy"
        policy_directory.mkdir(parents=True, exist_ok=True)
        manifest_path = workspace / "manifest.json"

        # Seed the workspace from the participant's current agent dir so
        # the callback edits the participant's tree, not an empty one.
        before = _seed_workspace(policy_directory, round_input.current_agent_dir)

        previous_score, incumbent_score = feedback_bytes_to_scores(
            round_input.restricted_feedback_bytes
        )
        request = _CampaignRequestShape(
            round_index=round_input.round_index,
            workspace=workspace,
            policy_directory=policy_directory,
            manifest_path=manifest_path,
            previous_score=previous_score,
            incumbent_score=incumbent_score,
            prediction_item_ids=prediction_item_ids,
            last_invalid_reason=last_invalid_reason,
        )
        try:
            callback(request)
        except TypeError as exc:
            raise CampaignBridgeError(
                f"campaign callback rejected the bridged request: {exc}"
            ) from exc

        after = _policy_tree_files(policy_directory)
        changed: dict[str, str] = {}
        for relative, content in after.items():
            if before.get(relative) != content:
                changed[relative] = content.decode("utf-8")
        return changed

    return run_round


def _seed_workspace(policy_directory: Path, agent_dir: Path) -> dict[str, bytes]:
    """Copy the agent tree into the workspace policy dir; return the snapshot."""

    if not agent_dir.is_dir():
        raise CampaignBridgeError(f"agent directory does not exist: {agent_dir}")
    snapshot: dict[str, bytes] = {}
    for path in sorted(agent_dir.rglob("*.py")):
        relative = path.relative_to(agent_dir).as_posix()
        destination = policy_directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(path.read_bytes())
        snapshot[relative] = path.read_bytes()
    return snapshot


def build_open_s_arm(
    callback: Callable[[object], None],
    workspace_root: Path,
    *,
    prediction_item_ids: tuple[str, ...],
    feedback_bytes_to_scores: Callable[[bytes], tuple[float | None, float | None]],
    usage_report: Callable[[], UsageReport] | None = None,
    last_invalid_reason: str | None = None,
) -> OpenSClIResearcherImprover:
    """Assemble the open-S CLI arm over the real campaign callback surface."""

    run_round = make_campaign_run_round(
        callback,
        workspace_root,
        prediction_item_ids=prediction_item_ids,
        feedback_bytes_to_scores=feedback_bytes_to_scores,
        last_invalid_reason=last_invalid_reason,
        usage_report=usage_report,
    )
    return OpenSClIResearcherImprover(run_round=run_round, usage_report=usage_report)


__all__ = [
    "CampaignBridgeError",
    "ImprovementRoundOutput",
    "RoundRunner",
    "build_open_s_arm",
    "make_campaign_run_round",
]
