"""The first control arms as ``ImprovementProcess`` implementations.

Fairness rules (docs/participant-interface-v1.md, the three first arms): all
arms face the identical task stream, the identical restricted-feedback bytes,
the identical resource envelope and split boundaries. The fixed-strategy arm
never changes strategy or state; the experience-accumulation arm keeps
strategy code byte-frozen and lets only state content grow; the open-S arm
delegates to the existing researcher harness through an injected callable.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from rsicontext.participant.registration import (
    ImprovementRoundInput,
    ImprovementRoundOutput,
)
from rsicontext.participant.usage import UsageReport

RoundRunner = Callable[[ImprovementRoundInput], Mapping[str, str]]
_FIXED_USAGE = UsageReport()
_NOTE_KEY_PREFIX = "note_"


class ArmError(ValueError):
    """Raised when an arm violates its frozen control contract."""


@dataclass(frozen=True, slots=True)
class FixedStrategyImprover:
    """Fixed-strategy reference arm: the "is updating worth it" denominator.

    No-op by construction: no file changes, no state update, zero accounted
    improvement usage. Strategy bytes are frozen by construction — a no-op
    improver cannot emit a file change.
    """

    def improve(self, round_input: ImprovementRoundInput) -> ImprovementRoundOutput:
        return ImprovementRoundOutput(
            agent_files_changed={},
            state_update=None,
            usage=_FIXED_USAGE,
        )


@dataclass(frozen=True, slots=True)
class ExperienceAccumulationImprover:
    """Experience-accumulation-only arm: state growth, strategy byte-frozen.

    Agent files are never changed (empty ``agent_files_changed``); each round
    appends one canonical note entry, distilled from the restricted feedback,
    to the accumulated state. State-only growth isolates experience content
    from strategy updates, per the interface's key decomposition.

    The previous state is loaded from ``round_input.state_path`` when present
    (an empty accumulated-notes list before the first round or after a split
    reset). State size is the owner's byte-cap problem at serialization, not
    trust — but this arm refuses to emit state the declared cap cannot hold,
    so the failure is loud here rather than silent later.
    """

    byte_cap: int

    def improve(self, round_input: ImprovementRoundInput) -> ImprovementRoundOutput:
        notes = _load_accumulated_notes(round_input.state_path)
        entry = _note_entry(round_input)
        notes.append(entry)
        state_bytes = _encode_notes(notes)
        if len(state_bytes) > self.byte_cap:
            raise ArmError(
                "experience state exceeds the declared byte cap: "
                f"{len(state_bytes)} > {self.byte_cap}"
            )
        return ImprovementRoundOutput(
            agent_files_changed={},
            state_update=state_bytes,
            usage=_FIXED_USAGE,
        )


@dataclass(frozen=True, slots=True)
class OpenSClIResearcherImprover:
    """Open-S researcher arm: delegate each round to the researcher harness.

    A bridge, not the harness itself. ``run_round`` is injected at
    construction with ``ResearchRoundRequest``-compatible semantics and
    returns changed agent files as a relative-path to content mapping; the
    real bridge over ``campaign/researcher.py`` is owner-wired to keep this
    package free of campaign imports (the campaign surface is
    callback-duck-typed, so a callback adapter satisfies this protocol).

    ``run_round`` supplies its own usage accounting; when it reports none, a
    zero report is recorded — a bridge that cannot account is a qualification
    concern, not a silent-cost license.
    """

    run_round: RoundRunner
    usage_report: Callable[[], UsageReport] | None = None

    def improve(self, round_input: ImprovementRoundInput) -> ImprovementRoundOutput:
        changed = self.run_round(round_input)
        if not isinstance(changed, Mapping):
            raise ArmError("run_round must return a Mapping of changed agent files")
        usage = self.usage_report() if self.usage_report is not None else UsageReport()
        return ImprovementRoundOutput(
            agent_files_changed=dict(changed),
            state_update=None,
            usage=usage,
        )


def _load_accumulated_notes(state_path: Path | None) -> list[dict[str, object]]:
    if state_path is None:
        return []
    try:
        state_bytes = state_path.read_bytes()
    except FileNotFoundError:
        return []
    if not state_bytes:
        return []
    raw = json.loads(state_bytes)
    if not isinstance(raw, list):
        raise ArmError("existing experience state is not a JSON list")
    return list(raw)


def _note_entry(round_input: ImprovementRoundInput) -> dict[str, object]:
    feedback_text = round_input.restricted_feedback_bytes.decode("utf-8")
    return {
        "note": feedback_text,
        "round_index": round_input.round_index,
    }


def _encode_notes(notes: list[dict[str, object]]) -> bytes:
    return json.dumps(
        notes,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
