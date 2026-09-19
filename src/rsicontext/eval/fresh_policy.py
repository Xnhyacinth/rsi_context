"""Fresh-process execution bridge for audited context-policy bundles.

This module provides process freshness, not filesystem or network confidentiality.
Cleanup covers processes that remain in the worker-created process group; descendants
can escape it with ``setsid``. Formal sealed evaluation must additionally run the
worker in a locked-down container or node with cgroup or PID-namespace ownership that
cannot reach evaluator-only data or external services.
"""

from __future__ import annotations

import json
import math
import os
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from rsicontext.policy import (
    Artifact,
    Budget,
    CompressedNote,
    ContextPack,
    ContextPolicy,
    DocumentChunk,
)
from rsicontext.security import PolicyAuditor, allowed_local_imports

_WORKER_ENVIRONMENT = {
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "PYTHONHASHSEED": "0",
    "PYTHONIOENCODING": "utf-8",
}


class PolicyProcessError(RuntimeError):
    """A fresh policy process could not produce a usable result."""


class PolicyProcessTimeout(PolicyProcessError):
    """A policy process exceeded its evaluator-owned wall-time limit."""


class PolicyProtocolError(PolicyProcessError):
    """A child response violated the bounded JSON protocol."""


class PolicyBundleError(ValueError):
    """A policy directory could not become an immutable audited bundle."""


@dataclass(frozen=True, slots=True, init=False)
class AuditedPolicyBundle:
    """Exact audited Python bytes plus a fixed loader entrypoint."""

    files: tuple[tuple[str, bytes], ...]
    entrypoint: str
    policy_class: str

    @classmethod
    def from_directory(
        cls,
        root: str | Path,
        *,
        auditor: PolicyAuditor | None = None,
        entrypoint: str = "policy.py",
        policy_class: str = "Policy",
    ) -> AuditedPolicyBundle:
        """Audit a tree and copy the exact re-audited bytes into immutable memory."""

        checked_entrypoint = _safe_relative_python_path(entrypoint)
        if not policy_class.isidentifier() or policy_class.startswith("_"):
            raise PolicyBundleError("policy_class must be a public Python identifier")
        active_auditor = auditor or PolicyAuditor()
        active_auditor.audit_tree(root).require_safe()
        policy_root = Path(root)
        try:
            resolved_root = policy_root.resolve(strict=True)
        except OSError as exc:
            raise PolicyBundleError("policy root does not exist") from exc
        if policy_root.is_symlink() or not resolved_root.is_dir():
            raise PolicyBundleError("policy root must be a regular directory")

        files: list[tuple[str, bytes]] = []
        for path in sorted(resolved_root.rglob("*")):
            relative = path.relative_to(resolved_root).as_posix()
            if path.is_symlink():
                raise PolicyBundleError(f"policy bundle contains a symlink: {relative}")
            if path.is_dir():
                continue
            if not path.is_file() or path.suffix != ".py":
                raise PolicyBundleError(f"policy bundle contains a non-Python file: {relative}")
            content = path.read_bytes()
            if len(content) > active_auditor.capabilities.max_file_bytes:
                raise PolicyBundleError("policy bundle exceeds the audited file-size limit")
            try:
                content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise PolicyBundleError(f"policy file is not UTF-8: {relative}") from exc
            files.append((relative, content))

        if not files:
            raise PolicyBundleError("policy bundle must contain at least one Python file")
        if len(files) > active_auditor.capabilities.max_files:
            raise PolicyBundleError("policy bundle exceeds the audited file-count limit")
        extra_imports = allowed_local_imports(relative for relative, _ in files)
        for relative, content in files:
            active_auditor.audit_source(
                content.decode("utf-8"),
                filename=str(resolved_root / relative),
                extra_allowed_imports=extra_imports,
            ).require_safe()
        if checked_entrypoint not in {path for path, _ in files}:
            raise PolicyBundleError(f"policy entrypoint is missing: {checked_entrypoint}")

        bundle = object.__new__(cls)
        object.__setattr__(bundle, "files", tuple(files))
        object.__setattr__(bundle, "entrypoint", checked_entrypoint)
        object.__setattr__(bundle, "policy_class", policy_class)
        return bundle


@dataclass(frozen=True, slots=True)
class FreshProcessPolicyFactory:
    """Create policies whose every assembly runs in a new Python interpreter."""

    bundle: AuditedPolicyBundle
    timeout_seconds: float = 10.0
    max_output_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be finite and positive")
        if (
            not isinstance(self.max_output_bytes, int)
            or isinstance(self.max_output_bytes, bool)
            or self.max_output_bytes <= 0
        ):
            raise ValueError("max_output_bytes must be a positive integer")

    def __call__(self) -> ContextPolicy:
        return _FreshProcessPolicy(
            self.bundle,
            timeout_seconds=float(self.timeout_seconds),
            max_output_bytes=self.max_output_bytes,
        )


