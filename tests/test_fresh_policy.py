from __future__ import annotations

import time
from pathlib import Path

import pytest

from rsicontext.eval import (
    AuditedPolicyBundle,
    FreshProcessPolicyFactory,
    PolicyProcessError,
    PolicyProcessTimeout,
    PolicyProtocolError,
)
from rsicontext.policy import Artifact, Budget, DocumentChunk
from rsicontext.security import AuditReport, PolicyAuditor


class PermissiveTestAuditor(PolicyAuditor):
    """Expose process isolation independently of the normal capability audit."""

    def audit_tree(self, root: str | Path) -> AuditReport:
        del root
        return AuditReport(("policy.py",), ())

    def audit_source(
        self, source: str, *, filename: str = "<policy>", extra_allowed_imports: object = ()
    ) -> AuditReport:
        del source, extra_allowed_imports
        return AuditReport((filename,), ())


def _artifact() -> Artifact:
    return Artifact(
        "doc",
        (
            DocumentChunk("first", "doc", 0, 5, "first", 1),
            DocumentChunk("second", "doc", 6, 12, "second", 1),
        ),
    )


def _write_policy(tmp_path: Path, source: str) -> Path:
    root = tmp_path / "policy"
    root.mkdir(parents=True)
    (root / "policy.py").write_text(source, encoding="utf-8")
    return root


