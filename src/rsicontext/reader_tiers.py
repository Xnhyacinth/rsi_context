"""Reader evidence-tier gates (benchmark contract v2, "Reader evidence tiers").

Classifies readers (and any model pool an S may schedule) by evidence
assurance — T1 anchor, T2 versioned API, T3 compatibility-only — and
enforces the T2 gates the hy3 record documented: pre/post canaries on
answer form, usage, and returned-model echo; a same-policy in-batch
score-variance floor from at least 5 repeats; version + access window +
echo recorded per artifact; and a pre-registered variance ceiling above
which the reader is rejected for that block.

T1 here keys off a single sentinel ``local_anchor`` attestation flag; the
full anchor manifest (weights pin, serving-profile hash, thinking flag,
tokenizer manifest) lives with the runtime attestation machinery, not in
this gate module.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "GateEvidence",
    "ReaderTier",
    "TierDecision",
    "check_rejection_ceiling",
    "evaluate_tier",
    "profile_tier",
]


class ReaderTier(StrEnum):
    """Reader evidence tier (contract v2; participant registration mirror).

    NOTE: participant registration semantics (participant-interface-v1.md
    "Reader tiers in registration") are owned by the participant
    workstream; this enum deliberately duplicates that shape without
    importing it. The owner reconciles the two once the participant
    package lands.
    """

    T1_ANCHOR = "t1_anchor"
    T2_VERSIONED_API = "t2_versioned_api"
    T3_COMPATIBILITY_ONLY = "t3_compatibility_only"


@dataclass(frozen=True, slots=True)
class GateEvidence:
    """Gate inputs gathered per artifact (canary + variance + identity)."""

    canary_answer_form_ok: bool
    canary_usage_ok: bool
    canary_model_echo_ok: bool
    canary_timestamp: str
    variance_floor_value: float | None
    variance_repeats: int
    version_string: str | None
    access_window: tuple[str, str] | None
    model_echo_recorded: bool
    local_anchor: bool = False

    def __post_init__(self) -> None:
        for field_name, value in (
            ("canary_answer_form_ok", self.canary_answer_form_ok),
            ("canary_usage_ok", self.canary_usage_ok),
            ("canary_model_echo_ok", self.canary_model_echo_ok),
            ("local_anchor", self.local_anchor),
        ):
            if not isinstance(value, bool):
                raise TypeError(f"{field_name} must be a boolean")
        if not isinstance(self.canary_timestamp, str) or not self.canary_timestamp.strip():
            raise ValueError("canary_timestamp must be a non-empty string")
        if self.variance_floor_value is not None and (
            isinstance(self.variance_floor_value, bool)
            or not isinstance(self.variance_floor_value, (int, float))
            or not math.isfinite(float(self.variance_floor_value))
            or float(self.variance_floor_value) < 0
        ):
            raise ValueError("variance_floor_value must be a finite non-negative number")
        if (
            not isinstance(self.variance_repeats, int)
            or isinstance(self.variance_repeats, bool)
            or self.variance_repeats < 0
        ):
            raise ValueError("variance_repeats must be a non-negative integer")
        if self.version_string is not None and (
            not isinstance(self.version_string, str) or not self.version_string.strip()
        ):
            raise ValueError("version_string must be a non-empty string or null")
        if self.access_window is not None and (
            not isinstance(self.access_window, tuple)
            or len(self.access_window) != 2
            or any(not isinstance(bound, str) or not bound.strip() for bound in self.access_window)
        ):
            raise ValueError("access_window must be a pair of non-empty strings or null")
        if not isinstance(self.model_echo_recorded, bool):
            raise TypeError("model_echo_recorded must be a boolean")


@dataclass(frozen=True, slots=True)
class TierDecision:
    """Outcome of one tier evaluation: tier, efficiency eligibility, reasons."""

    tier: ReaderTier
    eligible_for_efficiency: bool
    reasons: tuple[str, ...]
    batch_invalidating: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.tier, ReaderTier):
            raise TypeError("tier must be a ReaderTier value")
        if not isinstance(self.eligible_for_efficiency, bool):
            raise TypeError("eligible_for_efficiency must be a boolean")
        if not isinstance(self.batch_invalidating, bool):
            raise TypeError("batch_invalidating must be a boolean")
        if any(not isinstance(reason, str) or not reason for reason in self.reasons):
            raise ValueError("reasons must be non-empty strings")


MIN_VARIANCE_REPEATS = 5


def evaluate_tier(evidence: GateEvidence) -> TierDecision:
    """Apply the T2 gates; T1 requires the local-anchor attestation flag."""

    if not isinstance(evidence, GateEvidence):
        raise TypeError("evidence must be a GateEvidence value")
    if evidence.local_anchor:
        return TierDecision(
            tier=ReaderTier.T1_ANCHOR,
            eligible_for_efficiency=True,
            reasons=("local anchor attestation present",),
        )
    canary_ok = (
        evidence.canary_answer_form_ok
        and evidence.canary_usage_ok
        and evidence.canary_model_echo_ok
    )
    reasons: list[str] = []
    if not canary_ok:
        for name, ok in (
            ("answer form", evidence.canary_answer_form_ok),
            ("usage", evidence.canary_usage_ok),
            ("model echo", evidence.canary_model_echo_ok),
        ):
            if not ok:
                reasons.append(f"canary drift: {name} check failed")
    if evidence.variance_floor_value is None:
        reasons.append("variance floor not measured")
    elif evidence.variance_repeats < MIN_VARIANCE_REPEATS:
        reasons.append(
            f"variance floor repeats {evidence.variance_repeats} below {MIN_VARIANCE_REPEATS}"
        )
    if evidence.version_string is None:
        reasons.append("version string not recorded")
    if evidence.access_window is None:
        reasons.append("access window not recorded")
    if not evidence.model_echo_recorded:
        reasons.append("model echo not recorded")
    if reasons:
        return TierDecision(
            tier=ReaderTier.T3_COMPATIBILITY_ONLY,
            eligible_for_efficiency=False,
            reasons=tuple(reasons),
            batch_invalidating=not canary_ok,
        )
    return TierDecision(
        tier=ReaderTier.T2_VERSIONED_API,
        eligible_for_efficiency=True,
        reasons=("all T2 gates passed",),
    )


def check_rejection_ceiling(
    observed_variance: float,
    ceiling: float,
    evidence: GateEvidence,
) -> TierDecision:
    """Enforce the pre-registered in-batch variance ceiling for one block.

    Variance above the ceiling rejects the reader for that block: the tier
    drops to T3 with an explicit rejection reason, regardless of how the
    other gates evaluated.
    """

    if not isinstance(evidence, GateEvidence):
        raise TypeError("evidence must be a GateEvidence value")
    for field, value in (("observed_variance", observed_variance), ("ceiling", ceiling)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{field} must be numeric")
        if not math.isfinite(float(value)) or float(value) < 0:
            raise ValueError(f"{field} must be finite and non-negative")
    if float(observed_variance) > float(ceiling):
        return TierDecision(
            tier=ReaderTier.T3_COMPATIBILITY_ONLY,
            eligible_for_efficiency=False,
            reasons=(
                f"observed variance {float(observed_variance):g} exceeds "
                f"pre-registered ceiling {float(ceiling):g}",
            ),
            batch_invalidating=False,
        )
    return evaluate_tier(evidence)


def profile_tier(profile: Mapping[str, object]) -> ReaderTier:
    """Classify an api_profiles.json-shaped dict; pure, no file I/O.

    A profile dict alone cannot express T2 eligibility: the T2 gates
    (canaries, >=5-repeat variance floor, echo recording) are runtime
    evidence, not profile fields. The profile can only disqualify: a
    missing (null) provider revision or an absent access window means the
    version pinning T2 requires is not even declared, so the profile maps
    to T3. T1 detection likewise needs the anchor attestation, not the
    dict; a local host alone does not prove it. A profile with a pinned
    provider_revision is therefore at best T2-eligible *pending gates* --
    callers must combine it with evaluate_tier() evidence; the returned
    tier here is the evidence-floor, not the gate verdict.
    """

    if not isinstance(profile, Mapping):
        raise TypeError("profile must be a mapping")
    revision = profile.get("provider_revision")
    if revision is None:
        return ReaderTier.T3_COMPATIBILITY_ONLY
    if not isinstance(revision, str) or not revision.strip():
        return ReaderTier.T3_COMPATIBILITY_ONLY
    return ReaderTier.T2_VERSIONED_API
