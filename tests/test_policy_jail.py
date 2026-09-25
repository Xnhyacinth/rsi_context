"""Offline checks for the single-file staged policy jail.

These tests never contact a model or change the live isolation gate.
"""

from __future__ import annotations

import hashlib
import json
import os
import select
import shutil
import struct
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from rsicontext.lifecycle.group_baselines import (
    group_b_basline_policy_text,
    group_c_baseline_policy_text,
)
from rsicontext.lifecycle.strong_model_fixed import strong_model_fixed_policy_text
from rsicontext.security.policy_jail import (
    JailSetupError,
    StagedPolicyJail,
    launch_policy_jail,
    stage_policy_jail,
)
from rsicontext.security.policy_protocol import encode_message, read_frame

_POLICY = b"""def on_turn(turn):
    turn.state["seen"] = turn.view.kind
    return {"pack_text": turn.documents_text, "actions": (
        turn.actions.create_record("note", {"answer": "ready"}),
    )}
"""


def _python() -> Path:
    return Path(getattr(sys, "_base_executable", sys.executable)).resolve()


@pytest.fixture
def staged_jail() -> Iterator[StagedPolicyJail]:
    if os.geteuid() != 0:
        pytest.skip("root-owned jail staging requires host root")
    parent = Path(tempfile.mkdtemp(prefix="rsi-policy-jail-", dir="/tmp"))
    os.chmod(parent, 0o755)
    try:
        python = _python()
        yield stage_policy_jail(
            parent / "jail",
            _POLICY,
            python_executable=python,
            expected_python_sha256=hashlib.sha256(python.read_bytes()).hexdigest(),
        )
    finally:
        shutil.rmtree(parent)


def _stage(stage_id: str, kind: str = "survey") -> dict[str, object]:
    return {
        "version": 1,
        "seq": 0,
        "type": "stage_start",
        "body": {
            "view": {
                "stage_id": stage_id,
                "kind": kind,
                "prompt_text": "Read the visible note.",
                "documents": [
                    {
                        "doc_id": "d1",
                        "title": "Visible",
                        "text": "Evidence",
                        "source_url": "",
                        "retrieved_date": "",
                        "superseded_by": None,
                    }
                ],
                "axes": {
                    "information_scale_tokens": 100,
                    "dependency_distance_stages": 1,
                    "persistence_span_resets": 0,
                    "action_dependency": "strong",
                    "environment_changes": 0,
                },
                "remaining_budget": 2,
                "receipts": [],
            },
            "state": {},
        },
    }


def test_staged_manifest_is_read_only_and_pinned(staged_jail: StagedPolicyJail) -> None:
    staged_jail.verify()
    assert (staged_jail.root / "policy/seed.py").read_bytes() == _POLICY
    assert not (staged_jail.root / ".venv").exists()
    assert not (staged_jail.root / "lib/python3.12/site-packages").exists()
    assert (staged_jail.root / "MANIFEST.json").stat().st_mode & 0o222 == 0


def test_material_change_is_detected_before_launch(staged_jail: StagedPolicyJail) -> None:
    policy = staged_jail.root / "policy/seed.py"
    os.chmod(policy, 0o644)
    policy.write_bytes(_POLICY + b"\n# changed\n")
    os.chmod(policy, 0o444)
    with pytest.raises(JailSetupError, match="jail material changed"):
        staged_jail.verify()


@pytest.mark.parametrize("kind", ["broken_symlink", "fifo"])
def test_unmanifested_special_entry_is_rejected(staged_jail: StagedPolicyJail, kind: str) -> None:
    root = staged_jail.root
    os.chmod(root, 0o755)
    try:
        entry = root / "unmanifested"
        if kind == "broken_symlink":
            entry.symlink_to(root / "missing")
        else:
            os.mkfifo(entry)
    finally:
        os.chmod(root, 0o555)
    with pytest.raises(JailSetupError, match=r"symlink|special file"):
        staged_jail.verify()


def test_wrong_interpreter_pin_refuses_before_staging() -> None:
    if os.geteuid() != 0:
        pytest.skip("root-owned jail staging requires host root")
    parent = Path(tempfile.mkdtemp(prefix="rsi-policy-pin-", dir="/tmp"))
    os.chmod(parent, 0o755)
    try:
        with pytest.raises(JailSetupError, match="interpreter SHA256"):
            stage_policy_jail(
                parent / "jail",
                _POLICY,
                python_executable=_python(),
                expected_python_sha256="0" * 64,
            )
        assert not (parent / "jail").exists()
    finally:
        shutil.rmtree(parent)


