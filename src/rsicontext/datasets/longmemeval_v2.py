"""Text-only, offline LongMemEval-V2 trajectory compilation.

This module only turns pinned source records into immutable policy inputs. It does not
call a model, execute recorded actions, open screenshots, or evaluate answers.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from rsicontext.policy import Artifact, DocumentChunk

LongMemEvalTier = Literal["small", "medium"]

_QUESTION_FIELDS = frozenset(
    {
        "id",
        "domain",
        "environment",
        "question_type",
        "question",
        "image",
        "answer",
        "eval_function",
    }
)
_TRAJECTORY_FIELDS = frozenset(
    {"id", "domain", "environment", "goal", "outcome", "start_url", "states"}
)
_STATE_FIELDS = frozenset(
    {
        "state_index",
        "step",
        "url",
        "action",
        "thought",
        "accessibility_tree",
        "screenshot",
    }
)
_IMMUTABLE_REVISION = re.compile(r"[0-9a-f]{40}")


class LongMemEvalDataError(ValueError):
    """Raised when pinned LongMemEval-V2 inputs violate the expected schema."""


@dataclass(frozen=True, slots=True)
class SourceFileFingerprint:
    """Portable content identity for one input file."""

    relative_path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class LongMemEvalSource:
    """Pinned upstream revision and the exact files consumed by the adapter."""

    revision: str
    files: tuple[SourceFileFingerprint, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class LongMemEvalPolicyItem:
    """Label-free input that may cross into a context-policy workspace."""

    question_id: str
    query: str
    domain: str
    environment: str
    question_type: str
    trajectory_ids: tuple[str, ...]
    full_haystack_size: int
    artifact: Artifact


@dataclass(frozen=True, slots=True)
class LongMemEvalEvaluatorItem:
    """Evaluator-side labels paired with their label-free policy input."""

    policy_item: LongMemEvalPolicyItem
    answer: str
    eval_function: str
    image: str | None


@dataclass(frozen=True, slots=True)
class LongMemEvalOfflineDataset:
    """Compiled public transfer data; this is not a completed transfer experiment."""

    _evaluator_items: tuple[LongMemEvalEvaluatorItem, ...]
    source: LongMemEvalSource
    tier: LongMemEvalTier
    loaded_trajectory_ids: frozenset[str]
    excluded_image_question_count: int
    fingerprint: str

    def policy_items(self) -> tuple[LongMemEvalPolicyItem, ...]:
        """Return only fields allowed to enter the context-policy side."""

        return tuple(item.policy_item for item in self._evaluator_items)

    def evaluator_items(self) -> tuple[LongMemEvalEvaluatorItem, ...]:
        """Return reference answers inside the evaluator boundary only."""

        return self._evaluator_items


@dataclass(frozen=True, slots=True)
class _Question:
    question_id: str
    domain: str
    environment: str
    question_type: str
    question: str
    image: str | None
    answer: str
    eval_function: str


@dataclass(frozen=True, slots=True)
class _State:
    state_index: int
    action: str | None
    thought: str | None
    accessibility_tree: str


@dataclass(frozen=True, slots=True)
class _Trajectory:
    trajectory_id: str
    domain: str
    states: tuple[_State, ...]


def _require_record(raw: object, fields: frozenset[str], location: str) -> dict[str, object]:
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        raise LongMemEvalDataError(f"{location} must be a JSON object with string keys")
    record = cast(dict[str, object], raw)
    if set(record) != fields:
        missing = sorted(fields - set(record))
        unexpected = sorted(set(record) - fields)
        raise LongMemEvalDataError(
            f"{location} has unexpected schema; missing={missing}, unexpected={unexpected}"
        )
    return record


def _require_string(value: object, field: str, location: str) -> str:
    if not isinstance(value, str):
        raise LongMemEvalDataError(f"{location}.{field} must be a string")
    if not value:
        raise LongMemEvalDataError(f"{location}.{field} must not be empty")
    return value


def _optional_string(value: object, field: str, location: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, field, location)


def _require_integer(value: object, field: str, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LongMemEvalDataError(f"{location}.{field} must be an integer")
    return value


def _decode_json(raw: bytes, location: str) -> object:
    try:
        return cast(object, json.loads(raw))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LongMemEvalDataError(f"{location} is not valid UTF-8 JSON") from exc


def _source_record(relative_path: str, digest: hashlib._Hash, size: int) -> SourceFileFingerprint:
    return SourceFileFingerprint(relative_path, digest.hexdigest(), size)


def _load_questions(path: Path) -> tuple[tuple[_Question, ...], SourceFileFingerprint]:
    digest = hashlib.sha256()
    size = 0
    questions: list[_Question] = []
    seen: set[str] = set()
    try:
        source = path.open("rb")
    except OSError as exc:
        raise LongMemEvalDataError(f"cannot open source file: {path}") from exc
    with source:
        for line_number, raw_line in enumerate(source, start=1):
            digest.update(raw_line)
            size += len(raw_line)
            location = f"questions.jsonl:{line_number}"
            if not raw_line.strip():
                raise LongMemEvalDataError(f"{location} must not be blank")
            record = _require_record(_decode_json(raw_line, location), _QUESTION_FIELDS, location)
            question_id = _require_string(record["id"], "id", location)
            if question_id in seen:
                raise LongMemEvalDataError(f"duplicate question id: {question_id}")
            seen.add(question_id)
            questions.append(
                _Question(
                    question_id=question_id,
                    domain=_require_string(record["domain"], "domain", location),
                    environment=_require_string(record["environment"], "environment", location),
                    question_type=_require_string(
                        record["question_type"], "question_type", location
                    ),
                    question=_require_string(record["question"], "question", location),
                    image=_optional_string(record["image"], "image", location),
                    answer=_require_string(record["answer"], "answer", location),
                    eval_function=_require_string(
                        record["eval_function"], "eval_function", location
                    ),
                )
            )
    if not questions:
        raise LongMemEvalDataError("questions.jsonl must contain at least one question")
    return tuple(questions), _source_record("questions.jsonl", digest, size)


def _load_haystack(
    path: Path, *, relative_path: str, question_ids: frozenset[str]
) -> tuple[dict[str, tuple[str, ...]], SourceFileFingerprint]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise LongMemEvalDataError(f"cannot open source file: {path}") from exc
    decoded = _decode_json(raw, relative_path)
    if not isinstance(decoded, dict) or any(not isinstance(key, str) for key in decoded):
        raise LongMemEvalDataError(f"{relative_path} must map question ids to trajectory ids")
    mapping = cast(dict[str, object], decoded)
    if set(mapping) != question_ids:
        missing = sorted(question_ids - set(mapping))
        unexpected = sorted(set(mapping) - question_ids)
        raise LongMemEvalDataError(
            f"{relative_path} question coverage mismatch; "
            f"missing={missing}, unexpected={unexpected}"
        )
    haystack: dict[str, tuple[str, ...]] = {}
    for question_id, value in mapping.items():
        if not isinstance(value, list):
            raise LongMemEvalDataError(f"haystack for {question_id} must be a list")
        trajectory_ids = tuple(
            _require_string(item, f"trajectory_ids[{index}]", f"haystack[{question_id}]")
            for index, item in enumerate(value)
        )
        if not trajectory_ids:
            raise LongMemEvalDataError(f"haystack for {question_id} must not be empty")
        if len(trajectory_ids) != len(set(trajectory_ids)):
            raise LongMemEvalDataError(f"haystack for {question_id} contains duplicate ids")
        haystack[question_id] = trajectory_ids
    record = SourceFileFingerprint(relative_path, hashlib.sha256(raw).hexdigest(), len(raw))
    return haystack, record


def _parse_state(raw: object, *, trajectory_id: str, expected_index: int) -> _State:
    location = f"trajectory[{trajectory_id}].states[{expected_index}]"
    record = _require_record(raw, _STATE_FIELDS, location)
    state_index = _require_integer(record["state_index"], "state_index", location)
    if state_index != expected_index:
        raise LongMemEvalDataError(
            f"{location}.state_index must be {expected_index}, got {state_index}"
        )
    _require_integer(record["step"], "step", location)
    _require_string(record["url"], "url", location)
    action = _optional_string(record["action"], "action", location)
    thought = _optional_string(record["thought"], "thought", location)
    accessibility_tree = _require_string(
        record["accessibility_tree"], "accessibility_tree", location
    )
    _require_string(record["screenshot"], "screenshot", location)
    return _State(state_index, action, thought, accessibility_tree)


def _parse_trajectory(raw: object, *, line_number: int) -> _Trajectory:
    location = f"trajectories.jsonl:{line_number}"
    record = _require_record(raw, _TRAJECTORY_FIELDS, location)
    trajectory_id = _require_string(record["id"], "id", location)
    domain = _require_string(record["domain"], "domain", location)
    _require_string(record["environment"], "environment", location)
    _require_string(record["goal"], "goal", location)
    outcome = _require_string(record["outcome"], "outcome", location)
    if outcome not in {"success", "failure"}:
        raise LongMemEvalDataError(f"{location}.outcome must be success or failure")
    _require_string(record["start_url"], "start_url", location)
    states_raw = record["states"]
    if not isinstance(states_raw, list) or not states_raw:
        raise LongMemEvalDataError(f"{location}.states must be a non-empty list")
    states = tuple(
        _parse_state(state, trajectory_id=trajectory_id, expected_index=index)
        for index, state in enumerate(states_raw)
    )
    return _Trajectory(trajectory_id, domain, states)


def _load_trajectories(
    path: Path, requested_ids: frozenset[str]
) -> tuple[dict[str, _Trajectory], SourceFileFingerprint]:
    digest = hashlib.sha256()
    size = 0
    selected: dict[str, _Trajectory] = {}
    seen: set[str] = set()
    try:
        source = path.open("rb")
    except OSError as exc:
        raise LongMemEvalDataError(f"cannot open source file: {path}") from exc
    with source:
        for line_number, raw_line in enumerate(source, start=1):
            digest.update(raw_line)
            size += len(raw_line)
            location = f"trajectories.jsonl:{line_number}"
            if not raw_line.strip():
                raise LongMemEvalDataError(f"{location} must not be blank")
            trajectory = _parse_trajectory(
                _decode_json(raw_line, location), line_number=line_number
            )
            if trajectory.trajectory_id in seen:
                raise LongMemEvalDataError(f"duplicate trajectory id: {trajectory.trajectory_id}")
            seen.add(trajectory.trajectory_id)
            if trajectory.trajectory_id in requested_ids:
                selected[trajectory.trajectory_id] = trajectory
    missing = requested_ids - set(selected)
    if missing:
        raise LongMemEvalDataError(f"missing requested trajectory ids: {sorted(missing)}")
    return selected, _source_record("trajectories.jsonl", digest, size)


def _render_state(trajectory_id: str, state: _State) -> str:
    action = state.action if state.action is not None else "<none>"
    thought = state.thought if state.thought is not None else "<none>"
    return (
        f"[trajectory_id={trajectory_id} state_index={state.state_index}]\n"
        f"action: {action}\n"
        f"thought: {thought}\n"
        f"accessibility_tree:\n{state.accessibility_tree}"
    )


def _compile_artifact(
    trajectory_ids: tuple[str, ...], trajectories: dict[str, _Trajectory], tier: LongMemEvalTier
) -> Artifact:
    identity = hashlib.sha256(
        json.dumps(trajectory_ids, separators=(",", ":")).encode()
    ).hexdigest()[:20]
    document_id = f"lmev2-{tier}-{identity}"
    chunks: list[DocumentChunk] = []
    cursor = 0
    for trajectory_id in trajectory_ids:
        trajectory = trajectories[trajectory_id]
        for state in trajectory.states:
            text = _render_state(trajectory_id, state)
            chunks.append(
                DocumentChunk(
                    chunk_id=f"lmev2:{trajectory_id}:state:{state.state_index}",
                    document_id=document_id,
                    start=cursor,
                    end=cursor + len(text),
                    text=text,
                    token_count=len(text.split()),
                    role="trajectory_state",
                )
            )
            cursor += len(text) + 1
    return Artifact(document_id=document_id, chunks=tuple(chunks))


def _source_identity(revision: str, files: tuple[SourceFileFingerprint, ...]) -> LongMemEvalSource:
    canonical = {
        "files": [
            {
                "relative_path": item.relative_path,
                "sha256": item.sha256,
                "size_bytes": item.size_bytes,
            }
            for item in sorted(files, key=lambda item: item.relative_path)
        ],
        "revision": revision,
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return LongMemEvalSource(revision, files, fingerprint)


def _validate_limit(value: int | None, field: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise LongMemEvalDataError(f"{field} must be a positive integer or null")


def load_longmemeval_v2(
    root: Path,
    *,
    source_revision: str,
    tier: LongMemEvalTier = "small",
    question_limit: int | None = None,
    trajectories_per_question: int | None = None,
) -> LongMemEvalOfflineDataset:
    """Compile pinned LongMemEval-V2 histories into label-free text artifacts.

    Limits select an ordered prefix for qualification runs. ``full_haystack_size`` remains
    attached to every policy item so a truncated run cannot be mistaken for full coverage.
    """

    if not isinstance(root, Path):
        raise TypeError("root must be a pathlib.Path")
    if not isinstance(source_revision, str) or not source_revision.strip():
        raise LongMemEvalDataError("source_revision must be a non-empty string")
    if _IMMUTABLE_REVISION.fullmatch(source_revision) is None:
        raise LongMemEvalDataError("source_revision must be an immutable 40-character SHA")
    if tier not in {"small", "medium"}:
        raise LongMemEvalDataError(f"unsupported LongMemEval-V2 tier: {tier!r}")
    _validate_limit(question_limit, "question_limit")
    _validate_limit(trajectories_per_question, "trajectories_per_question")

    questions, questions_source = _load_questions(root / "questions.jsonl")
    haystack_relative = f"haystacks/lme_v2_{tier}.json"
    haystack, haystack_source = _load_haystack(
        root / haystack_relative,
        relative_path=haystack_relative,
        question_ids=frozenset(question.question_id for question in questions),
    )
    text_questions = tuple(question for question in questions if question.image is None)
    excluded_image_questions = len(questions) - len(text_questions)
    selected_questions = (
        text_questions if question_limit is None else text_questions[:question_limit]
    )
    if not selected_questions:
        raise LongMemEvalDataError("selection contains no text-only questions")

    selected_ids_by_question: dict[str, tuple[str, ...]] = {}
    for question in selected_questions:
        full_ids = haystack[question.question_id]
        selected_ids_by_question[question.question_id] = (
            full_ids if trajectories_per_question is None else full_ids[:trajectories_per_question]
        )
    requested_ids = frozenset(
        trajectory_id
        for trajectory_ids in selected_ids_by_question.values()
        for trajectory_id in trajectory_ids
    )
    trajectories, trajectories_source = _load_trajectories(
        root / "trajectories.jsonl", requested_ids
    )

    artifacts: dict[tuple[str, ...], Artifact] = {}
    evaluator_items: list[LongMemEvalEvaluatorItem] = []
    for question in selected_questions:
        trajectory_ids = selected_ids_by_question[question.question_id]
        for trajectory_id in trajectory_ids:
            if trajectories[trajectory_id].domain != question.domain:
                raise LongMemEvalDataError(
                    f"trajectory {trajectory_id} domain does not match question "
                    f"{question.question_id}"
                )
        artifact = artifacts.get(trajectory_ids)
        if artifact is None:
            artifact = _compile_artifact(trajectory_ids, trajectories, tier)
            artifacts[trajectory_ids] = artifact
        policy_item = LongMemEvalPolicyItem(
            question_id=question.question_id,
            query=question.question,
            domain=question.domain,
            environment=question.environment,
            question_type=question.question_type,
            trajectory_ids=trajectory_ids,
            full_haystack_size=len(haystack[question.question_id]),
            artifact=artifact,
        )
        evaluator_items.append(
            LongMemEvalEvaluatorItem(
                policy_item=policy_item,
                answer=question.answer,
                eval_function=question.eval_function,
                image=question.image,
            )
        )

    source = _source_identity(
        source_revision, (questions_source, trajectories_source, haystack_source)
    )
    canonical_selection = {
        "question_ids": [item.policy_item.question_id for item in evaluator_items],
        "source_fingerprint": source.fingerprint,
        "tier": tier,
        "trajectory_ids": {
            item.policy_item.question_id: item.policy_item.trajectory_ids
            for item in evaluator_items
        },
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical_selection, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return LongMemEvalOfflineDataset(
        _evaluator_items=tuple(evaluator_items),
        source=source,
        tier=tier,
        loaded_trajectory_ids=requested_ids,
        excluded_image_question_count=excluded_image_questions,
        fingerprint=fingerprint,
    )
