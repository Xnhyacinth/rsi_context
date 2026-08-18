from __future__ import annotations

from pathlib import Path

from rsicontext.security import observe_linux_isolation


def _fake_process(proc_root: Path, pid: int, *, suffix: str) -> None:
    process = proc_root / str(pid)
    (process / "ns").mkdir(parents=True)
    (process / "net").mkdir()
    (process / "ns" / "mnt").symlink_to(f"mnt:[{suffix}]")
    (process / "ns" / "pid").symlink_to(f"pid:[{suffix}]")
    (process / "cgroup").write_text(f"0::/rsibench/{suffix}\n", encoding="utf-8")
    (process / "mountinfo").write_text(
        "1 0 8:1 / /sealed ro,nosuid - ext4 /dev/root ro\n"
        "2 0 8:1 / /evaluator ro,nosuid - ext4 /dev/root ro\n",
        encoding="utf-8",
    )
    (process / "net" / "dev").write_text(
        "Inter-| Receive | Transmit\n face |bytes |bytes\n lo: 0 0\n",
        encoding="utf-8",
    )


def test_linux_observer_proves_each_required_boundary_from_proc(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    _fake_process(proc_root, 20, suffix="evaluator")
    _fake_process(proc_root, 10, suffix="researcher")

    attestation = observe_linux_isolation(
        researcher_pid=10,
        evaluator_pid=20,
        required_read_only_mounts=("/sealed/data", "/evaluator"),
        observed_at="2026-08-14T12:00:00Z",
        proc_root=proc_root,
    )

    assert attestation.evidence_source == "observed-linux"
    assert attestation.network_mode == "none"
    assert attestation.read_only_mounts == ("/evaluator", "/sealed")
    assert attestation.formal_failures == ()
    assert len(attestation.attestation_sha256) == 64


def test_linux_observer_does_not_claim_isolation_when_observation_is_missing(
    tmp_path: Path,
) -> None:
    attestation = observe_linux_isolation(
        researcher_pid=10,
        evaluator_pid=20,
        required_read_only_mounts=("/sealed",),
        observed_at="2026-08-14T12:00:00Z",
        proc_root=tmp_path / "missing-proc",
    )

    assert attestation.evidence_source == "incomplete-linux-observation"
    assert attestation.network_mode == "unknown"
    assert "declaration-only or incompletely observed" in attestation.formal_failures[0]


def test_linux_observer_reports_network_and_read_write_mount_failures(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    _fake_process(proc_root, 20, suffix="evaluator")
    _fake_process(proc_root, 10, suffix="researcher")
    (proc_root / "20" / "mountinfo").write_text(
        "1 0 8:1 / /sealed rw,nosuid - ext4 /dev/root rw\n",
        encoding="utf-8",
    )
    (proc_root / "20" / "net" / "dev").write_text(
        "Inter-| Receive | Transmit\n face |bytes |bytes\n lo: 0 0\n eth0: 0 0\n",
        encoding="utf-8",
    )

    attestation = observe_linux_isolation(
        researcher_pid=10,
        evaluator_pid=20,
        required_read_only_mounts=("/sealed",),
        observed_at="2026-08-14T12:00:00Z",
        proc_root=proc_root,
    )

    assert attestation.network_mode == "available"
    assert any("no-network" in failure for failure in attestation.formal_failures)
    assert any("read-only" in failure for failure in attestation.formal_failures)