def test_two_trusted_turns_use_same_pipes_and_reset_sequence(staged_jail: StagedPolicyJail) -> None:
    parent_to_child_read, parent_to_child_write = os.pipe()
    child_to_parent_read, child_to_parent_write = os.pipe()
    handle = launch_policy_jail(
        staged_jail, read_fd=parent_to_child_read, write_fd=child_to_parent_write
    )
    process = handle.process
    os.close(parent_to_child_read)
    os.close(child_to_parent_write)
    try:
        with (
            os.fdopen(parent_to_child_write, "wb") as outgoing,
            os.fdopen(child_to_parent_read, "rb") as incoming,
        ):
            for stage_id in ("s1", "s2"):
                outgoing.write(encode_message(_stage(stage_id)))
                outgoing.flush()
                ready, _, _ = select.select([incoming], [], [], 10)
                assert ready, "jailed child produced no response"
                done = read_frame(incoming)
                assert done["type"] == "turn_done" and done["seq"] == 1
                body = done["body"]
                assert isinstance(body, dict)
                assert body["state"] == {"seen": "survey"}
                decision = body["decision"]
                assert isinstance(decision, dict)
                assert "[[doc:d1]]" in decision["pack_text"]
                assert decision["actions"][0]["kind"] == "create_record"
        assert process.wait(timeout=5) == 0
    finally:
        handle.close()
    staged_jail.verify()


def _launch_trusted_probe(
    jail: StagedPolicyJail, mode: str, secret_path: str = ""
) -> tuple[subprocess.Popen[bytes], int, int]:
    """Test-only command with the same staged binary and namespace controls."""

    parent_to_child_read, parent_to_child_write = os.pipe()
    child_to_parent_read, child_to_parent_write = os.pipe()
    jail.verify()
    command = [
        "/usr/bin/setpriv",
        "--reuid",
        "65534",
        "--regid",
        "65534",
        "--clear-groups",
        "--no-new-privs",
        "/usr/bin/unshare",
        "--user",
        "--map-root-user",
        "--net",
        str(jail.root / "lib64/ld-linux-x86-64.so.2"),
        "--library-path",
        str(jail.root / "lib/x86_64-linux-gnu"),
        str(jail.root / "bin/python3.12"),
        "-S",
        "-P",
        str(jail.root / "child.py"),
        mode,
        str(jail.root),
        os.readlink("/proc/self/ns/net"),
        str(parent_to_child_read),
        str(child_to_parent_write),
        jail.policy_sha256,
    ]
    if mode == "--self-test":
        command.append(secret_path)
    process = subprocess.Popen(  # nosec B603 - fixed trusted offline probe argv
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={"PYTHONHOME": str(jail.root)},
        cwd="/",
        close_fds=True,
        pass_fds=(parent_to_child_read, child_to_parent_write),
    )
    os.close(parent_to_child_read)
    os.close(child_to_parent_write)
    return process, parent_to_child_write, child_to_parent_read


def test_kernel_guards_hide_host_and_bound_resources(staged_jail: StagedPolicyJail) -> None:
    with tempfile.NamedTemporaryFile(prefix="rsi-host-secret-", dir="/tmp") as secret:
        secret.write(b"host-only sentinel")
        secret.flush()
        os.chmod(secret.name, 0o644)
        process, parent_write, child_read = _launch_trusted_probe(
            staged_jail, "--self-test", secret.name
        )
        os.close(parent_write)
        try:
            ready, _, _ = select.select([child_read], [], [], 10)
            assert ready, "trusted security probe produced no response"
            with os.fdopen(child_read, "rb") as incoming:
                header = incoming.read(4)
                assert len(header) == 4
                size = struct.unpack(">I", header)[0]
                payload = incoming.read(size)
            assert len(payload) == size
            result = json.loads(payload)["probe"]
            assert result == {
                "host_secret_hidden": True,
                "proc_hidden": True,
                "host_file_hidden": True,
                "jail_write_denied": True,
                "network_denied": True,
                "fork_denied": True,
                "memory_denied": True,
                "output_denied": True,
                "cpu_limit_seconds": 3,
                "seccomp_mode": 2,
            }
            assert process.wait(timeout=5) == 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


def test_cpu_burn_is_killed_by_rlimit(staged_jail: StagedPolicyJail) -> None:
    process, parent_write, child_read = _launch_trusted_probe(staged_jail, "--cpu-burn")
    os.close(parent_write)
    os.close(child_read)
    try:
        assert process.wait(timeout=8) < 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_wall_deadline_reaps_idle_worker_group(staged_jail: StagedPolicyJail) -> None:
    parent_to_child_read, parent_to_child_write = os.pipe()
    child_to_parent_read, child_to_parent_write = os.pipe()
    handle = launch_policy_jail(
        staged_jail, read_fd=parent_to_child_read, write_fd=child_to_parent_write
    )
    os.close(parent_to_child_read)
    os.close(child_to_parent_write)
    try:
        with pytest.raises(JailSetupError, match="wall deadline"):
            handle.wait(timeout=0.2)
        assert handle.process.poll() is not None
        assert handle.process.stderr is None or handle.process.stderr.closed
    finally:
        os.close(parent_to_child_write)
        os.close(child_to_parent_read)
        handle.close()


