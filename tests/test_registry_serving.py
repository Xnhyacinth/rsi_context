from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from rsicontext.registry import (
    ServingProfile,
    build_serve_command,
    load_registry,
    load_serving_profiles,
)
from rsicontext.registry.schema import RegistryError

ROOT = Path(__file__).parents[1]


def test_serving_profiles_cover_required_models_and_contexts() -> None:
    registry = load_registry(ROOT / "configs" / "registry.json")
    profiles = load_serving_profiles(ROOT / "configs" / "serving_profiles.json", registry)

    observed = {(profile.model_id, profile.max_model_len) for profile in profiles.profiles}
    assert observed == {
        ("qwen3.6-27b", 131072),
        ("qwen3.6-27b", 262144),
        ("llama-3.3-70b-instruct", 131072),
    }
    assert all(profile.dtype == "bfloat16" for profile in profiles.profiles)
    assert all(profile.kv_cache_dtype == "bfloat16" for profile in profiles.profiles)
    assert all(not profile.enable_prefix_caching for profile in profiles.profiles)
    assert all(profile.tensor_parallel_size == 8 for profile in profiles.profiles)
    assert all(profile.data_parallel_size == 1 for profile in profiles.profiles)
    assert all(profile.host == "127.0.0.1" for profile in profiles.profiles)
    assert all(profile.port == 8017 for profile in profiles.profiles)
    profile = profiles.profiles[0]
    assert profile.chat_completions_endpoint == "http://127.0.0.1:8017/v1/chat/completions"
    assert len(profile.profile_hash) == 64
    assert (
        replace(profile, max_num_seqs=profile.max_num_seqs + 1).profile_hash != profile.profile_hash
    )


def test_qwen_command_has_language_reasoning_and_hold_flags() -> None:
    registry = load_registry(ROOT / "configs" / "registry.json")
    profiles = load_serving_profiles(ROOT / "configs" / "serving_profiles.json", registry)
    profile = profiles.get("qwen3.6-27b-262k-bf16-h200x8")
    model = registry.select([profile.model_id])[0]

    command = build_serve_command(profile, model)

    assert command.startswith("bash /workspace/wynckeliao/ops/gpu/hold.sh wrap 0,1,2,3,4,5,6,7 --")
    assert "--max-model-len 262144" in command
    assert "--tensor-parallel-size 8 --data-parallel-size 1" in command
    assert "--host 127.0.0.1 --port 8017" in command
    assert "--no-enable-prefix-caching" in command
    assert "--enable-chunked-prefill" in command
    assert "--language-model-only --reasoning-parser qwen3" in command


def test_llama_profile_uses_tp8_dp1_without_qwen_flags() -> None:
    registry = load_registry(ROOT / "configs" / "registry.json")
    profiles = load_serving_profiles(ROOT / "configs" / "serving_profiles.json", registry)
    profile = profiles.get("llama-3.3-70b-128k-bf16-h200x8")
    model = registry.select([profile.model_id])[0]

    command = build_serve_command(profile, model)

    assert "--tensor-parallel-size 8 --data-parallel-size 1" in command
    assert "--language-model-only" not in command
    assert "--reasoning-parser" not in command


def test_serving_profiles_reject_non_eight_gpu_topology(tmp_path: Path) -> None:
    registry = load_registry(ROOT / "configs" / "registry.json")
    raw = json.loads((ROOT / "configs" / "serving_profiles.json").read_text(encoding="utf-8"))
    raw["profiles"][0]["data_parallel_size"] = 7
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(RegistryError, match="exactly 8 GPUs"):
        load_serving_profiles(path, registry)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("max_model_len", True, "integer capacities"),
        ("seed", False, "seed"),
        ("gpu_memory_utilization", True, "gpu_memory_utilization"),
        ("port", True, "port"),
        ("port", 65_536, "port"),
        ("host", "0.0.0.0", "loopback"),
    ],
)
def test_serving_profiles_reject_booleans_in_numeric_fields(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    registry = load_registry(ROOT / "configs" / "registry.json")
    raw = json.loads((ROOT / "configs" / "serving_profiles.json").read_text(encoding="utf-8"))
    raw["profiles"][0][field] = value
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(RegistryError, match=message):
        load_serving_profiles(path, registry)


def test_serving_profiles_reject_unknown_fields(tmp_path: Path) -> None:
    registry = load_registry(ROOT / "configs" / "registry.json")
    raw = json.loads((ROOT / "configs" / "serving_profiles.json").read_text(encoding="utf-8"))
    raw["profiles"][0]["temperature"] = 0.7
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(RegistryError, match="unexpected"):
        load_serving_profiles(path, registry)

    top_level = json.loads((ROOT / "configs" / "serving_profiles.json").read_text(encoding="utf-8"))
    top_level["temperature"] = 0.7
    path.write_text(json.dumps(top_level), encoding="utf-8")
    with pytest.raises(RegistryError, match="top-level"):
        load_serving_profiles(path, registry)


def test_direct_serving_profile_construction_cannot_bypass_validation() -> None:
    raw = json.loads((ROOT / "configs" / "serving_profiles.json").read_text(encoding="utf-8"))
    raw["profiles"][0]["max_model_len"] = True

    with pytest.raises(RegistryError, match="integer capacities"):
        ServingProfile(**raw["profiles"][0])
