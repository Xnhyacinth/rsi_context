"""Validated, declarative vLLM serving profiles and dry-run command rendering."""

from __future__ import annotations

import hashlib
import json
import shlex
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rsicontext.registry.schema import Registry, RegistryEntry, RegistryError

if TYPE_CHECKING:
    from rsicontext.experiment import APIProfile, RunSpec


@dataclass(frozen=True)
class ServingProfile:
    """A conservative vLLM profile for one eight-GPU host."""

    id: str
    model_id: str
    host: str
    port: int
    max_model_len: int
    tensor_parallel_size: int
    data_parallel_size: int
    dtype: str
    kv_cache_dtype: str
    gpu_memory_utilization: float
    max_num_batched_tokens: int
    max_num_seqs: int
    seed: int
    enable_chunked_prefill: bool
    enable_prefix_caching: bool
    language_model_only: bool
    reasoning_parser: str | None

    def __post_init__(self) -> None:
        self._validate()

    @property
    def profile_hash(self) -> str:
        """Digest every serving field that can affect a frozen run."""

        payload = json.dumps(asdict(self), separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    @property
    def chat_completions_endpoint(self) -> str:
        return f"http://{self.host}:{self.port}/v1/chat/completions"

    @classmethod
    def from_dict(cls, data: object) -> ServingProfile:
        if not isinstance(data, dict):
            raise RegistryError("each serving profile must be an object")
        required = {
            "id",
            "model_id",
            "host",
            "port",
            "max_model_len",
            "tensor_parallel_size",
            "data_parallel_size",
            "dtype",
            "kv_cache_dtype",
            "gpu_memory_utilization",
            "max_num_batched_tokens",
            "max_num_seqs",
            "seed",
            "enable_chunked_prefill",
            "enable_prefix_caching",
            "language_model_only",
            "reasoning_parser",
        }
        missing = required.difference(data)
        if missing:
            raise RegistryError(f"serving profile missing fields: {', '.join(sorted(missing))}")
        unexpected = set(data).difference(required)
        if unexpected:
            raise RegistryError(
                f"serving profile has unexpected fields: {', '.join(sorted(unexpected))}"
            )
        return cls(**{key: data[key] for key in required})

    def _validate(self) -> None:
        if self.host != "127.0.0.1":
            raise RegistryError("serving profile host must be the IPv4 loopback address")
        if (
            not isinstance(self.port, int)
            or isinstance(self.port, bool)
            or not 1 <= self.port <= 65535
        ):
            raise RegistryError("serving profile port must be an integer within [1, 65535]")
        integer_fields = {
            "max_model_len": self.max_model_len,
            "tensor_parallel_size": self.tensor_parallel_size,
            "data_parallel_size": self.data_parallel_size,
            "max_num_batched_tokens": self.max_num_batched_tokens,
            "max_num_seqs": self.max_num_seqs,
        }
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 1
            for value in integer_fields.values()
        ):
            raise RegistryError("serving profile integer capacities must be positive")
        if self.tensor_parallel_size * self.data_parallel_size != 8:
            raise RegistryError(f"serving profile {self.id!r} must allocate exactly 8 GPUs")
        if self.dtype != "bfloat16" or self.kv_cache_dtype != "bfloat16":
            raise RegistryError(f"serving profile {self.id!r} must use BF16 model and KV cache")
        if (
            isinstance(self.gpu_memory_utilization, bool)
            or not isinstance(self.gpu_memory_utilization, (int, float))
            or not 0 < self.gpu_memory_utilization < 1
        ):
            raise RegistryError("gpu_memory_utilization must be between zero and one")
        boolean_fields = (
            self.enable_chunked_prefill,
            self.enable_prefix_caching,
            self.language_model_only,
        )
        if any(not isinstance(value, bool) for value in boolean_fields):
            raise RegistryError("serving profile feature flags must be booleans")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise RegistryError("serving profile seed must be an integer")
        if self.reasoning_parser is not None and not isinstance(self.reasoning_parser, str):
            raise RegistryError("reasoning_parser must be a string or null")


@dataclass(frozen=True)
class ServingProfiles:
    """A collection of profiles with model references checked against the registry."""

    profiles: tuple[ServingProfile, ...]

    def get(self, profile_id: str) -> ServingProfile:
        """Return one named profile."""
        matches = [profile for profile in self.profiles if profile.id == profile_id]
        if not matches:
            raise RegistryError(f"unknown serving profile: {profile_id}")
        return matches[0]