@dataclass(frozen=True, slots=True)
class _FreshProcessPolicy:
    bundle: AuditedPolicyBundle
    timeout_seconds: float
    max_output_bytes: int

    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        if not isinstance(query, str):
            raise TypeError("query must be a string")
        request = _encode_request(artifact, query, budget)
        with tempfile.TemporaryDirectory(prefix="rsicontext-policy-") as raw_directory:
            policy_root = Path(raw_directory)
            _materialize(self.bundle, policy_root)
            response = _run_worker(
                policy_root,
                self.bundle,
                request,
                timeout_seconds=self.timeout_seconds,
                max_output_bytes=self.max_output_bytes,
            )
        try:
            context = _decode_context(response)
            context.validate(artifact, budget)
        except (TypeError, ValueError) as exc:
            raise PolicyProtocolError(f"invalid ContextPack: {exc}") from exc
        return context


def _safe_relative_python_path(raw_path: str) -> str:
    path = PurePosixPath(raw_path)
    if (
        not raw_path
        or path.is_absolute()
        or path.suffix != ".py"
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise PolicyBundleError("entrypoint must be a safe relative .py path")
    return path.as_posix()


def _materialize(bundle: AuditedPolicyBundle, root: Path) -> None:
    for relative, content in bundle.files:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)


def _run_worker(
    policy_root: Path,
    bundle: AuditedPolicyBundle,
    request: bytes,
    *,
    timeout_seconds: float,
    max_output_bytes: int,
) -> bytes:
    command = (
        sys.executable,
        "-I",
        "-B",
        "-m",
        "rsicontext.eval._policy_worker",
        str(policy_root),
        bundle.entrypoint,
        bundle.policy_class,
    )
    with tempfile.TemporaryFile() as stdin:
        stdin.write(request)
        stdin.seek(0)
        try:
            process = subprocess.Popen(
                command,
                cwd=policy_root,
                env=_WORKER_ENVIRONMENT,
                stdin=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
                start_new_session=True,
            )
        except OSError as exc:
            raise PolicyProcessError("could not start fresh policy process") from exc

        deadline = time.monotonic() + timeout_seconds
        try:
            stdout, stderr = _capture_worker_output(
                process,
                deadline=deadline,
                max_output_bytes=max_output_bytes,
            )
        finally:
            _kill_worker_group(process)
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()

        if process.returncode != 0:
            diagnostic = stderr.decode("utf-8", errors="replace").strip()
            suffix = f": {diagnostic}" if diagnostic else ""
            raise PolicyProcessError(
                f"policy process exited non-zero ({process.returncode}){suffix}"
            )
        return stdout


def _capture_worker_output(
    process: subprocess.Popen[bytes],
    *,
    deadline: float,
    max_output_bytes: int,
) -> tuple[bytes, bytes]:
    if process.stdout is None or process.stderr is None:
        raise RuntimeError("policy worker pipes were not created")
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    try:
        while selector.get_map():
            if process.poll() is not None:
                _signal_worker_group(process)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PolicyProcessTimeout("policy process timed out")
            for key, _ in selector.select(min(remaining, 0.1)):
                stream = key.data
                if not isinstance(stream, str):
                    raise RuntimeError("unexpected selector metadata")
                captured = sum(len(value) for value in buffers.values())
                read_size = min(64 * 1024, max_output_bytes + 1 - captured)
                chunk = os.read(key.fd, read_size)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffers[stream].extend(chunk)
                if sum(len(value) for value in buffers.values()) > max_output_bytes:
                    raise PolicyProtocolError("policy process exceeded the output limit")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PolicyProcessTimeout("policy process timed out")
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            raise PolicyProcessTimeout("policy process timed out") from exc
    finally:
        selector.close()
    return bytes(buffers["stdout"]), bytes(buffers["stderr"])


def _kill_worker_group(process: subprocess.Popen[bytes]) -> None:
    # A group may retain redirected background children after its leader exits.
    _signal_worker_group(process)
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _signal_worker_group(process: subprocess.Popen[bytes]) -> None:
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)


