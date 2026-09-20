"""Participant registration, improvement arms, and usage accounting.

The v2 benchmark contract's participant surface: a registered participant is
``S = (A_0, Sigma, I, mu)`` (docs/participant-interface-v1.md). This package
sits beside ``campaign/`` without importing it — the runner remains
callback-duck-typed and the production open-S bridge is owner-wired.
"""

from rsicontext.participant.arms import (
    ArmError,
    ExperienceAccumulationImprover,
    FixedStrategyImprover,
    OpenSClIResearcherImprover,
)
from rsicontext.participant.recuris_arm import RecurisStyleImprover
from rsicontext.participant.registration import (
    ALLOWED_ARMS,
    ALLOWED_REGISTRATION_LABELS,
    ArmKind,
    EvidenceTier,
    FileAudit,
    ImprovementProcess,
    ImprovementRoundInput,
    ImprovementRoundOutput,
    ModelPool,
    ParticipantError,
    QualificationResult,
    Registration,
    RegistrationLabel,
    StateSpec,
    canonical_json_bytes,
    qualify_registration,
)
from rsicontext.participant.usage import UsageLedger, UsageReport

__all__ = [
    "ALLOWED_ARMS",
    "ALLOWED_REGISTRATION_LABELS",
    "ArmError",
    "ArmKind",
    "EvidenceTier",
    "ExperienceAccumulationImprover",
    "FileAudit",
    "FixedStrategyImprover",
    "ImprovementProcess",
    "ImprovementRoundInput",
    "ImprovementRoundOutput",
    "ModelPool",
    "OpenSClIResearcherImprover",
    "ParticipantError",
    "QualificationResult",
    "RecurisStyleImprover",
    "Registration",
    "RegistrationLabel",
    "StateSpec",
    "UsageLedger",
    "UsageReport",
    "canonical_json_bytes",
    "qualify_registration",
]