def load_serving_profiles(path: str | Path, registry: Registry) -> ServingProfiles:
    """Load profiles and validate every referenced model."""
    try:
        data: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RegistryError(f"cannot load serving profiles {path}: {error}") from error
    if not isinstance(data, dict):
        raise RegistryError("serving profile root must be an object")
    expected_fields = {"schema_version", "profiles"}
    if set(data) != expected_fields:
        raise RegistryError("serving profile top-level fields must be schema_version and profiles")
    if data.get("schema_version") != 1:
        raise RegistryError("unsupported serving profile schema")
    raw_profiles = data.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise RegistryError("profiles must be a non-empty list")
    profiles = tuple(ServingProfile.from_dict(item) for item in raw_profiles)
    ids = [profile.id for profile in profiles]
    if len(ids) != len(set(ids)):
        raise RegistryError("serving profile ids must be unique")
    entries = {entry.id: entry for entry in registry.entries}
    for profile in profiles:
        entry = entries.get(profile.model_id)
        if entry is None or entry.kind != "model":
            raise RegistryError(f"profile {profile.id!r} references an unknown model")
    return ServingProfiles(profiles)


def validate_run_binding(
    run_spec: RunSpec,
    profile: ServingProfile,
    model: RegistryEntry,
    reader_profile: APIProfile,
) -> None:
    """Reject any drift between a run identity and its registered serving stack."""

    if run_spec.serving_profile_hash != profile.profile_hash:
        raise RegistryError("run serving profile hash does not match the supplied profile")
    if model.kind != "model" or profile.model_id != model.id:
        raise RegistryError("serving profile does not match the supplied registry model")
    if model.revision is None:
        raise RegistryError("serving model must have a pinned revision")
    registered_model_id = model.url.removeprefix("https://huggingface.co/").rstrip("/")
    if run_spec.model.model_id != registered_model_id:
        raise RegistryError("run model id does not match the registered serving model")
    if run_spec.model.revision != model.revision:
        raise RegistryError("run model revision does not match the registered serving model")
    if run_spec.model.tokenizer_revision != model.revision:
        raise RegistryError("run tokenizer revision does not match the registered serving model")
    if run_spec.model.max_model_len != profile.max_model_len:
        raise RegistryError("run model length does not match the serving profile")
    if run_spec.seed != profile.seed:
        raise RegistryError("run seed does not match the serving profile")
    if run_spec.reader_profile_hash != reader_profile.profile_hash:
        raise RegistryError("run reader profile hash does not match the supplied reader profile")
    if reader_profile.model != run_spec.model.model_id:
        raise RegistryError("reader model does not match the run model")
    if reader_profile.allowed_host != profile.host:
        raise RegistryError("reader host does not match the serving profile")
    if reader_profile.provider_revision != run_spec.model.revision:
        raise RegistryError("reader revision does not match the run model revision")
    if reader_profile.evaluation_max_model_len != run_spec.model.max_model_len:
        raise RegistryError("reader model length does not match the run model length")
    if reader_profile.max_output_tokens != run_spec.budget.output_tokens:
        raise RegistryError("reader output limit does not match the run budget")
    if reader_profile.seed != run_spec.seed:
        raise RegistryError("reader seed does not match the run seed")
    if reader_profile.chat_template_enable_thinking != run_spec.chat_template_enable_thinking:
        raise RegistryError("reader thinking mode does not match the run")


def build_serve_command(
    profile: ServingProfile,
    model: RegistryEntry,
    *,
    hold_wrapper: str | Path = "/workspace/wynckeliao/ops/gpu/hold.sh",
) -> str:
    """Render a hold-wrapped command without executing it."""
    if model.id != profile.model_id or model.revision is None:
        raise RegistryError(f"profile {profile.id!r} does not match a pinned model")
    args = [
        "bash",
        str(hold_wrapper),
        "wrap",
        "0,1,2,3,4,5,6,7",
        "--",
        "vllm",
        "serve",
        model.url.removeprefix("https://huggingface.co/").rstrip("/"),
        "--host",
        profile.host,
        "--port",
        str(profile.port),
        "--revision",
        model.revision,
        "--dtype",
        profile.dtype,
        "--kv-cache-dtype",
        profile.kv_cache_dtype,
        "--max-model-len",
        str(profile.max_model_len),
        "--tensor-parallel-size",
        str(profile.tensor_parallel_size),
        "--data-parallel-size",
        str(profile.data_parallel_size),
        "--gpu-memory-utilization",
        str(profile.gpu_memory_utilization),
        "--max-num-batched-tokens",
        str(profile.max_num_batched_tokens),
        "--max-num-seqs",
        str(profile.max_num_seqs),
        "--seed",
        str(profile.seed),
    ]
    args.append(
        "--enable-chunked-prefill"
        if profile.enable_chunked_prefill
        else "--no-enable-chunked-prefill"
    )
    args.append(
        "--enable-prefix-caching" if profile.enable_prefix_caching else "--no-enable-prefix-caching"
    )
    if profile.language_model_only:
        args.append("--language-model-only")
    if profile.reasoning_parser is not None:
        args.extend(("--reasoning-parser", profile.reasoning_parser))
    return shlex.join(args)
