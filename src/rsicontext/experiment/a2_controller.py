"""A2 launch gate: refuse execution until landscape and isolation pass."""

from __future__ import annotations

from dataclasses import dataclass

from rsicontext.experiment.a2 import A2PilotPlan
from rsicontext.experiment.ledger import SpendCaps, SpendLedger


class A2LaunchError(RuntimeError):
    """Raised when the pre-registered A2 factorial may not start."""


@dataclass(frozen=True, slots=True)
class A2LaunchRequest:
    plan: A2PilotPlan
    caps: SpendCaps
    landscape_passed: bool
    isolation_formal: bool
    difficulty_profiles_passed: tuple[str, ...]


def launch_a2_pilot(request: A2LaunchRequest) -> SpendLedger:
    """Authorize spend caps but never start the factorial from this host path.

    The returned ledger is unused unless every scientific gate is already true.
    """

    if not isinstance(request, A2LaunchRequest):
        raise TypeError("request must be an A2LaunchRequest")
    if not isinstance(request.plan, A2PilotPlan):
        raise TypeError("plan must be an A2PilotPlan")
    if request.plan.qualification_only:
        raise A2LaunchError("the pre-registered plan is still qualification-only")
    if not request.landscape_passed:
        raise A2LaunchError(
            "A2 is blocked until both primary profiles pass the disposable landscape"
        )
    required = frozenset(request.plan.task_profiles)
    if frozenset(request.difficulty_profiles_passed) != required:
        raise A2LaunchError("difficulty assessment has not passed every A2 task profile")
    if not request.isolation_formal:
        raise A2LaunchError("formal gate scoring requires attested physical isolation")
    raise A2LaunchError("A2 execution is not enabled in this workspace")