def _encode_request(artifact: Artifact, query: str, budget: Budget) -> bytes:
    payload = {
        "artifact": {
            "chunks": [_encode_chunk(chunk) for chunk in artifact.chunks],
            "document_id": artifact.document_id,
            "notes": [_encode_note(note) for note in artifact.notes],
        },
        "budget": {
            "max_chunks": budget.max_chunks,
            "max_free_text_tokens": budget.max_free_text_tokens,
            "max_tokens": budget.max_tokens,
        },
        "query": query,
    }
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _decode_request(payload: bytes) -> tuple[Artifact, str, Budget]:
    raw = _decode_json_object(payload, "request")
    _require_keys(raw, {"artifact", "budget", "query"}, "request")
    artifact_raw = _require_mapping(raw["artifact"], "artifact")
    _require_keys(artifact_raw, {"chunks", "document_id", "notes"}, "artifact")
    chunks_raw = _require_list(artifact_raw["chunks"], "artifact.chunks")
    notes_raw = _require_list(artifact_raw["notes"], "artifact.notes")
    artifact = Artifact(
        document_id=_require_string(artifact_raw["document_id"], "artifact.document_id"),
        chunks=tuple(_decode_chunk(value) for value in chunks_raw),
        notes=tuple(_decode_note(value) for value in notes_raw),
    )
    query = raw["query"]
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    budget_raw = _require_mapping(raw["budget"], "budget")
    _require_keys(
        budget_raw,
        {"max_chunks", "max_free_text_tokens", "max_tokens"},
        "budget",
    )
    budget = Budget(
        max_tokens=_require_integer(budget_raw["max_tokens"], "budget.max_tokens"),
        max_free_text_tokens=_require_integer(
            budget_raw["max_free_text_tokens"], "budget.max_free_text_tokens"
        ),
        max_chunks=_require_optional_integer(budget_raw["max_chunks"], "budget.max_chunks"),
    )
    return artifact, query, budget


def _encode_context(context: ContextPack) -> bytes:
    payload = {
        "abstain": context.abstain,
        "notes": [_encode_note(note) for note in context.notes],
        "ordering": list(context.ordering),
        "request_reread": context.request_reread,
        "spans": [_encode_chunk(span) for span in context.spans],
        "token_count": context.token_count,
    }
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _decode_context(payload: bytes) -> ContextPack:
    raw = _decode_json_object(payload, "response")
    _require_keys(
        raw,
        {"abstain", "notes", "ordering", "request_reread", "spans", "token_count"},
        "response",
    )
    return ContextPack(
        spans=tuple(
            _decode_chunk(value) for value in _require_list(raw["spans"], "response.spans")
        ),
        notes=tuple(_decode_note(value) for value in _require_list(raw["notes"], "response.notes")),
        ordering=tuple(_require_string_list(raw["ordering"], "response.ordering")),
        token_count=_require_integer(raw["token_count"], "response.token_count"),
        abstain=_require_boolean(raw["abstain"], "response.abstain"),
        request_reread=_require_optional_string(raw["request_reread"], "response.request_reread"),
    )


def _encode_chunk(chunk: DocumentChunk) -> dict[str, object]:
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "end": chunk.end,
        "role": chunk.role,
        "start": chunk.start,
        "text": chunk.text,
        "token_count": chunk.token_count,
    }


def _decode_chunk(value: object) -> DocumentChunk:
    raw = _require_mapping(value, "chunk")
    _require_keys(
        raw,
        {"chunk_id", "document_id", "end", "role", "start", "text", "token_count"},
        "chunk",
    )
    return DocumentChunk(
        chunk_id=_require_string(raw["chunk_id"], "chunk.chunk_id"),
        document_id=_require_string(raw["document_id"], "chunk.document_id"),
        start=_require_integer(raw["start"], "chunk.start"),
        end=_require_integer(raw["end"], "chunk.end"),
        text=_require_string(raw["text"], "chunk.text"),
        token_count=_require_integer(raw["token_count"], "chunk.token_count"),
        role=_require_string(raw["role"], "chunk.role"),
    )


def _encode_note(note: CompressedNote) -> dict[str, object]:
    return {
        "note_id": note.note_id,
        "source_chunk_ids": list(note.source_chunk_ids),
        "text": note.text,
        "token_count": note.token_count,
    }


def _decode_note(value: object) -> CompressedNote:
    raw = _require_mapping(value, "note")
    _require_keys(raw, {"note_id", "source_chunk_ids", "text", "token_count"}, "note")
    return CompressedNote(
        note_id=_require_string(raw["note_id"], "note.note_id"),
        source_chunk_ids=tuple(
            _require_string_list(raw["source_chunk_ids"], "note.source_chunk_ids")
        ),
        text=_require_string(raw["text"], "note.text"),
        token_count=_require_integer(raw["token_count"], "note.token_count"),
    )


def _decode_json_object(payload: bytes, label: str) -> Mapping[str, object]:
    try:
        text = payload.decode("utf-8")
        value: object = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda value: _raise_invalid_constant(value),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise PolicyProtocolError(f"{label} is not valid JSON") from exc
    return _require_mapping(value, label)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _raise_invalid_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _require_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise TypeError(f"{label} must be an object")
    return value


def _require_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be an array")
    return value


def _require_string_list(value: object, label: str) -> list[str]:
    values = _require_list(value, label)
    if any(not isinstance(item, str) for item in values):
        raise TypeError(f"{label} must contain only strings")
    return [item for item in values if isinstance(item, str)]


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    return value


def _require_optional_string(value: object, label: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise TypeError(f"{label} must be a string or null")
    return value


def _require_integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{label} must be an integer")
    return value


def _require_optional_integer(value: object, label: str) -> int | None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
        raise TypeError(f"{label} must be an integer or null")
    return value


def _require_boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{label} must be a boolean")
    return value


def _require_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{label} has unexpected fields")
