"""Participant registration, the improvement-process protocol, and qualification.

This module defines the benchmark side of the participant boundary: how the
initial agent system ``A_0``, the retainable-state specification ``Sigma``, the
improvement process ``I``, and the model pool ``mu`` register as one
participant ``S = (A_0, Sigma, I, mu)`` (docs/participant-interface-v1.md).

It deliberately does not import the campaign runner, the CLI researcher, or
the security auditor: the campaign surface is callback duck-typed
(``campaign/researcher.py``) and the real adapters are owner-wired at a layer
above this package to avoid import cycles.

Construction-time checks are split by trust: benchmark-owned round inputs
validate fully at construction, while participant-supplied records (state
specs, model pools) validate structure at construction and contract gates at
``qualify_registration`` — a refused registration is an engineering record,
never an exception.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Final, Literal, Protocol, runtime_checkable

from rsicontext.participant.usage import UsageReport

ArmKind = Literal[
    "fixed_strategy",
    "experience_accumulation",
    "open_s_researcher",
    "stateful_control",
]
RegistrationLabel = Literal["external_researcher_assisted", "same_model_self_improvement"]
ALLOWED_ARMS: Final = frozenset(
    {"fixed_strategy", "experience_accumulation", "open_s_researcher", "stateful_control"}
)
ALLOWED_REGISTRATION_LABELS: Final = frozenset(
    {"external_researcher_assisted", "same_model_self_improvement"}
)
FileAudit = Callable[[Path], list[str]]
_SMOKE_FEEDBACK: Final = b"{}"
_SMOKE_TASK_TEXT: Final = "qualification smoke round"


class ParticipantError(ValueError):
    """Raised when a participant object violates its registration contract."""


class EvidenceTier(StrEnum):
    """Evidence-assurance tier of a model pool (contract, reader tiers)."""

    T1_ANCHOR = "t1_anchor"
    T2_VERSIONED_API = "t2_versioned_api"
    T3_COMPATIBILITY = "t3_compatibility"


def canonical_json_bytes(payload: object) -> bytes:
    """Canonical JSON bytes: sorted keys, no whitespace, UTF-8, no NaN.

    Mirrors the fresh-policy JSON protocol (``eval/fresh_policy.py``); kept
    local so this package does not import that module's private helpers.
    """

    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _is_safe_relative_path(raw: object) -> bool:
    if not isinstance(raw, str) or not raw:
        return False
    path = PurePosixPath(raw)
    return not path.is_absolute() and not any(part in {"", ".", ".."} for part in path.parts)


@dataclass(frozen=True, slots=True)
class ImprovementRoundInput:
    """One benchmark-owned improvement round: task, restricted feedback, state.

    ``restricted_feedback_bytes`` carries the frozen F-schema feedback — the
    only feedback channel an improver may consume. ``state_path`` is where the
    current retained state is loaded from (None before the first round or for
    a stateless arm). ``task_order_seed`` is the controlled task-order seed of
    the round's stream: order is a controlled input, not a nuisance.
    """

    round_index: int
    task_text: str
    restricted_feedback_bytes: bytes
    current_agent_dir: Path
    state_path: Path | None
    remaining_slots: int
    task_order_seed: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.round_index, int)
            or isinstance(self.round_index, bool)
            or self.round_index < 0
        ):
            raise ParticipantError("round_index must be a non-negative integer")
        if not isinstance(self.task_text, str):
            raise ParticipantError("task_text must be a string")
        if not isinstance(self.restricted_feedback_bytes, bytes):
            raise ParticipantError("restricted_feedback_bytes must be bytes")
        if not isinstance(self.current_agent_dir, Path):
            raise ParticipantError("current_agent_dir must be a Path")
        if self.state_path is not None and not isinstance(self.state_path, Path):
            raise ParticipantError("state_path must be a Path or None")
        if (
            not isinstance(self.remaining_slots, int)
            or isinstance(self.remaining_slots, bool)
            or self.remaining_slots < 0
        ):
            raise ParticipantError("remaining_slots must be a non-negative integer")
        if not isinstance(self.task_order_seed, int) or isinstance(self.task_order_seed, bool):
            raise ParticipantError("task_order_seed must be an integer")

    def canonical_bytes(self) -> bytes:
        """Deterministic recording of the round's stream content.

        Filesystem locations (``current_agent_dir``, ``state_path``) are
        excluded on purpose: they are run-record fields, so recorded stream
        bytes stay comparable across arms, seeds, and machines.
        """

        return canonical_json_bytes(
            {
                "remaining_slots": self.remaining_slots,
                "restricted_feedback_b64": base64.b64encode(self.restricted_feedback_bytes).decode(
                    "ascii"
                ),
                "round_index": self.round_index,
                "task_order_seed": self.task_order_seed,
                "task_text": self.task_text,
            }
        )


@dataclass(frozen=True, slots=True)
class ImprovementRoundOutput:
    """What one improvement round produced: file changes, state, usage.

    ``agent_files_changed`` maps safe relative paths under the agent directory
    to complete new file text; omitted files stay as the parent (merge
    semantics, matching the API researcher protocol). ``state_update`` is the
    complete new state bytes, or None when the arm declares no state change.
    """

    agent_files_changed: Mapping[str, str]
    state_update: bytes | None
    usage: UsageReport

    def __post_init__(self) -> None:
        if not isinstance(self.agent_files_changed, Mapping):
            raise ParticipantError("agent_files_changed must be a Mapping")
        for path, content in self.agent_files_changed.items():
            if not _is_safe_relative_path(path):
                raise ParticipantError(
                    f"agent_files_changed key is not a safe relative path: {path!r}"
                )
            if not isinstance(content, str):
                raise ParticipantError(f"agent_files_changed content must be a string: {path!r}")
        if self.state_update is not None and not isinstance(self.state_update, bytes):
            raise ParticipantError("state_update must be bytes or None")
        if not isinstance(self.usage, UsageReport):
            raise ParticipantError("usage must be a UsageReport")


@runtime_checkable
class ImprovementProcess(Protocol):
    """The participant-supplied improvement loop ``I``.

    Implementations are untrusted code: they receive one round input and
    return one round output, and they must not write the agent directory or
    the state store directly — the harness applies outputs. The production
    open-S bridge over ``campaign/researcher.py`` is owner-wired, so nothing
    here imports campaign modules.
    """

    def improve(self, round_input: ImprovementRoundInput) -> ImprovementRoundOutput: ...


@dataclass(frozen=True, slots=True)
class StateSpec:
    """Declared retainable-state schema ``Sigma`` plus its byte cap.

    ``digest`` is the sha256 of the canonical sorted-key JSON of the schema —
    the manifest's ``state_schema`` field. The byte cap is enforced at the
    serialization boundary by the harness and by registration qualification,
    never by trust.
    """

    schema: Mapping[str, object]
    byte_cap: int
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.schema, Mapping):
            raise ParticipantError("state schema must be a Mapping")
        if any(not isinstance(key, str) for key in self.schema):
            raise ParticipantError("state schema keys must be strings")
        if not isinstance(self.byte_cap, int) or isinstance(self.byte_cap, bool):
            raise ParticipantError("byte_cap must be an integer")
        try:
            canonical = canonical_json_bytes(dict(self.schema))
        except (TypeError, ValueError) as exc:
            raise ParticipantError("state schema is not canonically JSON-serializable") from exc
        object.__setattr__(self, "digest", hashlib.sha256(canonical).hexdigest())


@dataclass(frozen=True, slots=True)
class ModelPool:
    """The serving configuration ``mu``: one pool, fixed at registration.

    Structural checks run at construction; the tier gates (T2 requires a
    non-null access window and a version string per model) are refused at
    qualification, per the contract's reader-tier rules. Deep T2 gates
    (canaries, variance floor, echo) live in the cost-ledger workstream.
    """

    pool_id: str
    tier: EvidenceTier
    models: tuple[str, ...]
    version_strings: Mapping[str, str]
    access_window: tuple[str, str] | None

    def __post_init__(self) -> None:
        if not isinstance(self.pool_id, str) or not self.pool_id.strip():
            raise ParticipantError("pool_id must be a non-empty string")
        if not isinstance(self.tier, EvidenceTier):
            raise ParticipantError("tier must be an EvidenceTier")
        if (
            not isinstance(self.models, tuple)
            or not self.models
            or any(not isinstance(model, str) or not model.strip() for model in self.models)
        ):
            raise ParticipantError("models must be a non-empty tuple of non-empty strings")
        if len(self.models) != len(set(self.models)):
            raise ParticipantError("models must be unique")
        if not isinstance(self.version_strings, Mapping):
            raise ParticipantError("version_strings must be a Mapping")
        known = set(self.models)
        for model, version in self.version_strings.items():
            if model not in known:
                raise ParticipantError(f"version_strings names an unregistered model: {model!r}")
            if not isinstance(version, str) or not version.strip():
                raise ParticipantError(f"version string for {model!r} must be a non-empty string")
        if self.access_window is not None:
            if (
                not isinstance(self.access_window, tuple)
                or len(self.access_window) != 2
                or any(
                    not isinstance(bound, str) or not bound.strip() for bound in self.access_window
                )
            ):
                raise ParticipantError(
                    "access_window must be a (start, end) pair of non-empty strings"
                )
            if self.access_window[0] > self.access_window[1]:
                raise ParticipantError("access_window start must not be after its end")


@dataclass(frozen=True, slots=True)
class Registration:
    """One registered participant ``S = (A_0, Sigma, I, mu)`` plus run controls.

    ``seed_id`` identifies the research seed of the reported cell (the
    contract makes multi-seed mandatory and seed IDs manifest fields); the
    task-order seed travels per round input instead. ``registration_label``
    separates external-researcher-assisted from same-model self-improvement;
    the two are recorded distinctly and never pooled.
    """

    participant_id: str
    arm: ArmKind
    agent_dir: Path
    state_spec: StateSpec
    improver: ImprovementProcess
    pool: ModelPool
    registration_label: RegistrationLabel
    seed_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.participant_id, str) or not self.participant_id.strip():
            raise ParticipantError("participant_id must be a non-empty string")
        if not isinstance(self.arm, str) or self.arm not in ALLOWED_ARMS:
            raise ParticipantError(f"unsupported arm: {self.arm!r}")
        if not isinstance(self.agent_dir, Path):
            raise ParticipantError("agent_dir must be a Path")
        if not isinstance(self.state_spec, StateSpec):
            raise ParticipantError("state_spec must be a StateSpec")
        if not isinstance(self.improver, ImprovementProcess):
            raise ParticipantError("improver must implement the ImprovementProcess protocol")
        if not isinstance(self.pool, ModelPool):
            raise ParticipantError("pool must be a ModelPool")
        if (
            not isinstance(self.registration_label, str)
            or self.registration_label not in ALLOWED_REGISTRATION_LABELS
        ):
            raise ParticipantError(f"unsupported registration_label: {self.registration_label!r}")
        if not isinstance(self.seed_id, str) or not self.seed_id.strip():
            raise ParticipantError("seed_id must be a non-empty string")

    def to_dict(self) -> dict[str, object]:
        """Manifest-layer record for this registration (interface, manifest extensions)."""

        return {
            "participant_id": self.participant_id,
            "arm": self.arm,
            "seed_id": self.seed_id,
            "state_schema": self.state_spec.digest,
            "pool_tier": self.pool.tier.value,
            "registration_label": self.registration_label,
        }


@dataclass(frozen=True, slots=True)
class QualificationResult:
    """Engineering record of one registration qualification attempt."""

    participant_id: str
    passed: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def qualify_registration(registration: Registration, audit_file: FileAudit) -> QualificationResult:
    """Run the registration qualification gates and report every failure.

    A gate that raises internally is captured as a reason, so a failed
    qualification is always an engineering record rather than an exception
    (contract, honesty constraints). Checks: (i) the injected audit hook over
    every agent file, (ii) state-spec sanity, (iii) the pool tier contract,
    (iv) a synthetic smoke round through the improver.
    """

    reasons: list[str] = []
    reasons.extend(_audit_agent_files(registration, audit_file))
    reasons.extend(_check_state_spec(registration.state_spec))
    reasons.extend(_check_pool_tier(registration.pool))
    reasons.extend(_smoke_improver(registration))
    return QualificationResult(
        participant_id=registration.participant_id,
        passed=not reasons,
        reasons=tuple(reasons),
    )


def _audit_agent_files(registration: Registration, audit_file: FileAudit) -> list[str]:
    agent_dir = registration.agent_dir
    if not agent_dir.is_dir():
        return [f"agent_dir is not a directory: {agent_dir}"]
    reasons: list[str] = []
    try:
        entries = sorted(agent_dir.rglob("*"))
    except OSError as exc:
        return [f"agent file audit walk failed: {exc}"]
    for path in entries:
        relative = path.relative_to(agent_dir).as_posix()
        if path.is_symlink():
            reasons.append(f"agent tree contains a symlink: {relative}")
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            reasons.append(f"agent tree contains a non-regular file: {relative}")
            continue
        try:
            findings = list(audit_file(path))
        except Exception as exc:
            reasons.append(f"audit_file raised {type(exc).__name__} on {relative}: {exc}")
            continue
        reasons.extend(f"agent file audit: {relative}: {finding}" for finding in findings)
    return reasons


def _check_state_spec(spec: StateSpec) -> list[str]:
    reasons: list[str] = []
    if spec.byte_cap <= 0:
        reasons.append("state spec byte_cap must be a positive integer")
    try:
        canonical_json_bytes(dict(spec.schema))
    except (TypeError, ValueError):
        reasons.append("state schema is not canonically JSON-serializable")
    return reasons


def _check_pool_tier(pool: ModelPool) -> list[str]:
    reasons: list[str] = []
    if pool.tier is EvidenceTier.T2_VERSIONED_API:
        if pool.access_window is None:
            reasons.append("t2 model pool requires a non-null access window")
        missing = [model for model in pool.models if model not in pool.version_strings]
        if missing:
            reasons.append(
                "t2 model pool requires a version string per model: " + ", ".join(sorted(missing))
            )
    return reasons


def _smoke_improver(registration: Registration) -> list[str]:
    smoke_input = ImprovementRoundInput(
        round_index=0,
        task_text=_SMOKE_TASK_TEXT,
        restricted_feedback_bytes=_SMOKE_FEEDBACK,
        current_agent_dir=registration.agent_dir,
        state_path=None,
        remaining_slots=1,
        task_order_seed=0,
    )
    try:
        output = registration.improver.improve(smoke_input)
    except Exception as exc:
        return [f"improver smoke round raised {type(exc).__name__}: {exc}"]
    if not isinstance(output, ImprovementRoundOutput):
        return ["improver smoke round did not return an ImprovementRoundOutput"]
    reasons: list[str] = []
    if output.state_update is not None:
        if len(output.state_update) > registration.state_spec.byte_cap:
            reasons.append(
                "improver smoke state_update exceeds the declared byte cap: "
                f"{len(output.state_update)} > {registration.state_spec.byte_cap}"
            )
        try:
            json.loads(output.state_update)
        except (json.JSONDecodeError, UnicodeDecodeError):
            reasons.append("improver smoke state_update is not valid JSON")
    return reasons
