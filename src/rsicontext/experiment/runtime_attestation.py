"""Fail-closed runtime and isolation binding for formal evaluation runs."""

from __future__ import annotations

import hashlib
import json
import stat
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rsicontext.experiment.config import Split
from rsicontext.registry import validate_run_binding
from rsicontext.registry.schema import RegistryError
from rsicontext.security.isolation import IsolationAttestation

if TYPE_CHECKING:
    from rsicontext.experiment.api import APIProfile
    from rsicontext.experiment.config import RunSpec
    from rsicontext.registry.schema import RegistryEntry
    from rsicontext.registry.serving import ServingProfile

EndpointTransport = Callable[[urllib.request.Request, float], bytes]
_MAX_OBSERVATION_BYTES = 1024 * 1024
_SHA256 = frozenset("0123456789abcdef")
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class FormalRunError(ValueError):
    """Raised when runtime evidence is insufficient or drifts from the frozen run."""


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: object,
        code: int,
        message: str,
        headers: object,
        new_url: str,
    ) -> None:
        raise FormalRunError("runtime observation redirects are forbidden")


def _urlopen_transport(request: urllib.request.Request, timeout: float) -> bytes:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _RejectRedirects())
    try:
        with opener.open(request, timeout=timeout) as response:  # nosec B310
            payload = response.read(_MAX_OBSERVATION_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FormalRunError(f"runtime endpoint observation failed: {exc}") from exc
    if not isinstance(payload, bytes):
        raise FormalRunError("runtime observation returned a non-bytes payload")
    if len(payload) > _MAX_OBSERVATION_BYTES:
        raise FormalRunError("runtime observation exceeds the 1 MiB limit")
    return payload


def _require_sha256(value: str, field_name: str) -> None:
    if len(value) != 64 or any(character not in _SHA256 for character in value):
        raise FormalRunError(f"{field_name} must be a lowercase SHA-256 digest")


def _digest_json(value: object) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def canonical_reader_endpoint(endpoint: str) -> str:
    """Return a credential-free canonical chat endpoint or reject it."""

    if not isinstance(endpoint, str) or not endpoint:
        raise FormalRunError("endpoint must be a non-empty string")
    try:
        parsed = urllib.parse.urlsplit(endpoint)
        port = parsed.port
    except ValueError as exc:
        raise FormalRunError(f"endpoint is invalid: {exc}") from exc
    if parsed.scheme.casefold() not in {"http", "https"} or parsed.hostname is None:
        raise FormalRunError("endpoint must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise FormalRunError("endpoint must not contain credentials")
    if parsed.query:
        raise FormalRunError("endpoint must not contain a query string")
    if parsed.fragment:
        raise FormalRunError("endpoint must not contain a fragment")
    if parsed.path != "/v1/chat/completions":
        raise FormalRunError("formal endpoint must target /v1/chat/completions")
    scheme = parsed.scheme.casefold()
    hostname = parsed.hostname.casefold()
    host = f"[{hostname}]" if ":" in hostname else hostname
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    authority = host if port is None or default_port else f"{host}:{port}"
    return urllib.parse.urlunsplit((scheme, authority, parsed.path, "", ""))


@dataclass(frozen=True, slots=True)
class ObservedModel:
    id: str
    root: str | None
    parent: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise FormalRunError("observed model id must be non-empty")
        for field_name, value in (("root", self.root), ("parent", self.parent)):
            if value is not None and (not isinstance(value, str) or not value):
                raise FormalRunError(f"observed model {field_name} must be non-empty or null")


@dataclass(frozen=True, slots=True)
class EndpointObservation:
    """Credential-free live responses from one canonical runtime endpoint."""

    evidence_source: str
    observed_at: str
    endpoint: str
    version: str
    version_payload_sha256: str
    models_payload_sha256: str
    models: tuple[ObservedModel, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_source, str) or not self.evidence_source:
            raise FormalRunError("endpoint evidence source must be non-empty")
        if not isinstance(self.observed_at, str) or not self.observed_at:
            raise FormalRunError("endpoint observation timestamp must be non-empty")
        if canonical_reader_endpoint(self.endpoint) != self.endpoint:
            raise FormalRunError("observed endpoint is not canonical")
        if not isinstance(self.version, str) or not self.version:
            raise FormalRunError("observed runtime version must be non-empty")
        _require_sha256(self.version_payload_sha256, "version payload digest")
        _require_sha256(self.models_payload_sha256, "models payload digest")
        if not isinstance(self.models, tuple) or not self.models:
            raise FormalRunError("endpoint observation must contain at least one model")
        if any(not isinstance(model, ObservedModel) for model in self.models):
            raise FormalRunError("endpoint models must use ObservedModel records")
        ids = [model.id for model in self.models]
        if len(ids) != len(set(ids)):
            raise FormalRunError("endpoint observation contains duplicate model ids")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ModelContentEvidence:
    """One observed model-directory fingerprint or explicitly declared content digest."""

    evidence_source: str
    sha256: str
    locator: str

    def __post_init__(self) -> None:
        if self.evidence_source not in {
            "observed-directory-fingerprint",
            "declared-content-digest",
        }:
            raise FormalRunError("unsupported model content evidence source")
        _require_sha256(self.sha256, "model content digest")
        if not isinstance(self.locator, str) or not self.locator:
            raise FormalRunError("model content locator must be non-empty")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RuntimeCommandEvidence:
    """Digest of the command line observed for the serving process."""

    evidence_source: str
    pid: int
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_source, str) or not self.evidence_source:
            raise FormalRunError("runtime command evidence source must be non-empty")
        if not isinstance(self.pid, int) or isinstance(self.pid, bool) or self.pid <= 0:
            raise FormalRunError("runtime PID must be a positive integer")
        _require_sha256(self.sha256, "runtime command digest")


@dataclass(frozen=True, slots=True)
class FormalRunDescriptor:
    """Immutable result of validating every identity needed for a formal run."""

    schema_version: int
    run_id: str
    split: str
    formal_eligible: bool
    ineligibility_reasons: tuple[str, ...]
    endpoint: str
    endpoint_observation: EndpointObservation
    registry_model_id: str
    registry_model_revision: str
    serving_profile_sha256: str
    api_profile_sha256: str
    model_content: ModelContentEvidence
    runtime_command: RuntimeCommandEvidence
    runtime_profile_sha256: str
    isolation: IsolationAttestation | None

    def _identity_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def descriptor_sha256(self) -> str:
        return _digest_json(self._identity_dict())

    def to_dict(self) -> dict[str, Any]:
        result = self._identity_dict()
        result["descriptor_sha256"] = self.descriptor_sha256
        if self.isolation is not None:
            result["isolation"]["attestation_sha256"] = self.isolation.attestation_sha256
            result["isolation"]["formal_failures"] = list(self.isolation.formal_failures)
        return result


def runtime_command_digest(command: Sequence[str]) -> str:
    """Hash an argv vector without persisting possibly sensitive command text."""

    if isinstance(command, (str, bytes)) or not command:
        raise FormalRunError("runtime command must be a non-empty argv sequence")
    normalized = tuple(command)
    if any(not isinstance(part, str) or not part or "\0" in part for part in normalized):
        raise FormalRunError("runtime command arguments must be non-empty strings without NUL")
    return _digest_json(normalized)


def observe_runtime_process(
    pid: int,
    *,
    proc_root: str | Path = "/proc",
) -> RuntimeCommandEvidence:
    """Hash the argv observed for one live runtime PID without persisting argv."""

    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        raise FormalRunError("runtime PID must be a positive integer")
    try:
        with (Path(proc_root) / str(pid) / "cmdline").open("rb") as handle:
            raw = handle.read(_MAX_OBSERVATION_BYTES + 1)
    except OSError as exc:
        raise FormalRunError(f"cannot observe runtime PID {pid}: {exc}") from exc
    if len(raw) > _MAX_OBSERVATION_BYTES:
        raise FormalRunError("runtime command line exceeds the 1 MiB limit")
    try:
        command = tuple(part.decode() for part in raw.rstrip(b"\0").split(b"\0"))
    except UnicodeDecodeError as exc:
        raise FormalRunError("runtime command line is not valid UTF-8") from exc
    if not command or command == ("",):
        raise FormalRunError("runtime process has an empty command line")
    return RuntimeCommandEvidence(
        evidence_source="observed-proc",
        pid=pid,
        sha256=runtime_command_digest(command),
    )


def _parse_json(payload: bytes, label: str) -> dict[str, object]:
    try:
        raw: object = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FormalRunError(f"runtime {label} response is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise FormalRunError(f"runtime {label} response must be an object")
    return raw


def observe_runtime_endpoint(
    endpoint: str,
    *,
    transport: EndpointTransport = _urlopen_transport,
    timeout_seconds: float = 10.0,
    observed_at: str | None = None,
) -> EndpointObservation:
    """Fetch live vLLM version and model-card observations without credentials."""

    canonical_endpoint = canonical_reader_endpoint(endpoint)
    parsed = urllib.parse.urlsplit(canonical_endpoint)
    origin = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    payloads: list[bytes] = []
    for path in ("/version", "/v1/models"):
        request = urllib.request.Request(origin + path, method="GET")
        payloads.append(transport(request, timeout_seconds))
    version_raw = _parse_json(payloads[0], "version")
    version = version_raw.get("version")
    if not isinstance(version, str) or not version:
        raise FormalRunError("runtime /version response has no version string")
    models_raw = _parse_json(payloads[1], "models")
    data = models_raw.get("data")
    if not isinstance(data, list) or not data:
        raise FormalRunError("runtime /v1/models response has no model records")
    models: list[ObservedModel] = []
    for item in data:
        if not isinstance(item, dict):
            raise FormalRunError("runtime /v1/models records must be objects")
        model_id = item.get("id")
        if not isinstance(model_id, str):
            raise FormalRunError("runtime /v1/models record has no string id")
        models.append(
            ObservedModel(
                id=model_id,
                root=item.get("root"),
                parent=item.get("parent"),
            )
        )
    timestamp = observed_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return EndpointObservation(
        evidence_source="live-http",
        observed_at=timestamp,
        endpoint=canonical_endpoint,
        version=version,
        version_payload_sha256=hashlib.sha256(payloads[0]).hexdigest(),
        models_payload_sha256=hashlib.sha256(payloads[1]).hexdigest(),
        models=tuple(models),
    )


def fingerprint_model_directory(path: str | Path) -> ModelContentEvidence:
    """Hash regular model files and relative paths without following symlinks."""

    root = Path(path).resolve()
    if not root.is_dir():
        raise FormalRunError("model directory does not exist")
    digest = hashlib.sha256(b"rsicontext-model-directory-v1\0")
    file_count = 0
    for candidate in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = candidate.relative_to(root).as_posix()
        if candidate.is_symlink():
            raise FormalRunError(f"model directory contains a symlink: {relative}")
        metadata = candidate.stat(follow_symlinks=False)
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise FormalRunError(f"model directory contains a non-regular file: {relative}")
        file_count += 1
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(str(metadata.st_size).encode())
        digest.update(b"\0")
        with candidate.open("rb") as handle:
            while block := handle.read(1024 * 1024):
                digest.update(block)
        after = candidate.stat(follow_symlinks=False)
        if (metadata.st_size, metadata.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise FormalRunError(f"model file changed while being fingerprinted: {relative}")
    if file_count == 0:
        raise FormalRunError("model directory contains no regular files")
    return ModelContentEvidence(
        evidence_source="observed-directory-fingerprint",
        sha256=digest.hexdigest(),
        locator=str(root),
    )


def _expected_model_roots(
    run_spec: RunSpec,
    registry_model: RegistryEntry,
    model_content: ModelContentEvidence,
) -> frozenset[str]:
    roots = {
        run_spec.model.model_id,
        registry_model.url.removeprefix("https://huggingface.co/").rstrip("/"),
    }
    if model_content.evidence_source == "observed-directory-fingerprint":
        roots.add(model_content.locator)
    return frozenset(roots)


def attest_run(
    *,
    run_spec: RunSpec,
    serving_profile: ServingProfile,
    reader_profile: APIProfile,
    registry_model: RegistryEntry,
    endpoint: str,
    endpoint_observation: EndpointObservation,
    model_content: ModelContentEvidence,
    runtime_command: RuntimeCommandEvidence,
    isolation: IsolationAttestation | None,
    qualification_only: bool = False,
) -> FormalRunDescriptor:
    """Validate a runtime descriptor, rejecting insufficient formal evidence."""

    try:
        validate_run_binding(run_spec, serving_profile, registry_model, reader_profile)
    except RegistryError as exc:
        raise FormalRunError(f"registered run binding failed: {exc}") from exc
    canonical_endpoint = canonical_reader_endpoint(endpoint)
    parsed = urllib.parse.urlsplit(canonical_endpoint)
    if parsed.hostname not in _LOCAL_HOSTS:
        raise FormalRunError("formal runtime endpoint must be local to the evaluator")
    if parsed.hostname != reader_profile.allowed_host.casefold():
        raise FormalRunError("runtime endpoint host differs from the API profile")
    if endpoint_observation.evidence_source != "live-http":
        raise FormalRunError("endpoint identity must come from a live HTTP observation")
    if endpoint_observation.endpoint != canonical_endpoint:
        raise FormalRunError("live endpoint observation does not match the requested endpoint")
    matching_models = tuple(
        model for model in endpoint_observation.models if model.id == reader_profile.model
    )
    if len(matching_models) != 1:
        raise FormalRunError("live model identity does not uniquely match the reader profile")
    observed_model = matching_models[0]
    if observed_model.root not in _expected_model_roots(run_spec, registry_model, model_content):
        raise FormalRunError("live model root does not match the registered model content")
    if observed_model.parent is not None:
        raise FormalRunError("formal reader must expose the registered model as a root model")
    if (
        registry_model.checksum.algorithm == "sha256"
        and registry_model.checksum.verified
        and registry_model.checksum.value != model_content.sha256
    ):
        raise FormalRunError("model content digest differs from the verified registry digest")
    if not qualification_only and runtime_command.evidence_source != "observed-proc":
        raise FormalRunError("formal runtime command must be observed from the runtime PID")
    runtime_profile_sha256 = _digest_json(
        {
            "api_profile_sha256": reader_profile.profile_hash,
            "command_sha256": runtime_command.sha256,
            "model_content_sha256": model_content.sha256,
            "runtime_version": endpoint_observation.version,
            "serving_profile_sha256": serving_profile.profile_hash,
        }
    )
    reasons: tuple[str, ...]
    if qualification_only:
        if run_spec.split is not Split.VISIBLE:
            raise FormalRunError("only a visible run may be explicitly marked as qualification")
        eligible = False
        reasons = ("visible qualification explicitly non-formal",)
    else:
        failures = (
            ("formal isolation attestation is missing",)
            if isolation is None
            else isolation.formal_failures
        )
        if failures:
            raise FormalRunError("formal isolation failed: " + "; ".join(failures))
        raise FormalRunError(
            "formal isolation must be issued by the scored policy-worker launcher; "
            "researcher/evaluator preflight evidence is insufficient"
        )
    return FormalRunDescriptor(
        schema_version=1,
        run_id=run_spec.run_id,
        split=run_spec.split.value,
        formal_eligible=eligible,
        ineligibility_reasons=reasons,
        endpoint=canonical_endpoint,
        endpoint_observation=endpoint_observation,
        registry_model_id=registry_model.id,
        registry_model_revision=run_spec.model.revision,
        serving_profile_sha256=serving_profile.profile_hash,
        api_profile_sha256=reader_profile.profile_hash,
        model_content=model_content,
        runtime_command=runtime_command,
        runtime_profile_sha256=runtime_profile_sha256,
        isolation=isolation,
    )


def write_formal_run_descriptor(descriptor: FormalRunDescriptor, path: str | Path) -> None:
    """Persist one immutable descriptor without replacing prior evidence."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(descriptor.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")
