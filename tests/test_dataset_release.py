from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest

from rsicontext.release import ReleaseSpecError, build_dataset_release

ROOT = Path(__file__).parents[1]
SOURCE_REVISION = "a" * 40


def _release_spec() -> dict[str, object]:
    raw = json.loads((ROOT / "configs" / "hf_dataset_release.json").read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return cast(dict[str, object], raw)


def _write_spec(tmp_path: Path, raw: object) -> Path:
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _committed_release_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    fixture = repo / "tests" / "fixtures" / "musique_answerable_sample.jsonl"
    config = repo / "configs" / "hf_dataset_release.json"
    fixture.parent.mkdir(parents=True)
    config.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "tests/fixtures/musique_answerable_sample.jsonl", fixture)
    shutil.copyfile(ROOT / "configs/hf_dataset_release.json", config)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "release-test@example.invalid")
    _git(repo, "config", "user.name", "Release Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "test fixture")
    return repo, _git(repo, "rev-parse", "HEAD")


def test_release_contains_only_allowlisted_fixture_and_metadata(tmp_path: Path) -> None:
    repo, source_revision = _committed_release_repo(tmp_path)
    output = tmp_path / "release"

    manifest = build_dataset_release(
        spec_path=repo / "configs" / "hf_dataset_release.json",
        repo_root=repo,
        output_dir=output,
        source_revision=source_revision,
    )

    assert sorted(
        path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()
    ) == [
        "MANIFEST.json",
        "README.md",
        "checksums.sha256",
        "fixtures/musique_answerable_synthetic_v1.jsonl",
    ]
    payload = output / "fixtures" / "musique_answerable_synthetic_v1.jsonl"
    assert (
        payload.read_bytes()
        == (repo / "tests/fixtures/musique_answerable_sample.jsonl").read_bytes()
    )
    assert manifest["source_revision"] == source_revision
    assert manifest["qualification"] == "fixture-only; not a formal benchmark release"
    assert manifest["formal_benchmark_eligible"] is False
    assert manifest["boundary"] == {
        "classification": "researcher-visible",
        "allowed_splits": ["synthetic-visible-fixture"],
        "explicitly_excluded": [
            "gate/sealed questions or labels",
            "evaluator-only seeds and item scores",
            "raw API responses and experiment results",
            "upstream benchmark archives",
        ],
    }
    files = manifest["files"]
    assert isinstance(files, list)
    assert files == [
        {
            "path": "fixtures/musique_answerable_synthetic_v1.jsonl",
            "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
            "size_bytes": payload.stat().st_size,
            "source_path": "tests/fixtures/musique_answerable_sample.jsonl",
            "license": "other",
            "provenance": "Project-authored synthetic fixture shaped like MuSiQue answerable data.",
            "visibility": "synthetic-visible-fixture",
            "purpose": "schema-smoke",
            "record_count": 1,
            "label_fields": [
                "answer",
                "answer_aliases",
                "paragraphs[].is_supporting",
                "question_decomposition[].answer",
            ],
        }
    ]
    assert json.loads((output / "MANIFEST.json").read_text(encoding="utf-8")) == manifest
    checksum_line = (output / "checksums.sha256").read_text(encoding="utf-8")
    assert (
        checksum_line == f"{files[0]['sha256']}  fixtures/musique_answerable_synthetic_v1.jsonl\n"
    )


def test_release_is_reproducible(tmp_path: Path) -> None:
    repo, source_revision = _committed_release_repo(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"

    build_dataset_release(
        spec_path=repo / "configs" / "hf_dataset_release.json",
        repo_root=repo,
        output_dir=first,
        source_revision=source_revision,
    )
    build_dataset_release(
        spec_path=repo / "configs" / "hf_dataset_release.json",
        repo_root=repo,
        output_dir=second,
        source_revision=source_revision,
    )

    assert {
        path.relative_to(first): path.read_bytes() for path in first.rglob("*") if path.is_file()
    } == {
        path.relative_to(second): path.read_bytes() for path in second.rglob("*") if path.is_file()
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_path", "results/raw.json", "tests/fixtures"),
        ("source_path", "tests/fixtures/../secret.json", "safe relative"),
        ("destination_path", "../secret.json", "safe relative"),
        ("destination_path", "README.md", "reserved"),
    ],
)
def test_release_rejects_unsafe_or_unpublishable_paths(
    tmp_path: Path, field: str, value: str, message: str
) -> None:
    raw = _release_spec()
    assert isinstance(raw["files"], list)
    assert isinstance(raw["files"][0], dict)
    raw["files"][0][field] = value

    with pytest.raises(ReleaseSpecError, match=message):
        build_dataset_release(
            spec_path=_write_spec(tmp_path, raw),
            repo_root=ROOT,
            output_dir=tmp_path / "release",
            source_revision=SOURCE_REVISION,
        )


def test_release_rejects_invalid_revision_and_nonempty_destination(tmp_path: Path) -> None:
    output = tmp_path / "release"
    output.mkdir()
    (output / "stale.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ReleaseSpecError, match="absent"):
        build_dataset_release(
            spec_path=ROOT / "configs" / "hf_dataset_release.json",
            repo_root=ROOT,
            output_dir=output,
            source_revision=SOURCE_REVISION,
        )
    with pytest.raises(ReleaseSpecError, match="40-character"):
        build_dataset_release(
            spec_path=ROOT / "configs" / "hf_dataset_release.json",
            repo_root=ROOT,
            output_dir=tmp_path / "other",
            source_revision="main",
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"schema_version": 2}, "schema_version"),
        ({"formal_benchmark_eligible": True}, "formal_benchmark_eligible"),
        ({"files": []}, "non-empty list"),
        ({"unexpected": True}, "fields mismatch"),
        ({"description": " padded "}, "trimmed"),
    ],
)
def test_release_rejects_unsafe_root_schema(
    tmp_path: Path, mutation: dict[str, object], message: str
) -> None:
    raw = _release_spec()
    raw.update(mutation)

    with pytest.raises(ReleaseSpecError, match=message):
        build_dataset_release(
            spec_path=_write_spec(tmp_path, raw),
            repo_root=ROOT,
            output_dir=tmp_path / "release",
            source_revision=SOURCE_REVISION,
        )