def test_normal_completion_does_not_signal_reaped_pid(
    staged_jail: StagedPolicyJail, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent_to_child_read, parent_to_child_write = os.pipe()
    child_to_parent_read, child_to_parent_write = os.pipe()
    handle = launch_policy_jail(
        staged_jail, read_fd=parent_to_child_read, write_fd=child_to_parent_write
    )
    os.close(parent_to_child_read)
    os.close(child_to_parent_write)
    os.close(parent_to_child_write)  # A clean protocol EOF ends the session.
    os.close(child_to_parent_read)
    assert handle.process.wait(timeout=5) == 0

    def forbidden_signal(_pid: int, _signal: int) -> None:
        pytest.fail("a reaped worker PID must never be signalled")

    monkeypatch.setattr("rsicontext.security.policy_jail.os.killpg", forbidden_signal)
    handle.close()
    assert handle.process.stderr is None or handle.process.stderr.closed


def test_cleanup_error_does_not_replace_primary_failure(
    staged_jail: StagedPolicyJail, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent_to_child_read, parent_to_child_write = os.pipe()
    child_to_parent_read, child_to_parent_write = os.pipe()
    handle = launch_policy_jail(
        staged_jail, read_fd=parent_to_child_read, write_fd=child_to_parent_write
    )
    os.close(parent_to_child_read)
    os.close(child_to_parent_write)

    def broken_verify(_self: StagedPolicyJail) -> None:
        raise JailSetupError("cleanup digest failed")

    monkeypatch.setattr(StagedPolicyJail, "verify", broken_verify)
    try:
        with pytest.raises(ValueError, match="primary broker failure") as caught, handle:
            raise ValueError("primary broker failure")
        assert any("cleanup digest failed" in note for note in caught.value.__notes__)
        assert handle.process.poll() is not None
    finally:
        os.close(parent_to_child_write)
        os.close(child_to_parent_read)


@pytest.mark.parametrize(
    "policy_text",
    [
        strong_model_fixed_policy_text(),
        group_b_basline_policy_text(),
        group_c_baseline_policy_text(),
    ],
    ids=["A", "B", "C"],
)
def test_fixed_abc_seed_survey_uses_broker_rpc(policy_text: str) -> None:
    if os.geteuid() != 0:
        pytest.skip("root-owned jail staging requires host root")
    parent = Path(tempfile.mkdtemp(prefix="rsi-policy-seed-", dir="/tmp"))
    os.chmod(parent, 0o755)
    python = _python()
    jail = stage_policy_jail(
        parent / "jail",
        policy_text.encode(),
        python_executable=python,
        expected_python_sha256=hashlib.sha256(python.read_bytes()).hexdigest(),
    )
    parent_to_child_read, parent_to_child_write = os.pipe()
    child_to_parent_read, child_to_parent_write = os.pipe()
    handle = launch_policy_jail(jail, read_fd=parent_to_child_read, write_fd=child_to_parent_write)
    os.close(parent_to_child_read)
    os.close(child_to_parent_write)
    try:
        with (
            os.fdopen(parent_to_child_write, "wb") as outgoing,
            os.fdopen(child_to_parent_read, "rb") as incoming,
        ):
            outgoing.write(encode_message(_stage("seed-survey")))
            outgoing.flush()
            ready, _, _ = select.select([incoming], [], [], 10)
            assert ready
            request = read_frame(incoming)
            assert request["type"] == "tool_request" and request["seq"] == 1
            request_body = request["body"]
            assert isinstance(request_body, dict)
            assert request_body["tool"] == "ask_model"
            outgoing.write(
                encode_message(
                    {
                        "version": 1,
                        "seq": 2,
                        "type": "tool_reply",
                        "body": {
                            "tool": "ask_model",
                            "result": {
                                "ok": True,
                                "answer": "note from visible evidence",
                                "cause": "",
                                "tokens_in": 4,
                                "tokens_out": 4,
                            },
                        },
                    }
                )
            )
            outgoing.flush()
            ready, _, _ = select.select([incoming], [], [], 10)
            assert ready
            done = read_frame(incoming)
            assert done["type"] == "turn_done" and done["seq"] == 3
            done_body = done["body"]
            assert isinstance(done_body, dict)
            decision = done_body["decision"]
            state = done_body["state"]
            assert isinstance(decision, dict) and isinstance(state, dict)
            assert decision["errors"] == []
            assert state["notes"] == {"batch-0": "note from visible evidence"}
        assert handle.process.wait(timeout=5) == 0
    finally:
        handle.close()
        shutil.rmtree(parent)
