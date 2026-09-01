"""Safe researcher CLI specifications, execution, and output normalization."""

from .commands import (
    ClaudeCommandBuilder,
    CodexCommandBuilder,
    CommandBuildError,
    CommandSpec,
    ResearcherRequest,
)
from .process import (
    ProcessLimits,
    ResearcherProcessError,
    ResearcherProcessResult,
    researcher_failure_diagnostic,
    run_researcher_process,
)
from .streams import (
    NormalizedEvent,
    StreamFormatError,
    TokenUsage,
    normalize_claude_stream_json,
    normalize_codex_jsonl,
)

__all__ = [
    "ClaudeCommandBuilder",
    "CodexCommandBuilder",
    "CommandBuildError",
    "CommandSpec",
    "NormalizedEvent",
    "ProcessLimits",
    "ResearcherProcessError",
    "ResearcherProcessResult",
    "ResearcherRequest",
    "StreamFormatError",
    "TokenUsage",
    "normalize_claude_stream_json",
    "normalize_codex_jsonl",
    "researcher_failure_diagnostic",
    "run_researcher_process",
]