def test_release_rejects_duplicate_destination_and_invalid_file_fields(tmp_path: Path) -> None:
    duplicate = _release_spec()
    assert isinstance(duplicate["files"], list)
    duplicate["files"].append(dict(duplicate["files"][0]))
    with pytest.raises(ReleaseSpecError, match="unique"):
        build_dataset_release(
            spec_path=_write_spec(tmp_path, duplicate),
            repo_root=ROOT,
            output_dir=tmp_path / "duplicate-output",
            source_revision=SOURCE_REVISION,
        )

    invalid = _release_spec()
    assert isinstance(invalid["files"], list)
    invalid["files"] = ["not-an-object"]
    with pytest.raises(ReleaseSpecError, match="must be an object"):
        build_dataset_release(
            spec_path=_write_spec(tmp_path, invalid),
            repo_root=ROOT,
            output_dir=tmp_path / "invalid-output",
            source_revision=SOURCE_REVISION,
        )


@pytest.mark.parametrize(
    ("label_fields", "message"),
    [(["answer", "answer"], "unique"), ([" answer"], "trimmed"), ("answer", "list")],
)
def test_release_rejects_invalid_label_field_declarations(
    tmp_path: Path, label_fields: object, message: str
) -> None:
    raw = _release_spec()
    assert isinstance(raw["files"], list)
    assert isinstance(raw["files"][0], dict)
    raw["files"][0]["label_fields"] = label_fields

    with pytest.raises(ReleaseSpecError, match=message):
        build_dataset_release(
            spec_path=_write_spec(tmp_path, raw),
            repo_root=ROOT,
            output_dir=tmp_path / "release",
            source_revision=SOURCE_REVISION,
        )


@pytest.mark.parametrize("raw", [{}, [], "invalid"])
def test_release_rejects_invalid_json_roots(tmp_path: Path, raw: object) -> None:
    with pytest.raises(ReleaseSpecError, match=r"JSON object|fields mismatch"):
        build_dataset_release(
            spec_path=_write_spec(tmp_path, raw),
            repo_root=ROOT,
            output_dir=tmp_path / "release",
            source_revision=SOURCE_REVISION,
        )


