"""Bounded local-process execution for inert researcher command specifications.

This module constrains one subprocess invocation. It is not an OS sandbox and
does not provide filesystem or network confidentiality against a malicious
executable. Cleanup covers processes that remain in the runner-created process
group; descendants can escape it with ``setsid``. Sealed evaluation therefore
requires a locked-down container or node with cgroup or PID-namespace ownership.
"""

from __future__ import annotations

import math
import os
import re
import selectors
import signal
import subprocess
import tempfile
import time
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass

from .commands import CommandSpec
from .streams import (
    NormalizedEvent,
    StreamFormatError,
    TokenUsage,
    normalize_claude_stream_json,
    normalize_codex_jsonl,
)


class ResearcherProcessError(RuntimeError):
    """Raised when execution or the researcher completion protocol fails."""

    def __init__(self, message: str, *, stdout: bytes = b"", stderr: bytes = b"") -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr


_MAX_FAILURE_DIAGNOSTIC_CHARS = 400
_FAILURE_DIAGNOSTIC_LINE = re.compile(r"(?:Error|Exception|Timeout): ")


def researcher_failure_diagnostic(
    message: str,
    stderr: bytes,
    *,
    max_chars: int = _MAX_FAILURE_DIAGNOSTIC_CHARS,
) -> str:
    """Return a one-line exception diagnostic without dumping raw stderr secrets."""

    if not isinstance(message, str) or not message.strip():
        raise ValueError("failure message must be a non-empty string")
    if not isinstance(stderr, bytes):
        raise TypeError("stderr must be bytes")
    if not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars < 1:
        raise ValueError("max_chars must be a positive integer")
    chosen = message.strip()
    text = stderr.decode("utf-8", errors="replace")
    for raw_line in reversed(text.splitlines()):
        line = raw_line.strip()
        if line.startswith("policy worker failed:") or _FAILURE_DIAGNOSTIC_LINE.search(line):
            if line.startswith("During handling"):
                continue
            chosen = line
            break
    chosen = " ".join(chosen.split())
    if len(chosen) > max_chars:
        chosen = chosen[:max_chars]
    return chosen


