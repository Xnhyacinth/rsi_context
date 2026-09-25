from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rsicontext.registry import build_download_plan, load_registry, run_preflight
from rsicontext.registry.schema import Registry, RegistryError

REGISTRY_PATH = Path(__file__).parents[1] / "configs" / "registry.json"


def test_project_registry_has_required_entries_and_modes() -> None:
    registry = load_registry(REGISTRY_PATH)
    entries = {entry.id: entry for entry in registry.entries}

    assert set(entries) == {
        "qwen3.6-27b",
        "llama-3.3-70b-instruct",
        "longbench-v2-data",
        "ruler-v1",
        "helmet",
        "helmet-data",
        "longmemeval-v2",
        "longmemeval-v2-data",
        "rsibench-context-prepared-visible",
        "musique",
        "musique-answerable-data-qualification",
        "hotpotqa",
        "2wikimultihopqa",
        "otel-semconv-v1.43.0",
        "kubernetes-enhancements-kep753",
        "python-pep-process",
        "postgresql-rel-17-0",
        "gepa",
        "mce",
        "meta-harness",
        "recuris",
        "rlm",
        "kvpress",
    }
    assert entries["qwen3.6-27b"].integration == "direct"
    assert entries["gepa"].integration == "adapter"
    assert entries["mce"].integration == "adapter"
    assert entries["recuris"].revision == "a0479b27a2d08b7fbf2607acf1841a06b121ee91"
    assert entries["longmemeval-v2"].integration == "direct"
    assert entries["longmemeval-v2-data"].kind == "dataset"
    assert (
        entries["rsibench-context-prepared-visible"].revision
        == "6c384b2c209f79201a8b3ff9c54bbda2a339c62c"
    )
    assert entries["rsibench-context-prepared-visible"].access == "gated"
    assert entries["longbench-v2-data"].license == "Apache-2.0"
    assert entries["llama-3.3-70b-instruct"].access == "gated"
    assert entries["musique"].revision == "922ac98f19a201998dbdae6d7f2887a5258dbdeb"
    musique_data = entries["musique-answerable-data-qualification"]
    assert musique_data.revision == "763b65f844118a148e92bb88e7de5cb191b4c5dc"
    assert musique_data.integration == "adapter"
    assert "qualification only" in musique_data.notes
    assert entries["hotpotqa"].revision == "3635853403a8735609ee997664e1528f4480762a"
    assert entries["2wikimultihopqa"].revision == "13800e5be57df1b4040b9b1588c6c811779e69e9"
    for entry_id, revision in (
        ("otel-semconv-v1.43.0", "89aae438b3b3b0a8dd33003c9d70592baf7dbd0d"),
        ("kubernetes-enhancements-kep753", "13e8bb54ff7b1777d97c0f7f3cc9691c67414d4a"),
        ("python-pep-process", "6822259db9c95f02da739b3e2830a4aa1ae35134"),
        ("postgresql-rel-17-0", "d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e"),
    ):
        entry = entries[entry_id]
        assert entry.kind == "dataset"
        assert entry.integration == "adapter"
        assert entry.source_type == "git"
        assert entry.revision == revision
        assert entry.checksum.value == revision
        assert entry.checksum.verified


def test_registry_rejects_duplicate_ids() -> None:
    manifest = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    manifest["entries"].append(manifest["entries"][0])

    with pytest.raises(RegistryError, match="unique"):
        Registry.from_dict(manifest)


def test_registry_select_preserves_requested_order_and_rejects_unknown() -> None:
    registry = load_registry(REGISTRY_PATH)

    selected = registry.select(["kvpress", "qwen3.6-27b"])
    assert [entry.id for entry in selected] == ["kvpress", "qwen3.6-27b"]
    with pytest.raises(RegistryError, match="missing"):
        registry.select(["missing"])


def test_download_plan_is_dry_run_and_does_not_create_destination(tmp_path: Path) -> None:
    registry = load_registry(REGISTRY_PATH)
    destination = tmp_path / "not-created"

    plan = build_download_plan(registry.select(["qwen3.6-27b", "ruler-v1", "mce"]), destination)

    assert plan.dry_run is True
    assert not destination.exists()
    qwen, ruler, mce = plan.artifacts
    assert qwen.acquire_command is not None
    assert "hf download Qwen/Qwen3.6-27B" in qwen.acquire_command
    assert (
        "uvx --with click==8.3.1 --from huggingface-hub==1.3.3 hf cache verify"
        in qwen.verify_commands[0]
    )
    assert "--local-dir" in qwen.verify_commands[0]
    assert "--fail-on-missing-files" in qwen.verify_commands[0]
    assert "--fail-on-extra-files" not in qwen.verify_commands[0]
    assert ruler.acquire_command is not None
    assert "git clone --filter=blob:none" in ruler.acquire_command
    assert len(ruler.verify_commands) == 2
    assert not any("not pinned" in warning for warning in ruler.warnings)
    assert mce.acquire_command is not None
    assert mce.destination is not None


def test_download_plan_reports_known_and_unknown_sizes(tmp_path: Path) -> None:
    registry = load_registry(REGISTRY_PATH)
    plan = build_download_plan(
        registry.select(["qwen3.6-27b", "llama-3.3-70b-instruct", "helmet"]), tmp_path
    )

    assert plan.known_size_bytes == 196_700_000_000
    assert plan.unknown_size_count == 1


def test_hugging_face_dataset_plan_sets_repo_type_for_download_and_verification(
    tmp_path: Path,
) -> None:
    registry = load_registry(REGISTRY_PATH)

    artifact = build_download_plan(registry.select(["longbench-v2-data"]), tmp_path).artifacts[0]

    assert artifact.acquire_command is not None
    assert "--repo-type dataset" in artifact.acquire_command
    assert "--repo-type dataset" in artifact.verify_commands[0]
    assert "--fail-on-missing-files" in artifact.verify_commands[0]


def test_preflight_is_read_only_and_detects_missing_gated_auth(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    wrapper = tmp_path / "hold.sh"
    wrapper.touch()
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr("rsicontext.registry.preflight.Path.home", lambda: tmp_path)
    monkeypatch.setattr("rsicontext.registry.preflight.shutil.which", lambda _: "nvidia-smi")
    monkeypatch.setattr(
        "rsicontext.registry.preflight.shutil.disk_usage",
        lambda _: SimpleNamespace(free=1_000_000),
    )
    monkeypatch.setattr(
        "rsicontext.registry.preflight.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="NVIDIA H200, 143771\nNVIDIA H200, 143771\n",
            stderr="",
        ),
    )

    report = run_preflight(
        tmp_path,
        required_bytes=100,
        expected_gpus=2,
        hf_auth_required=True,
        hold_wrapper=wrapper,
    )

    assert report.read_only is True
    assert report.ready is False
    assert {check.name: check.status for check in report.checks}["hf_auth"] == "fail"
    assert "wrap 0,1 -- <COMMAND>" in report.gpu_hold_command


def test_preflight_rejects_invalid_resource_requirements(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        run_preflight(tmp_path, required_bytes=-1)
    with pytest.raises(ValueError, match="positive"):
        run_preflight(tmp_path, required_bytes=0, expected_gpus=0)