def test_release_reports_unreadable_and_invalid_json_specs(tmp_path: Path) -> None:
    with pytest.raises(ReleaseSpecError, match="cannot read"):
        build_dataset_release(
            spec_path=tmp_path / "missing.json",
            repo_root=ROOT,
            output_dir=tmp_path / "missing-output",
            source_revision=SOURCE_REVISION,
        )
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    with pytest.raises(ReleaseSpecError, match="invalid JSON"):
        build_dataset_release(
            spec_path=invalid,
            repo_root=ROOT,
            output_dir=tmp_path / "invalid-output",
            source_revision=SOURCE_REVISION,
        )


def test_release_requires_existing_current_revision_and_clean_worktree(tmp_path: Path) -> None:
    repo, first_revision = _committed_release_repo(tmp_path)
    spec = repo / "configs" / "hf_dataset_release.json"

    with pytest.raises(ReleaseSpecError, match="does not exist"):
        build_dataset_release(
            spec_path=spec,
            repo_root=repo,
            output_dir=tmp_path / "nonexistent",
            source_revision=SOURCE_REVISION,
        )

    _git(repo, "commit", "--allow-empty", "-q", "-m", "second")
    with pytest.raises(ReleaseSpecError, match="current HEAD"):
        build_dataset_release(
            spec_path=spec,
            repo_root=repo,
            output_dir=tmp_path / "mismatched",
            source_revision=first_revision,
        )

    current_revision = _git(repo, "rev-parse", "HEAD")
    fixture = repo / "tests" / "fixtures" / "musique_answerable_sample.jsonl"
    fixture.write_text(fixture.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ReleaseSpecError, match="worktree must be clean"):
        build_dataset_release(
            spec_path=spec,
            repo_root=repo,
            output_dir=tmp_path / "dirty",
            source_revision=current_revision,
        )

    assert not (tmp_path / "nonexistent").exists()
    assert not (tmp_path / "mismatched").exists()
    assert not (tmp_path / "dirty").exists()


def test_release_compares_every_payload_with_the_committed_blob(tmp_path: Path) -> None:
    ignored_repo, _ = _committed_release_repo(tmp_path / "ignored")
    ignored_spec = ignored_repo / "configs" / "hf_dataset_release.json"
    raw = json.loads(ignored_spec.read_text(encoding="utf-8"))
    raw["files"][0]["source_path"] = "tests/fixtures/ignored.log"
    ignored_spec.write_text(json.dumps(raw), encoding="utf-8")
    (ignored_repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
    _git(ignored_repo, "add", "configs/hf_dataset_release.json", ".gitignore")
    _git(ignored_repo, "commit", "-q", "-m", "reference ignored payload")
    ignored_payload = ignored_repo / "tests" / "fixtures" / "ignored.log"
    ignored_payload.write_text("ignored but present\n", encoding="utf-8")

    with pytest.raises(ReleaseSpecError, match="regular blob"):
        build_dataset_release(
            spec_path=ignored_spec,
            repo_root=ignored_repo,
            output_dir=tmp_path / "ignored-output",
            source_revision=_git(ignored_repo, "rev-parse", "HEAD"),
        )

    assumed_repo, assumed_revision = _committed_release_repo(tmp_path / "assumed")
    assumed_fixture = assumed_repo / "tests" / "fixtures" / "musique_answerable_sample.jsonl"
    _git(
        assumed_repo,
        "update-index",
        "--assume-unchanged",
        assumed_fixture.relative_to(assumed_repo).as_posix(),
    )
    assumed_fixture.write_text("hidden modification\n", encoding="utf-8")

    with pytest.raises(ReleaseSpecError, match="bytes do not match"):
        build_dataset_release(
            spec_path=assumed_repo / "configs" / "hf_dataset_release.json",
            repo_root=assumed_repo,
            output_dir=tmp_path / "assumed-output",
            source_revision=assumed_revision,
        )


def test_release_removes_atomic_staging_after_publish_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, source_revision = _committed_release_repo(tmp_path)
    output = tmp_path / "release"

    def fail_replace(_: Path, __: Path) -> Path:
        raise OSError("simulated rename failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        build_dataset_release(
            spec_path=repo / "configs" / "hf_dataset_release.json",
            repo_root=repo,
            output_dir=output,
            source_revision=source_revision,
        )

    assert not output.exists()
    assert not list(tmp_path.glob(".rsicontext-release-*"))
