from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from typing import cast

import pytest

from rsicontext.experiment import load_api_profiles
from rsicontext.researcher import ResearcherRequest
from rsicontext.researcher.api import (
    API_RESEARCHER_SYSTEM_PROMPT,
    APIResearcherArtifact,
    APIResearcherCommandBuilder,
    APIResearcherError,
    api_researcher_system_prompt_hash,
    run_api_researcher_turn,
)

ROOT = Path(__file__).parents[1]
PROFILE_ID = "tencent-copilot-hy3-ioa-researcher"


def _manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "candidate_name": "api-candidate",
        "parent_artifact_id": "a" * 64,
        "mechanisms": [
            {
                "mechanism_id": "lexical",
                "description": "Rank chunks by query overlap.",
                "policy_paths": ["policy/policy.py"],
            }
        ],
        "evidence": [
            {
                "evidence_id": "visible",
                "kind": "visible-item-trace",
                "reference": "VISIBLE_FEEDBACK_BEGIN",
                "claim": "Visible failures motivate lexical selection.",
            }
        ],
        "predictions": [
            {
                "item_id": "visible-1",
                "probabilities": {"improve": 0.5, "unchanged": 0.4, "regress": 0.1},
                "mechanism_ids": ["lexical"],
                "evidence_ids": ["visible"],
            }
        ],
        "cost": {
            "researcher_input_tokens": 0,
            "researcher_output_tokens": 0,
            "evaluation_input_tokens": 0,
            "evaluation_output_tokens": 0,
            "gpu_seconds": 0.0,
            "wall_seconds": 0.0,
        },
        "promotion": {
            "decision": "hold",
            "expected_score_delta": 0.0,
            "max_regression_probability": 0.1,
            "rationale": "Qualification prediction.",
        },
    }


def _artifact_response(*, policy_source: str | None = None) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "policy_source": policy_source
            or (
                "from rsicontext.policy import LexicalPolicy\n\n"
                "class Policy(LexicalPolicy):\n"
                "    pass\n"
            ),
            "manifest": _manifest(),
        }
    )


def _stream(content: str) -> bytes:
    event = {
        "choices": [{"delta": {"content": content}, "finish_reason": "stop"}],
        "id": "research-response-1",
        "model": "hy3-ioa",
        "usage": {"completion_tokens": 300, "prompt_tokens": 700},
    }
    return f"data: {json.dumps(event)}\n\ndata: [DONE]\n\n".encode()


def test_researcher_profile_is_distinct_from_reader_but_uses_same_alias() -> None:
    profiles = load_api_profiles(ROOT / "configs" / "api_profiles.json")
    reader = profiles.get("tencent-copilot-hy3-ioa")
    researcher = profiles.get(PROFILE_ID)

    assert researcher.model == reader.model == "hy3-ioa"
    assert researcher.endpoint_env == reader.endpoint_env
    assert researcher.api_key_env == reader.api_key_env
    assert researcher.max_output_tokens == 8192
    assert researcher.profile_hash != reader.profile_hash
    assert len(api_researcher_system_prompt_hash()) == 64
    assert "question-answering reader" in API_RESEARCHER_SYSTEM_PROMPT


def test_api_artifact_parser_and_writer_replace_only_policy_and_manifest(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    policy = workspace / "policy"
    policy.mkdir(parents=True)
    (policy / "seed.py").write_text("class Policy:\n    pass\n", encoding="utf-8")

    artifact = APIResearcherArtifact.from_response(_artifact_response())
    artifact.write_workspace(workspace)

    assert sorted(path.name for path in policy.iterdir()) == ["policy.py"]
    assert "LexicalPolicy" in (policy / "policy.py").read_text(encoding="utf-8")
    assert (
        json.loads((workspace / "manifest.json").read_text(encoding="utf-8"))["parent_artifact_id"]
        == "a" * 64
    )
    assert sorted(path.name for path in workspace.iterdir()) == ["manifest.json", "policy"]


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ("```json\n{}\n```", "valid JSON"),
        (json.dumps({"schema_version": 1}), "fields"),
        (
            _artifact_response(policy_source="import os\nclass Policy:\n    pass\n"),
            "policy audit",
        ),
    ],
)
def test_api_artifact_fails_closed_without_partial_writes(
    tmp_path: Path, response: str, message: str
) -> None:
    workspace = tmp_path / "workspace"
    policy = workspace / "policy"
    policy.mkdir(parents=True)
    seed = policy / "seed.py"
    seed.write_text("class Policy:\n    pass\n", encoding="utf-8")

    with pytest.raises(APIResearcherError, match=message):
        APIResearcherArtifact.from_response(response).write_workspace(workspace)

    assert seed.is_file()
    assert not (workspace / "manifest.json").exists()


def test_api_researcher_turn_freezes_request_and_records_identity(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "policy").mkdir(parents=True)
    (workspace / "policy" / "seed.py").write_text("class Policy:\n    pass\n", encoding="utf-8")
    profile = load_api_profiles(ROOT / "configs" / "api_profiles.json").get(PROFILE_ID)
    requests: list[dict[str, object]] = []

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        assert request.data is not None
        requests.append(json.loads(cast(bytes, request.data)))
        return _stream(_artifact_response())

    result = run_api_researcher_turn(
        profile=profile,
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        api_key="secret",
        prompt="visible research prompt",
        workspace=workspace,
        transport=transport,
        timer=iter((1.0, 1.5)).__next__,
    )

    assert result.profile_id == PROFILE_ID
    assert result.profile_hash == profile.profile_hash
    assert result.response_model == "hy3-ioa"
    assert result.response_id == "research-response-1"
    assert result.input_tokens == 700
    assert result.output_tokens == 300
    assert result.elapsed_seconds == pytest.approx(0.5)
    assert requests[0]["temperature"] == 0.0
    assert requests[0]["seed"] == 42
    assert requests[0]["max_tokens"] == 8192
    messages = cast(list[dict[str, object]], requests[0]["messages"])
    assert messages[0]["content"] == API_RESEARCHER_SYSTEM_PROMPT
    assert messages[1]["content"] == "visible research prompt"
    assert "secret" not in json.dumps(result.to_dict())


def test_api_researcher_command_is_inert_and_prompt_stays_on_stdin(tmp_path: Path) -> None:
    request = ResearcherRequest(workspace=tmp_path, prompt="visible prompt", model="hy3-ioa")
    builder = APIResearcherCommandBuilder(
        python_executable=Path(sys.executable),
        profiles_path=ROOT / "configs" / "api_profiles.json",
        profile_id=PROFILE_ID,
    )

    spec = builder.build(request)

    assert spec.output_format == "jsonl"
    assert spec.cwd == tmp_path.resolve()
    assert spec.argv[:3] == (
        str(Path(sys.executable).absolute()),
        "-m",
        "rsicontext.researcher.api",
    )
    assert "visible prompt" not in spec.argv
    assert spec.stdin == "visible prompt"