@dataclass(frozen=True, slots=True)
class ProcessLimits:
    """Wall-clock and captured-output limits for one researcher process."""

    timeout_seconds: float = 1800.0
    max_line_bytes: int = 16 * 1024 * 1024
    max_stdout_bytes: int = 32 * 1024 * 1024
    max_stderr_bytes: int = 2 * 1024 * 1024
    max_total_bytes: int = 34 * 1024 * 1024

    def __post_init__(self) -> None:
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be finite and positive")
        for name in (
            "max_line_bytes",
            "max_stdout_bytes",
            "max_stderr_bytes",
            "max_total_bytes",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class ResearcherProcessResult:
    """Normalized successful output and CLI-reported usage for one invocation."""

    events: tuple[NormalizedEvent, ...]
    usage: TokenUsage
    stderr: str
    returncode: int
    elapsed_seconds: float
    stdout_bytes: int
    stderr_bytes: int


_BASE_ENVIRONMENT = {
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "PYTHONIOENCODING": "utf-8",
}
_ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_UNSAFE_ENVIRONMENT_NAMES = {
    "BASH_ENV",
    "ENV",
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "NODE_OPTIONS",
    "PYTHONHOME",
    "PYTHONPATH",
}


def run_researcher_process(
    spec: CommandSpec,
    *,
    limits: ProcessLimits,
    environment_allowlist: Iterable[str] = (),
) -> ResearcherProcessResult:
    """Execute one fixed command without a shell and require a valid completion."""

    _validate_spec(spec)
    environment = _minimal_environment(environment_allowlist)
    prompt = spec.stdin.encode("utf-8")
    started = time.monotonic()

    with tempfile.TemporaryFile() as stdin_file:
        stdin_file.write(prompt)
        stdin_file.seek(0)
        try:
            process = subprocess.Popen(
                spec.argv,
                cwd=spec.cwd,
                env=environment,
                stdin=stdin_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
            )
        except OSError as exc:
            raise ResearcherProcessError("researcher process could not be started") from exc

        try:
            stdout, stderr = _capture_output(process, limits=limits, started=started)
        finally:
            _kill_process_group(process)
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()

    elapsed = time.monotonic() - started
    if process.returncode != 0:
        raise ResearcherProcessError(
            f"researcher process exited with status {process.returncode}",
            stdout=stdout,
            stderr=stderr,
        )
    stdout_text = _decode_output(stdout, stream="stdout")
    stderr_text = _decode_output(stderr, stream="stderr")
    events = _normalize_output(spec, stdout_text)
    usage = _require_successful_completion(events)
    return ResearcherProcessResult(
        events=events,
        usage=usage,
        stderr=stderr_text,
        returncode=process.returncode,
        elapsed_seconds=elapsed,
        stdout_bytes=len(stdout),
        stderr_bytes=len(stderr),
    )


def _validate_spec(spec: CommandSpec) -> None:
    if not spec.argv or any(
        not isinstance(argument, str) or not argument or "\x00" in argument
        for argument in spec.argv
    ):
        raise ResearcherProcessError("researcher argv contains an invalid value")
    if not spec.cwd.is_dir():
        raise ResearcherProcessError("researcher cwd must be an existing directory")
    if "\x00" in spec.stdin:
        raise ResearcherProcessError("researcher stdin cannot contain NUL")
    if spec.output_format not in {"jsonl", "stream-json"}:
        raise ResearcherProcessError("researcher output format is unsupported")


def _minimal_environment(allowlist: Iterable[str]) -> dict[str, str]:
    environment = dict(_BASE_ENVIRONMENT)
    for name in allowlist:
        if not isinstance(name, str) or _ENVIRONMENT_NAME.fullmatch(name) is None:
            raise ResearcherProcessError("environment allowlist contains an invalid name")
        if (
            name in _BASE_ENVIRONMENT
            or name in _UNSAFE_ENVIRONMENT_NAMES
            or name.startswith("DYLD_")
        ):
            raise ResearcherProcessError(f"environment allowlist contains unsafe name: {name}")
        try:
            value = os.environ[name]
        except KeyError as exc:
            raise ResearcherProcessError(
                f"allowlisted environment variable is not set: {name}"
            ) from exc
        if "\x00" in value:
            raise ResearcherProcessError(f"allowlisted environment variable contains NUL: {name}")
        environment[name] = value
    return environment


def _capture_output(
    process: subprocess.Popen[bytes], *, limits: ProcessLimits, started: float
) -> tuple[bytes, bytes]:
    if process.stdout is None or process.stderr is None:
        raise RuntimeError("researcher process pipes were not created")
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    line_lengths = {"stdout": 0, "stderr": 0}
    try:
        while selector.get_map():
            if process.poll() is not None:
                _signal_process_group(process)
            remaining = limits.timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise ResearcherProcessError("researcher process timed out")
            for key, _ in selector.select(min(remaining, 0.1)):
                stream = key.data
                if not isinstance(stream, str):
                    raise RuntimeError("unexpected selector metadata")
                try:
                    chunk = os.read(key.fd, 64 * 1024)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                _append_output(
                    stream,
                    chunk,
                    buffers=buffers,
                    line_lengths=line_lengths,
                    limits=limits,
                )
        remaining = limits.timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise ResearcherProcessError("researcher process timed out")
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            raise ResearcherProcessError("researcher process timed out") from exc
    finally:
        selector.close()
    return bytes(buffers["stdout"]), bytes(buffers["stderr"])


def _append_output(
    stream: str,
    chunk: bytes,
    *,
    buffers: dict[str, bytearray],
    line_lengths: dict[str, int],
    limits: ProcessLimits,
) -> None:
    buffer = buffers[stream]
    buffer.extend(chunk)
    stream_limit = limits.max_stdout_bytes if stream == "stdout" else limits.max_stderr_bytes
    if len(buffer) > stream_limit:
        raise ResearcherProcessError(f"researcher {stream} exceeds its byte limit")
    if sum(len(value) for value in buffers.values()) > limits.max_total_bytes:
        raise ResearcherProcessError("researcher total output exceeds its byte limit")

    parts = chunk.split(b"\n")
    first_length = line_lengths[stream] + len(parts[0])
    if first_length > limits.max_line_bytes:
        raise ResearcherProcessError(f"researcher {stream} line exceeds its byte limit")
    if len(parts) == 1:
        line_lengths[stream] = first_length
        return
    if any(len(part) > limits.max_line_bytes for part in parts[1:-1]):
        raise ResearcherProcessError(f"researcher {stream} line exceeds its byte limit")
    line_lengths[stream] = len(parts[-1])


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    # The group can outlive an already-reaped leader when a researcher leaves
    # redirected background children behind, so signal it unconditionally.
    _signal_process_group(process)
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _signal_process_group(process: subprocess.Popen[bytes]) -> None:
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)


def _decode_output(value: bytes, *, stream: str) -> str:
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ResearcherProcessError(f"researcher {stream} is not valid UTF-8") from exc


def _normalize_output(spec: CommandSpec, stdout: str) -> tuple[NormalizedEvent, ...]:
    normalizer = (
        normalize_codex_jsonl if spec.output_format == "jsonl" else normalize_claude_stream_json
    )
    try:
        return tuple(normalizer(stdout.splitlines()))
    except StreamFormatError as exc:
        raise ResearcherProcessError(f"invalid researcher output: {exc}") from exc


def _require_successful_completion(events: tuple[NormalizedEvent, ...]) -> TokenUsage:
    if any(event.kind == "error" for event in events):
        raise ResearcherProcessError("researcher output contains an error event")
    completions = [event for event in events if event.kind == "complete"]
    if len(completions) != 1:
        raise ResearcherProcessError("researcher output must contain exactly one completion")
    completion = completions[0]
    if not events or events[-1] is not completion:
        raise ResearcherProcessError("researcher completion must be the final event")
    if completion.usage is None:
        raise ResearcherProcessError("researcher completion is missing usage")
    return completion.usage
