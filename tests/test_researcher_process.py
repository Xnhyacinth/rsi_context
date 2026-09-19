import json
import time
from pathlib import Path

import pytest

from rsicontext.researcher import (
    CommandSpec,
    ProcessLimits,
    ResearcherProcessError,
    researcher_failure_diagnostic,
    run_researcher_process,
)


def _fake_executable(tmp_path: Path, body: str) -> Path:
    executable = tmp_path / "fake-researcher"
    executable.write_text("#!/usr/bin/python3\n" + body, encoding="utf-8")
    executable.chmod(0o700)
    return executable


def _codex_spec(
    executable: Path, workspace: Path, *, stdin: str = "research prompt"
) -> CommandSpec:
    return CommandSpec(
        argv=(str(executable), "literal;not-shell", "$(still-not-shell)"),
        cwd=workspace,
        output_format="jsonl",
        stdin=stdin,
    )


def _assert_process_stopped(pid_file: Path) -> None:
    pid = int(pid_file.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            state = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()[2]
        except FileNotFoundError:
            return
        if state == "Z":
            return
        time.sleep(0.01)
    pytest.fail(f"background process {pid} survived researcher cleanup")


def test_process_executes_fixed_spec_with_minimal_allowlisted_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable = _fake_executable(
        tmp_path,
        """
import json
import os
import sys

observed = {
    "argv": sys.argv[1:],
    "cwd": os.getcwd(),
    "environment": sorted(os.environ),
    "prompt": sys.stdin.read(),
    "secret": os.environ.get("RSICONTEXT_TEST_CREDENTIAL"),
}
print(json.dumps({
    "type": "item.completed",
    "item": {"type": "agent_message", "text": json.dumps(observed)},
}))
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 17, "output_tokens": 5}}))
""",
    )
    monkeypatch.setenv("RSICONTEXT_TEST_CREDENTIAL", "allowed-secret")
    monkeypatch.setenv("RSICONTEXT_SHOULD_NOT_LEAK", "blocked-secret")

    result = run_researcher_process(
        _codex_spec(executable, tmp_path),
        limits=ProcessLimits(timeout_seconds=2),
        environment_allowlist=("RSICONTEXT_TEST_CREDENTIAL",),
    )

    assert result.returncode == 0
    assert result.usage.input_tokens == 17
    assert result.usage.output_tokens == 5
    assert result.events[-1].kind == "complete"
    observed = json.loads(result.events[0].text or "")
    assert observed["argv"] == ["literal;not-shell", "$(still-not-shell)"]
    assert observed["cwd"] == str(tmp_path)
    assert observed["prompt"] == "research prompt"
    assert observed["secret"] == "allowed-secret"
    assert "RSICONTEXT_TEST_CREDENTIAL" in observed["environment"]
    assert "RSICONTEXT_SHOULD_NOT_LEAK" not in observed["environment"]
    assert set(observed["environment"]) <= {
        "LANG",
        "LC_ALL",
        "PATH",
        "PYTHONHASHSEED",
        "PYTHONIOENCODING",
        "RSICONTEXT_TEST_CREDENTIAL",
    }
    assert not (tmp_path / "not-shell").exists()
    assert not (tmp_path / "still-not-shell").exists()


def test_process_normalizes_claude_completion_and_usage(tmp_path: Path) -> None:
    executable = _fake_executable(
        tmp_path,
        """
import json

print(json.dumps({"type": "system", "subtype": "init", "session_id": "session-1"}))
print(json.dumps({
    "type": "result",
    "subtype": "success",
    "result": "done",
    "usage": {
        "input_tokens": 11,
        "output_tokens": 3,
        "cache_read_input_tokens": 2,
        "cache_creation_input_tokens": 4,
    },
    "total_cost_usd": 0.25,
}))
""",
    )
    spec = CommandSpec((str(executable),), tmp_path, "stream-json", "prompt")

    result = run_researcher_process(spec, limits=ProcessLimits(timeout_seconds=2))

    assert [event.kind for event in result.events] == ["session", "complete"]
    assert result.usage.total_input_tokens == 17
    assert result.usage.cost_usd == 0.25


def test_process_rejects_missing_allowlisted_environment_variable(tmp_path: Path) -> None:
    executable = _fake_executable(tmp_path, "raise AssertionError('must not execute')\n")

    with pytest.raises(ResearcherProcessError, match="is not set"):
        run_researcher_process(
            _codex_spec(executable, tmp_path),
            limits=ProcessLimits(timeout_seconds=2),
            environment_allowlist=("RSICONTEXT_DEFINITELY_MISSING",),
        )


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            'print(\'{"type":"turn.completed","usage":'
            '{"input_tokens":1,"output_tokens":1}}\')\nraise SystemExit(7)\n',
            "status 7",
        ),
        (
            'print(\'{"type":"item.completed","item":{"type":"agent_message","text":"unfinished"}}\')\n',
            "exactly one completion",
        ),
        ('print(\'{"type":"turn.completed"}\')\n', "usage"),
        (
            'print(\'{"type":"turn.failed","error":"research failed"}\')\n',
            "error event",
        ),
        (
            'print(\'{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}\')\n'
            'print(\'{"type":"item.completed","item":{"type":"agent_message","text":"late"}}\')\n',
            "final event",
        ),
    ],
)
def test_process_fails_closed_on_unsuccessful_protocol(
    tmp_path: Path, body: str, message: str
) -> None:
    executable = _fake_executable(tmp_path, body)

    with pytest.raises(ResearcherProcessError, match=message):
        run_researcher_process(
            _codex_spec(executable, tmp_path), limits=ProcessLimits(timeout_seconds=2)
        )


