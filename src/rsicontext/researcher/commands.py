"""Pure command builders for supported coding-researcher CLIs."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


class CommandBuildError(ValueError):
    """Raised when a researcher command cannot be represented safely."""


def _validate_cli_value(value: str, *, field: str) -> None:
    if not value or "\x00" in value or "\n" in value or "\r" in value:
        raise CommandBuildError(f"{field} must be a non-empty, single-line value")


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


@dataclass(frozen=True, slots=True)
class ResearcherRequest:
    """Inputs shared by Codex and Claude command builders."""

    workspace: Path
    prompt: str
    model: str | None = None
    output_schema: Path | None = None
    max_budget_usd: float | None = None

    def __post_init__(self) -> None:
        workspace = self.workspace.resolve()
        if not workspace.is_dir():
            raise CommandBuildError("workspace must be an existing directory")
        if not self.prompt.strip() or "\x00" in self.prompt:
            raise CommandBuildError("prompt must be non-empty and cannot contain NUL")
        if self.model is not None:
            _validate_cli_value(self.model, field="model")
        if self.output_schema is not None:
            schema = self.output_schema.resolve()
            if not schema.is_file() or not _within(schema, workspace):
                raise CommandBuildError("output_schema must be a file inside the workspace")
            object.__setattr__(self, "output_schema", schema)
        if self.max_budget_usd is not None and (
            isinstance(self.max_budget_usd, bool)
            or not isinstance(self.max_budget_usd, (int, float))
            or not math.isfinite(self.max_budget_usd)
            or self.max_budget_usd <= 0
        ):
            raise CommandBuildError("max_budget_usd must be finite and positive")
        object.__setattr__(self, "workspace", workspace)


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """An inert argv/cwd specification; it cannot execute a process."""

    argv: tuple[str, ...]
    cwd: Path
    output_format: Literal["jsonl", "stream-json"]
    stdin: str


@dataclass(frozen=True, slots=True)
class CodexCommandBuilder:
    """Build a non-interactive Codex JSONL invocation with safe defaults."""

    executable: str = "codex"
    sandbox: Literal["read-only", "workspace-write"] = "workspace-write"

    def __post_init__(self) -> None:
        _validate_cli_value(self.executable, field="executable")
        if self.sandbox not in {"read-only", "workspace-write"}:
            raise CommandBuildError("Codex sandbox must not bypass isolation")

    def build(self, request: ResearcherRequest) -> CommandSpec:
        """Return argv only; callers must separately authorize execution."""

        if request.max_budget_usd is not None:
            raise CommandBuildError("Codex CLI has no supported max-budget flag")
        workspace = request.workspace.resolve()
        argv = [
            self.executable,
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--strict-config",
            "--sandbox",
            self.sandbox,
            "--cd",
            str(workspace),
        ]
        if request.model is not None:
            argv.extend(("--model", request.model))
        if request.output_schema is not None:
            argv.extend(("--output-schema", str(request.output_schema.resolve())))
        argv.append("-")
        return CommandSpec(tuple(argv), workspace, "jsonl", request.prompt)


@dataclass(frozen=True, slots=True)
class ClaudeCommandBuilder:
    """Build a non-interactive Claude stream-json invocation.

    The tool allowlist intentionally excludes Bash, web access, MCP, and
    subagents. This adapter is for bounded policy-file editing, not evaluation.
    """

    executable: str = "claude"
    allowed_tools: tuple[str, ...] = ("Read", "Edit", "Write", "Glob", "Grep")

    def __post_init__(self) -> None:
        _validate_cli_value(self.executable, field="executable")
        if not self.allowed_tools or any(
            not tool or any(char in tool for char in "\x00\n\r,") for tool in self.allowed_tools
        ):
            raise CommandBuildError("Claude allowed_tools contains an invalid tool name")
        safe_tools = {"Read", "Edit", "Write", "Glob", "Grep"}
        if not set(self.allowed_tools).issubset(safe_tools):
            raise CommandBuildError("Claude allowed_tools grants an out-of-scope capability")

    def build(self, request: ResearcherRequest) -> CommandSpec:
        """Return argv only; callers must separately authorize execution."""

        workspace = request.workspace.resolve()
        argv = [
            self.executable,
            "--print",
            "--output-format",
            "stream-json",
            "--no-session-persistence",
            "--safe-mode",
            "--permission-mode",
            "dontAsk",
            "--strict-mcp-config",
            "--mcp-config",
            "{}",
            "--tools",
            ",".join(self.allowed_tools),
        ]
        if request.model is not None:
            argv.extend(("--model", request.model))
        if request.max_budget_usd is not None:
            argv.extend(("--max-budget-usd", format(request.max_budget_usd, ".12g")))
        if request.output_schema is not None:
            try:
                schema: object = json.loads(request.output_schema.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise CommandBuildError("output_schema is not valid JSON") from exc
            if not isinstance(schema, dict):
                raise CommandBuildError("output_schema root must be a JSON object")
            argv.extend(
                (
                    "--json-schema",
                    json.dumps(schema, allow_nan=False, separators=(",", ":"), sort_keys=True),
                )
            )
        return CommandSpec(tuple(argv), workspace, "stream-json", request.prompt)
