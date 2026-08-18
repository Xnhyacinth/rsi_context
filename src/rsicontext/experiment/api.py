"""Strict API profiles and a recorded frozen-reader connectivity canary."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from rsicontext.eval.openai_compatible import OpenAICompatibleReader, Transport
from rsicontext.policy import ContextPack, DocumentChunk
from rsicontext.registry.schema import RegistryError

APIProtocol = Literal["chat-completions-sse"]
_ENVIRONMENT_NAME = re.compile(r"[A-Z_][A-Z0-9_]*")
_PROFILE_ID = re.compile(r"[a-z0-9][a-z0-9._-]*")
_CANARY_QUERY = "What is the canary code?"
_CANARY_TEXT = "The canary code is amber."
_CANARY_ANSWER = "amber"


@dataclass(frozen=True, slots=True)
class APIProfile:
    """Evaluator-owned configuration for one external frozen-reader candidate."""

    id: str
    provider: str
    endpoint_env: str
    api_key_env: str
    allowed_host: str
    model: str
    protocol: APIProtocol
    evaluation_max_model_len: int
    max_output_tokens: int
    seed: int
    temperature: float
    provider_revision: str | None
    chat_template_enable_thinking: bool | None = None

    def __post_init__(self) -> None:
        for field_name, value in (
            ("id", self.id),
            ("provider", self.provider),
            ("endpoint_env", self.endpoint_env),
            ("api_key_env", self.api_key_env),
            ("allowed_host", self.allowed_host),
            ("model", self.model),
        ):
            if not isinstance(value, str) or not value.strip():
                raise RegistryError(f"API profile {field_name} must be a non-empty string")
        if _PROFILE_ID.fullmatch(self.id) is None:
            raise RegistryError("API profile id is unsafe")
        if any(
            _ENVIRONMENT_NAME.fullmatch(name) is None
            for name in (self.endpoint_env, self.api_key_env)
        ):
            raise RegistryError("API profile environment variable names are unsafe")
        if self.protocol != "chat-completions-sse":
            raise RegistryError("unsupported API protocol")
        for field_name, capacity_value in (
            ("evaluation_max_model_len", self.evaluation_max_model_len),
            ("max_output_tokens", self.max_output_tokens),
        ):
            if (
                not isinstance(capacity_value, int)
                or isinstance(capacity_value, bool)
                or capacity_value <= 0
            ):
                raise RegistryError(f"API profile {field_name} must be a positive integer")
        if self.max_output_tokens >= self.evaluation_max_model_len:
            raise RegistryError("API output cap must be smaller than the evaluation model length")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or self.seed < 0:
            raise RegistryError("API profile seed must be a non-negative integer")
        if (
            isinstance(self.temperature, bool)
            or not isinstance(self.temperature, (int, float))
            or not math.isfinite(self.temperature)
            or self.temperature != 0.0
        ):
            raise RegistryError("API profile temperature must be exactly zero")
        if self.provider_revision is not None and (
            not isinstance(self.provider_revision, str) or not self.provider_revision.strip()
        ):
            raise RegistryError("provider_revision must be a non-empty string or null")
        if self.chat_template_enable_thinking is not None and not isinstance(
            self.chat_template_enable_thinking, bool
        ):
            raise RegistryError("chat_template_enable_thinking must be a boolean or null")

    @classmethod
    def from_dict(cls, value: object) -> APIProfile:
        if not isinstance(value, dict):
            raise RegistryError("each API profile must be an object")
        fields = {
            "id",
            "provider",
            "endpoint_env",
            "api_key_env",
            "allowed_host",
            "model",
            "protocol",
            "evaluation_max_model_len",
            "max_output_tokens",
            "seed",
            "temperature",
            "provider_revision",
        }
        missing = fields.difference(value)
        if missing:
            raise RegistryError(f"API profile missing fields: {', '.join(sorted(missing))}")
        optional_fields = {"chat_template_enable_thinking"}
        unexpected = set(value).difference(fields | optional_fields)
        if unexpected:
            raise RegistryError(
                f"API profile has unexpected fields: {', '.join(sorted(unexpected))}"
            )
        return cls(
            **{field_name: value[field_name] for field_name in fields},
            chat_template_enable_thinking=value.get("chat_template_enable_thinking"),
        )

    @property
    def version_pinned(self) -> bool:
        return self.provider_revision is not None

    @property
    def profile_hash(self) -> str:
        identity = asdict(self)
        if self.chat_template_enable_thinking is None:
            identity.pop("chat_template_enable_thinking")
        payload = json.dumps(identity, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class APIProfiles:
    profiles: tuple[APIProfile, ...]

    def get(self, profile_id: str) -> APIProfile:
        matches = [profile for profile in self.profiles if profile.id == profile_id]
        if not matches:
            raise RegistryError(f"unknown API profile: {profile_id}")
        return matches[0]


@dataclass(frozen=True, slots=True)
class APICanaryResult:
    """Serializable evidence about one repeated API compatibility probe."""

    schema_version: int
    canary_id: str
    started_at: str
    endpoint: str
    profile_id: str
    profile_hash: str
    provider: str
    requested_model: str
    provider_revision: str | None
    version_pinned: bool
    seed: int
    temperature: float
    answers: tuple[str, ...]
    observed_models: tuple[str, ...]
    response_ids: tuple[str, ...]
    input_tokens: tuple[int, ...]
    output_tokens: tuple[int, ...]
    latency_seconds: tuple[float, ...]
    answer_stable: bool
    answer_correct: bool
    usage_stable: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_api_profiles(path: str | Path) -> APIProfiles:
    try:
        raw: object = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"cannot load API profiles {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise RegistryError("API profile root must be an object")
    if set(raw) != {"schema_version", "profiles"}:
        raise RegistryError("API profile top-level fields must be schema_version and profiles")
    if raw.get("schema_version") != 1:
        raise RegistryError("unsupported API profile schema")
    raw_profiles = raw.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise RegistryError("API profiles must be a non-empty list")
    profiles = tuple(APIProfile.from_dict(value) for value in raw_profiles)
    ids = [profile.id for profile in profiles]
    if len(ids) != len(set(ids)):
        raise RegistryError("API profile ids must be unique")
    return APIProfiles(profiles)


def run_api_canary(
    profile: APIProfile,
    *,
    endpoint: str,
    api_key: str,
    repetitions: int = 5,
    transport: Transport | None = None,
    timer: Callable[[], float] = time.perf_counter,
    started_at: str | None = None,
) -> APICanaryResult:
    """Replay a public, answer-stable probe without persisting credentials."""

    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions < 1:
        raise ValueError("repetitions must be a positive integer")
    reader_kwargs: dict[str, Any] = {}
    if transport is not None:
        reader_kwargs["transport"] = transport
    reader = OpenAICompatibleReader(
        endpoint=endpoint,
        model=profile.model,
        max_tokens=min(8, profile.max_output_tokens),
        max_model_len=profile.evaluation_max_model_len,
        seed=profile.seed,
        stream=True,
        require_response_model=True,
        chat_template_enable_thinking=profile.chat_template_enable_thinking,
        allowed_hosts=(profile.allowed_host,),
        api_key=api_key,
        **reader_kwargs,
    )
    chunk = DocumentChunk("api-canary-1", "api-canary", 0, len(_CANARY_TEXT), _CANARY_TEXT, 6)
    context = ContextPack(spans=(chunk,), ordering=(chunk.chunk_id,), token_count=6)
    answers: list[str] = []
    observed_models: list[str] = []
    response_ids: list[str] = []
    input_tokens: list[int] = []
    output_tokens: list[int] = []
    latency_seconds: list[float] = []
    for _ in range(repetitions):
        before = timer()
        output = reader.read(_CANARY_QUERY, context)
        elapsed = timer() - before
        if not math.isfinite(elapsed) or elapsed < 0:
            raise RuntimeError("API canary timer returned an invalid duration")
        latency_seconds.append(elapsed)
        if output.response_model is None or output.response_id is None:
            raise RuntimeError("strict API canary reader returned no response identity")
        answers.append(output.answer)
        observed_models.append(output.response_model)
        response_ids.append(output.response_id)
        input_tokens.append(output.input_tokens)
        output_tokens.append(output.output_tokens)
    timestamp = started_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return APICanaryResult(
        schema_version=2,
        canary_id="evidence-exact-v1",
        started_at=timestamp,
        endpoint=endpoint,
        profile_id=profile.id,
        profile_hash=profile.profile_hash,
        provider=profile.provider,
        requested_model=profile.model,
        provider_revision=profile.provider_revision,
        version_pinned=profile.version_pinned,
        seed=profile.seed,
        temperature=profile.temperature,
        answers=tuple(answers),
        observed_models=tuple(observed_models),
        response_ids=tuple(response_ids),
        input_tokens=tuple(input_tokens),
        output_tokens=tuple(output_tokens),
        latency_seconds=tuple(latency_seconds),
        answer_stable=len(set(answers)) == 1,
        answer_correct=all(answer == _CANARY_ANSWER for answer in answers),
        usage_stable=len(set(input_tokens)) == 1 and len(set(output_tokens)) == 1,
    )


def write_api_canary(result: APICanaryResult, path: str | Path) -> None:
    """Write one immutable canary record without replacing earlier evidence."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")