def _factory(
    tmp_path: Path,
    source: str,
    *,
    auditor: PolicyAuditor | None = None,
    timeout_seconds: float = 1.0,
    max_output_bytes: int = 64_000,
) -> FreshProcessPolicyFactory:
    bundle = AuditedPolicyBundle.from_directory(_write_policy(tmp_path, source), auditor=auditor)
    return FreshProcessPolicyFactory(
        bundle,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
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
    pytest.fail(f"background process {pid} survived policy-worker cleanup")


def test_fresh_interpreter_prevents_cross_item_module_state_leakage(tmp_path: Path) -> None:
    factory = _factory(
        tmp_path,
        """
from rsicontext.policy import ContextPack

CALLS = 0

class Policy:
    def assemble(self, artifact, query, budget):
        global CALLS
        CALLS += 1
        spans = (artifact.chunks[0],) if CALLS == 1 else (artifact.chunks[1],)
        return ContextPack(spans=spans, ordering=(spans[0].chunk_id,), token_count=1)
""",
        auditor=PermissiveTestAuditor(),
    )
    policy = factory()
    artifact = _artifact()

    assert policy.assemble(artifact, "query", Budget(1)).ordering == ("first",)
    assert policy.assemble(artifact, "query", Budget(1)).ordering == ("first",)


def test_parent_reconstructs_a_valid_context_pack(tmp_path: Path) -> None:
    factory = _factory(
        tmp_path,
        """
from rsicontext.policy import ContextPack

class Policy:
    def assemble(self, artifact, query, budget):
        del query, budget
        span = artifact.chunks[1]
        return ContextPack(spans=(span,), ordering=(span.chunk_id,), token_count=span.token_count)
""",
    )

    pack = factory().assemble(_artifact(), "query", Budget(1))

    assert pack.ordering == ("second",)
    assert pack.spans == (_artifact().chunks[1],)


def test_bundle_uses_audited_bytes_after_source_directory_changes(tmp_path: Path) -> None:
    policy_root = _write_policy(
        tmp_path,
        """
from rsicontext.policy import ContextPack

class Policy:
    def assemble(self, artifact, query, budget):
        del query, budget
        span = artifact.chunks[1]
        return ContextPack(spans=(span,), ordering=(span.chunk_id,), token_count=1)
""",
    )
    bundle = AuditedPolicyBundle.from_directory(policy_root)
    (policy_root / "policy.py").write_text("import os\n", encoding="utf-8")

    pack = FreshProcessPolicyFactory(bundle)().assemble(_artifact(), "query", Budget(1))

    assert pack.ordering == ("second",)


def test_parent_rejects_over_budget_child_result(tmp_path: Path) -> None:
    factory = _factory(
        tmp_path,
        """
from rsicontext.policy import ContextPack

class Policy:
    def assemble(self, artifact, query, budget):
        del query, budget
        return ContextPack(spans=artifact.chunks, ordering=("first", "second"), token_count=2)
""",
    )

    with pytest.raises(PolicyProtocolError, match="budget"):
        factory().assemble(_artifact(), "query", Budget(1))


def test_parent_rejects_forged_provenance_from_child(tmp_path: Path) -> None:
    factory = _factory(
        tmp_path,
        """
from rsicontext.policy import ContextPack, DocumentChunk

class Policy:
    def assemble(self, artifact, query, budget):
        del artifact, query, budget
        forged = DocumentChunk("first", "doc", 0, 5, "forged", 1)
        return ContextPack(spans=(forged,), ordering=("first",), token_count=1)
""",
    )

    with pytest.raises(PolicyProtocolError, match="provenance"):
        factory().assemble(_artifact(), "query", Budget(1))


def test_child_timeout_fails_closed(tmp_path: Path) -> None:
    factory = _factory(
        tmp_path,
        """
class Policy:
    def assemble(self, artifact, query, budget):
        del artifact, query, budget
        while True:
            pass
""",
        timeout_seconds=0.05,
    )

    with pytest.raises(PolicyProcessTimeout, match="timed out"):
        factory().assemble(_artifact(), "query", Budget(1))


def test_invalid_or_oversized_child_output_fails_closed(tmp_path: Path) -> None:
    invalid = _factory(
        tmp_path,
        """
from rsicontext.policy import ContextPack
print("not-json")

class Policy:
    def assemble(self, artifact, query, budget):
        del artifact, query, budget
        return ContextPack()
""",
    )
    with pytest.raises(PolicyProtocolError, match="JSON"):
        invalid().assemble(_artifact(), "query", Budget(1))

    oversized = _factory(
        tmp_path / "oversized",
        """
from rsicontext.policy import ContextPack
print("x" * 10000)

class Policy:
    def assemble(self, artifact, query, budget):
        del artifact, query, budget
        return ContextPack()
""",
        max_output_bytes=256,
    )
    with pytest.raises(PolicyProtocolError, match="output limit"):
        oversized().assemble(_artifact(), "query", Budget(1))


def test_loader_error_and_nonzero_exit_fail_closed(tmp_path: Path) -> None:
    factory = _factory(tmp_path, "class NotPolicy:\n    pass\n")

    with pytest.raises(PolicyProcessError, match="non-zero"):
        factory().assemble(_artifact(), "query", Budget(1))


def test_fresh_worker_uses_minimal_environment_and_safe_cwd(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    secret_file = tmp_path / "evaluator-secret.txt"
    secret_file.write_text("file-secret", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RSICONTEXT_EVALUATOR_SECRET", "environment-secret")
    factory = _factory(
        tmp_path / "candidate",
        """
import os
from pathlib import Path
from rsicontext.policy import ContextPack

class Policy:
    def assemble(self, artifact, query, budget):
        del query, budget
        safe = (
            "RSICONTEXT_EVALUATOR_SECRET" not in os.environ
            and not Path("evaluator-secret.txt").exists()
            and Path.cwd().name.startswith("rsicontext-policy-")
        )
        span = artifact.chunks[0] if safe else artifact.chunks[1]
        return ContextPack(spans=(span,), ordering=(span.chunk_id,), token_count=1)
""",
        auditor=PermissiveTestAuditor(),
    )

    pack = factory().assemble(_artifact(), "query", Budget(1))

    assert pack.ordering == ("first",)


@pytest.mark.parametrize("outcome", ["success", "failure", "timeout"])
def test_fresh_worker_cleans_background_descendants_on_every_exit(
    tmp_path: Path,
    outcome: str,
) -> None:
    pid_file = tmp_path / f"policy-child-{outcome}.pid"
    endings = {
        "success": (
            "span = artifact.chunks[0]\n"
            "        return ContextPack(spans=(span,), ordering=(span.chunk_id,), token_count=1)"
        ),
        "failure": 'raise RuntimeError("candidate failed")',
        "timeout": "time.sleep(10)",
    }
    factory = _factory(
        tmp_path / outcome,
        f"""
import subprocess
import sys
import time
from pathlib import Path
from rsicontext.policy import ContextPack

class Policy:
    def assemble(self, artifact, query, budget):
        del query, budget
        child = subprocess.Popen(
            (sys.executable, "-c", "import time; time.sleep(30)"),
        )
        Path({str(pid_file)!r}).write_text(str(child.pid), encoding="utf-8")
        {endings[outcome]}
""",
        auditor=PermissiveTestAuditor(),
        timeout_seconds=0.1 if outcome == "timeout" else 1,
    )

    if outcome == "success":
        factory().assemble(_artifact(), "query", Budget(1))
    elif outcome == "failure":
        with pytest.raises(PolicyProcessError, match="non-zero"):
            factory().assemble(_artifact(), "query", Budget(1))
    else:
        with pytest.raises(PolicyProcessTimeout, match="timed out"):
            factory().assemble(_artifact(), "query", Budget(1))

    _assert_process_stopped(pid_file)