def test_process_enforces_timeout(tmp_path: Path) -> None:
    executable = _fake_executable(tmp_path, "import time\ntime.sleep(10)\n")

    with pytest.raises(ResearcherProcessError, match="timed out"):
        run_researcher_process(
            _codex_spec(executable, tmp_path), limits=ProcessLimits(timeout_seconds=0.05)
        )


@pytest.mark.parametrize("outcome", ["success", "failure", "timeout"])
def test_process_cleans_background_descendants_on_every_exit(
    tmp_path: Path,
    outcome: str,
) -> None:
    pid_file = tmp_path / f"child-{outcome}.pid"
    endings = {
        "success": (
            'print(\'{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}\')\n'
        ),
        "failure": "raise SystemExit(7)\n",
        "timeout": "time.sleep(10)\n",
    }
    executable = _fake_executable(
        tmp_path,
        f"""
import subprocess
import sys
import time
from pathlib import Path

child = subprocess.Popen(
    (sys.executable, "-c", "import time; time.sleep(30)"),
)
Path({str(pid_file)!r}).write_text(str(child.pid), encoding="utf-8")
{endings[outcome]}
""",
    )

    if outcome == "success":
        run_researcher_process(
            _codex_spec(executable, tmp_path), limits=ProcessLimits(timeout_seconds=2)
        )
    else:
        message = "status 7" if outcome == "failure" else "timed out"
        with pytest.raises(ResearcherProcessError, match=message):
            run_researcher_process(
                _codex_spec(executable, tmp_path),
                limits=ProcessLimits(timeout_seconds=0.1 if outcome == "timeout" else 2),
            )

    _assert_process_stopped(pid_file)


@pytest.mark.parametrize(
    ("body", "limits", "message"),
    [
        (
            'print("x" * 80)\n',
            ProcessLimits(timeout_seconds=2, max_line_bytes=64),
            "line",
        ),
        (
            'print("x" * 40)\nprint("y" * 40)\n',
            ProcessLimits(timeout_seconds=2, max_stdout_bytes=64),
            "stdout",
        ),
        (
            'import sys\nsys.stderr.write("e" * 80)\n',
            ProcessLimits(timeout_seconds=2, max_stderr_bytes=64),
            "stderr",
        ),
        (
            'import sys\nsys.stdout.write("o" * 50 + "\\n")\n'
            'sys.stdout.flush()\nsys.stderr.write("e" * 50 + "\\n")\n',
            ProcessLimits(
                timeout_seconds=2,
                max_line_bytes=64,
                max_stdout_bytes=64,
                max_stderr_bytes=64,
                max_total_bytes=96,
            ),
            "total",
        ),
    ],
)
def test_process_enforces_output_limits(
    tmp_path: Path, body: str, limits: ProcessLimits, message: str
) -> None:
    executable = _fake_executable(tmp_path, body)

    with pytest.raises(ResearcherProcessError, match=message):
        run_researcher_process(_codex_spec(executable, tmp_path), limits=limits)


def test_process_limits_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        ProcessLimits(timeout_seconds=True)
    with pytest.raises(ValueError, match="max_total_bytes"):
        ProcessLimits(timeout_seconds=1, max_total_bytes=0)


def test_process_rejects_invalid_spec_without_spawning(tmp_path: Path) -> None:
    spec = CommandSpec(("bad\x00argv",), tmp_path, "jsonl", "prompt")

    with pytest.raises(ResearcherProcessError, match="argv"):
        run_researcher_process(spec, limits=ProcessLimits(timeout_seconds=1))


@pytest.mark.parametrize("name", ["LD_PRELOAD", "PATH", "PYTHONPATH"])
def test_process_rejects_runtime_injection_environment_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
) -> None:
    executable = _fake_executable(tmp_path, "raise AssertionError('must not execute')\n")
    monkeypatch.setenv(name, "/tmp/not-allowed")

    with pytest.raises(ResearcherProcessError, match="unsafe"):
        run_researcher_process(
            _codex_spec(executable, tmp_path),
            limits=ProcessLimits(timeout_seconds=1),
            environment_allowlist=(name,),
        )


def test_failure_diagnostic_keeps_exception_line_and_drops_raw_stderr() -> None:
    traceback = (
        "Traceback (most recent call last):\n"
        '  File "api.py", line 1, in main\n'
        "    raise APIResearcherError('API researcher response is not valid JSON')\n"
        "APIResearcherError: API researcher response is not valid JSON\n"
    )

    assert (
        researcher_failure_diagnostic(
            "researcher process exited with status 1",
            traceback.encode(),
        )
        == "APIResearcherError: API researcher response is not valid JSON"
    )
    assert (
        researcher_failure_diagnostic(
            "researcher process exited with status 7",
            b"FAILURE-SECRET\n",
        )
        == "researcher process exited with status 7"
    )
