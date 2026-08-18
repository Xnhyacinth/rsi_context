from __future__ import annotations

import json
import urllib.request
from dataclasses import replace
from pathlib import Path

import pytest

from rsicontext.experiment import APIProfile, BudgetSpec, ModelSpec, RunSpec, Split, Track
from rsicontext.experiment.runtime_attestation import (
    EndpointObservation,
    FormalRunDescriptor,
    FormalRunError,
    ModelContentEvidence,
    ObservedModel,
    RuntimeCommandEvidence,
    attest_run,
    canonical_reader_endpoint,
    fingerprint_model_directory,
    observe_runtime_endpoint,
    observe_runtime_process,
    runtime_command_digest,
)
from rsicontext.registry import ServingProfile, load_registry
from rsicontext.registry.schema import RegistryEntry
from rsicontext.security.isolation import IsolationAttestation

ROOT = Path(__file__).parents[1]
MODEL_REVISION = "1b559cf7215ebe67ff10758e14f6293ba883223b"
MODEL_NAME = "Qwen/Qwen3.6-27B"
ENDPOINT = "http://127.0.0.1:8000/v1/chat/completions"


def _stack(split: Split) -> tuple[RunSpec, ServingProfile, APIProfile, RegistryEntry]:
    registry_model = load_registry(ROOT / "configs" / "registry.json").select(["qwen3.6-27b"])[0]
    serving_profile = ServingProfile(
        id="test-qwen",
        model_id="qwen3.6-27b",
        max_model_len=131_072,
        tensor_parallel_size=8,
        data_parallel_size=1,
        dtype="bfloat16",
        kv_cache_dtype="bfloat16",
        gpu_memory_utilization=0.9,
        max_num_batched_tokens=8192,
        max_num_seqs=4,
        seed=42,
        enable_chunked_prefill=True,
        enable_prefix_caching=False,
        language_model_only=True,
        reasoning_parser="qwen3",
    )
    reader_profile = APIProfile(
        id="test-local-qwen",
        provider="local-vllm",
        endpoint_env="TEST_ENDPOINT",
        api_key_env="TEST_KEY",
        allowed_host="127.0.0.1",
        model=MODEL_NAME,
        protocol="chat-completions-sse",
        evaluation_max_model_len=131_072,
        max_output_tokens=512,
        seed=42,
        temperature=0.0,
        provider_revision=MODEL_REVISION,
        chat_template_enable_thinking=False,
    )
    run = RunSpec(
        experiment="formal-test",
        dataset_revision="dataset-revision",
        evaluator_revision="evaluator-revision",
        policy_hash="policy-hash",
        serving_profile_hash=serving_profile.profile_hash,
        reader_profile_hash=reader_profile.profile_hash,
        chat_template_enable_thinking=False,
        model=ModelSpec(MODEL_NAME, MODEL_REVISION, MODEL_REVISION, 131_072),
        budget=BudgetSpec(32_000, 512, target_calls=1),
        split=split,
        track=Track.SINGLE_READER,
        seed=42,
    )
    return run, serving_profile, reader_profile, registry_model


def _endpoint_observation(endpoint: str = ENDPOINT) -> EndpointObservation:
    return EndpointObservation(
        evidence_source="live-http",
        observed_at="2026-08-14T12:00:00Z",
        endpoint=endpoint,
        version="0.25.1",
        version_payload_sha256="1" * 64,
        models_payload_sha256="2" * 64,
        models=(ObservedModel(id=MODEL_NAME, root=MODEL_NAME, parent=None),),
    )


def _isolation(source: str = "observed-linux") -> IsolationAttestation:
    return IsolationAttestation(
        evidence_source=source,
        observed_at="2026-08-14T12:00:00Z",
        evaluator_pid=1200,
        researcher_pid=1100,
        evaluator_container_namespace="mnt:[42]",
        researcher_container_namespace="mnt:[41]",
        evaluator_cgroup="/rsibench/evaluator",
        researcher_cgroup="/rsibench/researcher",
        evaluator_pid_namespace="pid:[52]",
        researcher_pid_namespace="pid:[51]",
        network_mode="none",
        read_only_mounts=("/sealed", "/evaluator"),
        required_read_only_mounts=("/sealed", "/evaluator"),
    )


def _attest(
    *,
    split: Split = Split.GATE,
    endpoint: str = ENDPOINT,
    observation: EndpointObservation | None = None,
    isolation: IsolationAttestation | None = None,
    qualification_only: bool = False,
) -> FormalRunDescriptor:
    run, serving_profile, reader_profile, registry_model = _stack(split)
    return attest_run(
        run_spec=run,
        serving_profile=serving_profile,
        reader_profile=reader_profile,
        registry_model=registry_model,
        endpoint=endpoint,
        endpoint_observation=observation or _endpoint_observation(endpoint),
        model_content=ModelContentEvidence(
            evidence_source="declared-content-digest",
            sha256="3" * 64,
            locator="registry-sidecar:model.safetensors.index.json",
        ),
        runtime_command=RuntimeCommandEvidence(
            evidence_source="observed-proc",
            pid=900,
            sha256=runtime_command_digest(
                ("vllm", "serve", MODEL_NAME, "--revision", MODEL_REVISION)
            ),
        ),
        isolation=isolation,
        qualification_only=qualification_only,
    )


