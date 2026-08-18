import json
from pathlib import Path

import pytest

from rsicontext.researcher import (
    ClaudeCommandBuilder,
    CodexCommandBuilder,
    CommandBuildError,
    ResearcherRequest,
    StreamFormatError,
    normalize_claude_stream_json,
    normalize_codex_jsonl,
)


def test_codex_builder_returns_inert_jsonl_argv(tmp_path: Path) -> None:
    request = ResearcherRequest(workspace=tmp_path, prompt="Edit policy/select.py", model="model-x")
    spec = CodexCommandBuilder().build(request)

    assert spec.cwd == tmp_path.resolve()
    assert spec.output_format == "jsonl"
    assert spec.argv[:3] == ("codex", "exec", "--json")
    assert "--ephemeral" in spec.argv
    assert "--ignore-user-config" in spec.argv
    assert "--ignore-rules" in spec.argv
    assert "workspace-write" in spec.argv
    assert "dangerously-bypass-approvals-and-sandbox" not in " ".join(spec.argv)
    assert spec.argv[-1] == "-"
    assert spec.stdin == request.prompt
    assert request.prompt not in spec.argv


def test_claude_builder_disables_persistence_mcp_and_shell(tmp_path: Path) -> None:
    schema = tmp_path / "schema.json"
    schema.write_text('{"type":"object"}', encoding="utf-8")
    request = ResearcherRequest(
        workspace=tmp_path,
        prompt="Edit policy/select.py",
        model="sonnet",
        output_schema=schema,
        max_budget_usd=2.5,
    )
    spec = ClaudeCommandBuilder().build(request)

    joined = " ".join(spec.argv)
    assert spec.output_format == "stream-json"
    assert "--no-session-persistence" in spec.argv
    assert "--safe-mode" in spec.argv
    assert "--strict-mcp-config" in spec.argv
    assert "Bash" not in joined
    assert "dangerously-skip-permissions" not in joined
    assert spec.stdin == request.prompt
    assert request.prompt not in spec.argv


def test_builders_reject_unbounded_or_out_of_workspace_options(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-schema.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(CommandBuildError, match="inside"):
        ResearcherRequest(workspace=tmp_path, prompt="work", output_schema=outside)

    budgeted = ResearcherRequest(workspace=tmp_path, prompt="work", max_budget_usd=1.0)
    with pytest.raises(CommandBuildError, match="max-budget"):
        CodexCommandBuilder().build(budgeted)
    with pytest.raises(CommandBuildError, match="capability"):
        ClaudeCommandBuilder(allowed_tools=("Read", "Bash"))
    with pytest.raises(CommandBuildError, match="capability"):
        ClaudeCommandBuilder(allowed_tools=("Read", "Bash(*)"))
    with pytest.raises(CommandBuildError, match="max_budget_usd"):
        ResearcherRequest(workspace=tmp_path, prompt="work", max_budget_usd=True)


@pytest.mark.parametrize(
    "prompt",
    ["--dangerously-bypass-approvals-and-sandbox", "--dangerously-skip-permissions"],
)
def test_prompts_are_passed_via_stdin_not_parsed_as_options(tmp_path: Path, prompt: str) -> None:
    request = ResearcherRequest(workspace=tmp_path, prompt=prompt)

    codex = CodexCommandBuilder().build(request)
    claude = ClaudeCommandBuilder().build(request)

    assert prompt not in codex.argv and codex.stdin == prompt
    assert prompt not in claude.argv and claude.stdin == prompt


def test_request_freezes_resolved_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    schema = workspace / "schema.json"
    schema.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    request = ResearcherRequest(
        workspace=Path("workspace"), prompt="work", output_schema=Path("workspace/schema.json")
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert CodexCommandBuilder().build(request).cwd == workspace.resolve()
    assert request.output_schema == schema.resolve()


def test_codex_jsonl_normalization_preserves_messages_tools_and_usage() -> None:
    lines = [
        json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
        json.dumps(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "implemented"},
            }
        ),
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "status": "completed",
                    "aggregated_output": "tests pass",
                },
            }
        ),
        json.dumps(
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 10, "output_tokens": 4},
            }
        ),
    ]
    events = list(normalize_codex_jsonl(lines))

    assert [event.kind for event in events] == ["session", "message", "tool_result", "complete"]
    assert events[1].text == "implemented"
    assert events[2].tool_name == "command_execution"
    assert events[-1].usage is not None
    assert events[-1].usage.input_tokens == 10


def test_claude_stream_json_normalization_handles_blocks_deltas_and_result() -> None:
    lines = [
        json.dumps({"type": "system", "subtype": "init", "session_id": "session-1"}),
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "editing"},
                        {"type": "tool_use", "name": "Edit", "input": {}},
                    ]
                },
            }
        ),
        json.dumps(
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": " done"},
                },
            }
        ),
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "result": "complete",
                "usage": {
                    "cache_creation_input_tokens": 7,
                    "cache_read_input_tokens": 3,
                    "input_tokens": 11,
                    "output_tokens": 5,
                },
                "total_cost_usd": 0.02,
            }
        ),
    ]
    events = list(normalize_claude_stream_json(lines))

    assert [event.kind for event in events] == [
        "session",
        "message",
        "tool_call",
        "message_delta",
        "complete",
    ]
    assert events[2].tool_name == "Edit"
    assert events[-1].usage is not None
    assert events[-1].usage.cost_usd == 0.02
    assert events[-1].usage.cache_creation_input_tokens == 7
    assert events[-1].usage.cached_input_tokens == 3
    assert events[-1].usage.total_input_tokens == 21


def test_normalizers_fail_closed_on_malformed_json() -> None:
    with pytest.raises(StreamFormatError, match="line 1"):
        list(normalize_codex_jsonl(["not-json"]))
    with pytest.raises(StreamFormatError, match="object"):
        list(normalize_claude_stream_json(["[]"]))
    with pytest.raises(StreamFormatError, match="duplicate"):
        list(normalize_codex_jsonl(['{"type":"error","type":"result"}']))
    with pytest.raises(StreamFormatError, match="non-finite"):
        list(normalize_claude_stream_json(['{"type":"result","total_cost_usd":NaN}']))
    with pytest.raises(StreamFormatError, match="input_tokens"):
        list(
            normalize_codex_jsonl(
                [json.dumps({"type": "turn.completed", "usage": {"input_tokens": -1}})]
            )
        )
    with pytest.raises(StreamFormatError, match="usage"):
        list(normalize_codex_jsonl([json.dumps({"type": "turn.completed"})]))
    with pytest.raises(StreamFormatError, match="usage"):
        list(
            normalize_claude_stream_json(
                [json.dumps({"type": "result", "subtype": "success", "result": "done"})]
            )
        )
