"""Immutable allocation contract for one bounded visible RSI trajectory."""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

from rsicontext.campaign.loop import (
    FEEDBACK_VISIBLE_GOLD,
    LINEAGE_LAST_VALID,
    SEARCH_NORMAL,
    LoopContractError,
    validate_loop_contract,
)
from rsicontext.policy import Budget
from rsicontext.researcher import ProcessLimits

_SHA256 = re.compile(r"[0-9a-f]{64}")
_ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_SECRET_IDENTITY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "bearer_token",
        "credential",
        "credentials",
        "password",
        "refresh_token",
        "secret",
        "token",
    }
)
_SECRET_IDENTITY_SUFFIXES = (
    "_access_token",
    "_api_key",
    "_authorization",
    "_bearer_token",
    "_client_secret",
    "_credential",
    "_credentials",
    "_password",
    "_refresh_token",
    "_secret",
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def policy_tree_sha256(root: Path) -> str:
    """Hash ordered Python paths and bytes without trusting Git metadata."""

    if not isinstance(root, Path):
        raise TypeError("policy root must be a pathlib.Path")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("policy root must be a regular directory")
    digest = hashlib.sha256()
    file_count = 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise ValueError(f"policy tree contains a symlink: {relative.as_posix()}")
        if path.is_dir():
            continue
        if not path.is_file() or path.suffix != ".py":
            raise ValueError(f"policy tree contains a non-Python file: {relative.as_posix()}")
        encoded_path = relative.as_posix().encode()
        content = path.read_bytes()
        digest.update(len(encoded_path).to_bytes(4, "big"))
        digest.update(encoded_path)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
        file_count += 1
    if file_count == 0:
        raise ValueError("policy tree must contain at least one Python file")
    return digest.hexdigest()


def _callable_identity(function: Callable[..., object]) -> tuple[str, str, str]:
    name = f"{function.__module__}.{function.__qualname__}"
    try:
        source = inspect.getsource(function).encode()
        module = inspect.getmodule(function)
        if module is None:
            raise ValueError(f"scorer module is unavailable: {name}")
        module_source = inspect.getsource(module).encode()
    except (OSError, TypeError) as error:
        raise ValueError(f"scorer source is unavailable: {name}") from error
    return (
        name,
        hashlib.sha256(source).hexdigest(),
        hashlib.sha256(module_source).hexdigest(),
    )


def _identity_preimage(value: Mapping[str, object] | None, field: str) -> str:
    if value is None or not value:
        raise ValueError(f"{field} must be a non-empty identity mapping")
    normalized = dict(value)
    _validate_identity_value(normalized, field)
    return json.dumps(
        normalized,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _validate_identity_value(value: object, field: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError(f"{field} identity keys must be non-empty strings")
            normalized_key = key.casefold().replace("-", "_")
            if normalized_key in _SECRET_IDENTITY_KEYS or normalized_key.endswith(
                _SECRET_IDENTITY_SUFFIXES
            ):
                raise ValueError(f"{field} contains secret-bearing key: {key}")
            _validate_identity_value(item, f"{field}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_identity_value(item, f"{field}[{index}]")
        return
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    raise ValueError(f"{field} must contain only finite JSON identity values")


def _identity_sha256(preimage: str) -> str:
    return hashlib.sha256(preimage.encode()).hexdigest()


def _positive_integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class BoundedRSIRunContract:
    """Pre-run identities, budgets, and lineage rules for visible qualification."""

    dataset_fingerprint: str
    visible_items_sha256: str
    visible_item_count: int
    visible_item_ids_sha256: str
    initial_policy_sha256: str
    scorer_name: str
    scorer_sha256: str
    scorer_module_sha256: str
    token_axis_identity_preimage: str
    token_axis_identity_sha256: str
    reader_identity_preimage: str
    researcher_identity_preimage: str
    reader_identity_sha256: str
    researcher_identity_sha256: str
    rounds: int
    budget: Budget
    max_reader_calls: int
    max_researcher_turns: int
    max_prompt_bytes: int
    researcher_environment_allowlist: tuple[str, ...]
    max_budget_usd: float | None
    researcher_budget_usd_ceiling: float | None
    researcher_turn_timeout_seconds: float
    researcher_wall_seconds_ceiling: float
    max_line_bytes: int
    max_stdout_bytes: int
    max_stderr_bytes: int
    max_total_bytes: int
    valid_candidate_reader_calls_per_item: int = 1
    invalid_submission_reader_calls: int = 0
    lineage_rule: str = LINEAGE_LAST_VALID
    selection_rule: str = "visible-strict-historical-best"
    feedback_schema: str = FEEDBACK_VISIBLE_GOLD
    search_mode: str = SEARCH_NORMAL
    matched_primary_estimand: bool = False
    formal_process_isolation: bool = False
    qualification_only: bool = True
    schema_version: int = 2

    def __post_init__(self) -> None:
        for field in (
            "dataset_fingerprint",
            "visible_items_sha256",
            "visible_item_ids_sha256",
            "initial_policy_sha256",
            "scorer_sha256",
            "scorer_module_sha256",
            "token_axis_identity_sha256",
            "reader_identity_sha256",
            "researcher_identity_sha256",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
                raise ValueError(f"{field} must be a lowercase SHA-256 digest")
        for preimage_field, digest_field in (
            ("token_axis_identity_preimage", "token_axis_identity_sha256"),
            ("reader_identity_preimage", "reader_identity_sha256"),
            ("researcher_identity_preimage", "researcher_identity_sha256"),
        ):
            preimage = getattr(self, preimage_field)
            if not isinstance(preimage, str):
                raise ValueError(f"{preimage_field} must be canonical JSON")
            try:
                decoded = json.loads(preimage)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{preimage_field} must be canonical JSON") from exc
            if not isinstance(decoded, dict) or not decoded:
                raise ValueError(f"{preimage_field} must encode a non-empty identity mapping")
            if _identity_preimage(decoded, preimage_field) != preimage:
                raise ValueError(f"{preimage_field} must use canonical JSON encoding")
            if _identity_sha256(preimage) != getattr(self, digest_field):
                raise ValueError(f"{digest_field} does not match its identity preimage")
        for field in (
            "visible_item_count",
            "rounds",
            "max_reader_calls",
            "max_researcher_turns",
            "max_prompt_bytes",
            "max_line_bytes",
            "max_stdout_bytes",
            "max_stderr_bytes",
            "max_total_bytes",
        ):
            _positive_integer(getattr(self, field), field)
        if not isinstance(self.budget, Budget):
            raise TypeError("budget must be Budget")
        _positive_integer(self.budget.max_tokens, "budget.max_tokens")
        if not isinstance(self.scorer_name, str) or not self.scorer_name:
            raise ValueError("scorer_name must be non-empty")
        if not isinstance(self.researcher_environment_allowlist, tuple):
            raise TypeError("researcher_environment_allowlist must be a tuple")
        if len(self.researcher_environment_allowlist) != len(
            set(self.researcher_environment_allowlist)
        ):
            raise ValueError("researcher_environment_allowlist must be unique")
        for name in self.researcher_environment_allowlist:
            if not isinstance(name, str) or _ENVIRONMENT_NAME.fullmatch(name) is None:
                raise ValueError("researcher_environment_allowlist contains an invalid name")
        if self.max_budget_usd is not None and (
            isinstance(self.max_budget_usd, bool)
            or not isinstance(self.max_budget_usd, (int, float))
            or not math.isfinite(self.max_budget_usd)
            or self.max_budget_usd <= 0
        ):
            raise ValueError("max_budget_usd must be finite and positive")
        expected_usd_ceiling = (
            None if self.max_budget_usd is None else self.rounds * self.max_budget_usd
        )
        if self.researcher_budget_usd_ceiling != expected_usd_ceiling:
            raise ValueError("researcher dollar ceiling must equal rounds times per-turn budget")
        if self.max_researcher_turns != self.rounds:
            raise ValueError("max_researcher_turns must equal rounds")
        expected_calls = self.visible_item_count * (1 + self.rounds)
        if self.max_reader_calls != expected_calls:
            raise ValueError("max_reader_calls must cover H0 plus one call per item and round")
        if (
            not math.isfinite(self.researcher_turn_timeout_seconds)
            or self.researcher_turn_timeout_seconds <= 0
        ):
            raise ValueError("researcher_turn_timeout_seconds must be finite and positive")
        if self.researcher_wall_seconds_ceiling != (
            self.rounds * self.researcher_turn_timeout_seconds
        ):
            raise ValueError("researcher wall ceiling must equal rounds times per-turn timeout")
        if self.valid_candidate_reader_calls_per_item != 1:
            raise ValueError("visible single-reader RSI requires one call per valid item")
        if self.invalid_submission_reader_calls != 0:
            raise ValueError("invalid submissions must not call the reader")
        if (
            self.matched_primary_estimand is not False
            or self.formal_process_isolation is not False
            or self.qualification_only is not True
        ):
            raise ValueError("this contract is restricted to visible qualification")
        if self.schema_version != 2:
            raise ValueError("unsupported bounded RSI run contract schema")
        try:
            validate_loop_contract(
                lineage_rule=self.lineage_rule,
                search_mode=self.search_mode,
                feedback_schema=self.feedback_schema,
            )
        except LoopContractError as exc:
            raise ValueError(str(exc)) from exc

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["token_axis_identity_preimage"] = json.loads(self.token_axis_identity_preimage)
        payload["reader_identity_preimage"] = json.loads(self.reader_identity_preimage)
        payload["researcher_identity_preimage"] = json.loads(self.researcher_identity_preimage)
        return payload

    @property
    def contract_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    def validate_observed(
        self,
        *,
        round_slots: int,
        valid_candidate_rounds: int,
        reader_calls: int,
    ) -> None:
        """Fail if execution exceeded or silently skipped its frozen allocation."""

        if round_slots != self.rounds:
            raise RuntimeError("observed researcher slots do not match the run contract")
        if valid_candidate_rounds < 0 or valid_candidate_rounds > round_slots:
            raise RuntimeError("observed valid candidate count violates the run contract")
        expected_calls = self.visible_item_count * (1 + valid_candidate_rounds)
        if reader_calls != expected_calls:
            raise RuntimeError("observed reader calls do not match valid candidate rounds")


def build_bounded_rsi_run_contract(
    *,
    dataset_fingerprint: str,
    visible_items_sha256: str,
    visible_item_ids: tuple[str, ...],
    initial_policy_directory: Path,
    scorer: Callable[..., object],
    token_axis_identity: Mapping[str, object] | None,
    reader_identity: Mapping[str, object] | None,
    researcher_identity: Mapping[str, object] | None,
    researcher_environment_allowlist: tuple[str, ...],
    max_budget_usd: float | None,
    rounds: int,
    budget: Budget,
    max_prompt_bytes: int,
    process_limits: ProcessLimits,
    lineage_rule: str = LINEAGE_LAST_VALID,
    feedback_schema: str = FEEDBACK_VISIBLE_GOLD,
    search_mode: str = SEARCH_NORMAL,
) -> BoundedRSIRunContract:
    """Freeze one visible trajectory's allocations before its first model call."""

    if not isinstance(dataset_fingerprint, str) or _SHA256.fullmatch(dataset_fingerprint) is None:
        raise ValueError("dataset_fingerprint must be a lowercase SHA-256 digest")
    if not isinstance(visible_items_sha256, str) or _SHA256.fullmatch(visible_items_sha256) is None:
        raise ValueError("visible_items_sha256 must be a lowercase SHA-256 digest")
    if not visible_item_ids or any(not item_id for item_id in visible_item_ids):
        raise ValueError("visible_item_ids must be non-empty strings")
    if len(visible_item_ids) != len(set(visible_item_ids)):
        raise ValueError("visible_item_ids must be unique")
    _positive_integer(rounds, "rounds")
    if not isinstance(budget, Budget):
        raise TypeError("budget must be Budget")
    _positive_integer(max_prompt_bytes, "max_prompt_bytes")
    if not isinstance(process_limits, ProcessLimits):
        raise TypeError("process_limits must be ProcessLimits")
    scorer_name, scorer_sha256, scorer_module_sha256 = _callable_identity(scorer)
    token_axis_preimage = _identity_preimage(token_axis_identity, "token_axis_identity")
    reader_preimage = _identity_preimage(reader_identity, "reader_identity")
    researcher_preimage = _identity_preimage(researcher_identity, "researcher_identity")
    return BoundedRSIRunContract(
        dataset_fingerprint=dataset_fingerprint,
        visible_items_sha256=visible_items_sha256,
        visible_item_count=len(visible_item_ids),
        visible_item_ids_sha256=_canonical_sha256(list(visible_item_ids)),
        initial_policy_sha256=policy_tree_sha256(initial_policy_directory),
        scorer_name=scorer_name,
        scorer_sha256=scorer_sha256,
        scorer_module_sha256=scorer_module_sha256,
        token_axis_identity_preimage=token_axis_preimage,
        token_axis_identity_sha256=_identity_sha256(token_axis_preimage),
        reader_identity_preimage=reader_preimage,
        researcher_identity_preimage=researcher_preimage,
        reader_identity_sha256=_identity_sha256(reader_preimage),
        researcher_identity_sha256=_identity_sha256(researcher_preimage),
        rounds=rounds,
        budget=budget,
        max_reader_calls=len(visible_item_ids) * (1 + rounds),
        max_researcher_turns=rounds,
        max_prompt_bytes=max_prompt_bytes,
        researcher_environment_allowlist=researcher_environment_allowlist,
        max_budget_usd=max_budget_usd,
        researcher_budget_usd_ceiling=(None if max_budget_usd is None else rounds * max_budget_usd),
        researcher_turn_timeout_seconds=float(process_limits.timeout_seconds),
        researcher_wall_seconds_ceiling=rounds * float(process_limits.timeout_seconds),
        max_line_bytes=process_limits.max_line_bytes,
        max_stdout_bytes=process_limits.max_stdout_bytes,
        max_stderr_bytes=process_limits.max_stderr_bytes,
        max_total_bytes=process_limits.max_total_bytes,
        lineage_rule=lineage_rule,
        feedback_schema=feedback_schema,
        search_mode=search_mode,
    )


def contract_file_sha256(path: Path) -> str:
    """Return the byte identity of a regular run-contract file."""

    if not isinstance(path, Path):
        raise TypeError("contract path must be a pathlib.Path")
    if path.is_symlink() or not path.is_file():
        raise ValueError("contract path must be a regular file")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_contract_file_unchanged(path: Path, expected_sha256: str) -> None:
    """Fail closed if a persisted run contract changed during execution."""

    if not isinstance(expected_sha256, str) or _SHA256.fullmatch(expected_sha256) is None:
        raise ValueError("expected contract file hash must be a lowercase SHA-256 digest")
    if contract_file_sha256(path) != expected_sha256:
        raise RuntimeError("run contract file content changed during execution")