def test_preflight_cannot_self_certify_formal_policy_worker_isolation() -> None:
    with pytest.raises(FormalRunError, match="policy-worker launcher"):
        _attest(isolation=_isolation())


def test_spoofed_reader_identity_is_rejected() -> None:
    spoofed = replace(
        _endpoint_observation(),
        models=(ObservedModel(id=MODEL_NAME, root="attacker/lookalike", parent=None),),
    )

    with pytest.raises(FormalRunError, match="root"):
        _attest(observation=spoofed, isolation=_isolation())


def test_endpoint_drift_is_rejected() -> None:
    observed_elsewhere = _endpoint_observation("http://127.0.0.1:8001/v1/chat/completions")

    with pytest.raises(FormalRunError, match="endpoint"):
        _attest(observation=observed_elsewhere, isolation=_isolation())


@pytest.mark.parametrize("isolation", [None, _isolation("declaration")])
def test_gate_rejects_missing_or_declaration_only_isolation(
    isolation: IsolationAttestation | None,
) -> None:
    with pytest.raises(FormalRunError, match="isolation"):
        _attest(isolation=isolation)


def test_formal_run_rejects_declaration_only_runtime_command() -> None:
    run, serving_profile, reader_profile, registry_model = _stack(Split.GATE)

    with pytest.raises(FormalRunError, match="runtime command"):
        attest_run(
            run_spec=run,
            serving_profile=serving_profile,
            reader_profile=reader_profile,
            registry_model=registry_model,
            endpoint=ENDPOINT,
            endpoint_observation=_endpoint_observation(),
            model_content=ModelContentEvidence(
                "declared-content-digest", "3" * 64, "registry-sidecar"
            ),
            runtime_command=RuntimeCommandEvidence(
                "declaration",
                900,
                runtime_command_digest(("vllm", "serve", MODEL_NAME)),
            ),
            isolation=_isolation(),
        )


def test_visible_qualification_can_explicitly_remain_ineligible() -> None:
    descriptor = _attest(
        split=Split.VISIBLE,
        isolation=None,
        qualification_only=True,
    )

    assert descriptor.formal_eligible is False
    assert descriptor.ineligibility_reasons == ("visible qualification explicitly non-formal",)
    assert descriptor.isolation is None


def test_gate_cannot_be_downgraded_to_qualification() -> None:
    with pytest.raises(FormalRunError, match="visible"):
        _attest(split=Split.SEALED, qualification_only=True)


def test_canonical_endpoint_is_credential_free_and_stable() -> None:
    assert canonical_reader_endpoint("HTTP://LOCALHOST:80/v1/chat/completions") == (
        "http://localhost/v1/chat/completions"
    )
    with pytest.raises(FormalRunError, match="credentials"):
        canonical_reader_endpoint("http://user:secret@localhost/v1/chat/completions")
    with pytest.raises(FormalRunError, match="query"):
        canonical_reader_endpoint("http://localhost/v1/chat/completions?token=secret")


def test_live_endpoint_observation_fetches_version_and_models_without_credentials() -> None:
    requests: list[urllib.request.Request] = []

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        requests.append(request)
        if request.full_url.endswith("/version"):
            return b'{"version":"0.25.1"}'
        return json.dumps(
            {
                "object": "list",
                "data": [{"id": MODEL_NAME, "root": MODEL_NAME, "parent": None}],
            }
        ).encode()

    observation = observe_runtime_endpoint(
        ENDPOINT,
        transport=transport,
        observed_at="2026-08-14T12:00:00Z",
    )

    assert [request.full_url for request in requests] == [
        "http://127.0.0.1:8000/version",
        "http://127.0.0.1:8000/v1/models",
    ]
    assert all(request.get_header("Authorization") is None for request in requests)
    assert observation.endpoint == ENDPOINT
    assert observation.models == (ObservedModel(MODEL_NAME, MODEL_NAME, None),)


def test_runtime_process_observation_hashes_proc_cmdline(tmp_path: Path) -> None:
    process = tmp_path / "proc" / "900"
    process.mkdir(parents=True)
    command = ("vllm", "serve", MODEL_NAME, "--revision", MODEL_REVISION)
    (process / "cmdline").write_bytes(b"\0".join(part.encode() for part in command) + b"\0")

    evidence = observe_runtime_process(900, proc_root=tmp_path / "proc")

    assert evidence.evidence_source == "observed-proc"
    assert evidence.pid == 900
    assert evidence.sha256 == runtime_command_digest(command)


def test_model_directory_fingerprint_changes_with_bytes_and_rejects_symlinks(
    tmp_path: Path,
) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text('{"model":"qwen"}', encoding="utf-8")
    first = fingerprint_model_directory(model_dir)
    same = fingerprint_model_directory(model_dir)
    (model_dir / "config.json").write_text('{"model":"other"}', encoding="utf-8")
    changed = fingerprint_model_directory(model_dir)

    assert first == same
    assert first.sha256 != changed.sha256
    (model_dir / "linked").symlink_to(model_dir / "config.json")
    with pytest.raises(FormalRunError, match="symlink"):
        fingerprint_model_directory(model_dir)
