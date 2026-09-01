from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

from rsicontext.campaign.autonomous_dynamic import (
    DynamicFreshEvaluator,
    DynamicReaderIdentity,
    VisibleItemFeedback,
    _build_research_prompt,
    build_visible_feedback,
    public_visible_items_fingerprint,
    run_autonomous_dynamic_pilot,
)
from rsicontext.campaign.researcher import ResearchRoundRequest
from rsicontext.datasets import generate_dynamic_long_context_dataset
from rsicontext.eval import (
    EvaluationItem,
    OpenAICompatibleReader,
    ReaderOutput,
    extractive_span_match,
)
from rsicontext.experiment import Split
from rsicontext.experiment.api import load_api_profiles
from rsicontext.policy import Artifact, Budget, ContextPack, DocumentChunk
from rsicontext.researcher import ProcessLimits


class GoldEvidenceReader:
    def __init__(self, *, seed: str, items_per_profile: int) -> None:
        dataset = generate_dynamic_long_context_dataset(
            seed=seed,
            items_per_profile=items_per_profile,
        )
        self.expected = {
            item.evaluation_item.query: (
                item.evaluation_item.answer,
                item.evaluation_item.gold_chunk_ids,
            )
            for item in dataset.visible_items()
        }
        self.calls = 0

    def read(self, query: str, context: ContextPack) -> ReaderOutput:
        self.calls += 1
        answer, gold_ids = self.expected[query]
        selected = {span.chunk_id for span in context.spans}
        prediction = answer if gold_ids <= selected else ""
        return ReaderOutput(prediction, context.token_count + 3, int(bool(prediction)))


def _seed_policy(tmp_path: Path) -> Path:
    policy = tmp_path / "initial-policy"
    policy.mkdir(parents=True)
    (policy / "seed.py").write_text(
        "from rsicontext.policy import LexicalPolicy\n\nclass Policy(LexicalPolicy):\n    pass\n",
        encoding="utf-8",
    )
    return policy


def _declared_reader_identity(model: str) -> DynamicReaderIdentity:
    return DynamicReaderIdentity(
        profile_id="test-reader",
        profile_hash="a" * 64,
        provider="test-provider",
        requested_model=model,
        provider_revision=None,
        max_model_len=131_072,
        max_output_tokens=64,
        seed=42,
        temperature=0.0,
        chat_template_enable_thinking=False,
        serving_profile_id=None,
        serving_profile_hash=None,
    )


def _fake_codex(
    tmp_path: Path,
    *,
    hardcode: bool = False,
    mutate_contract: bool = False,
    policy_source: str | None = None,
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    executable = tmp_path / "fake-codex"
    default_policy = (
        "from rsicontext.policy import LexicalPolicy\n\nclass Policy(LexicalPolicy):\n    pass\n"
    )
    policy_literal = repr(policy_source or default_policy)
    script = """#!/usr/bin/python3
import json
import pathlib
import sys

prompt = sys.stdin.read()
if "Do not use from __future__ imports" not in prompt or "module/class constants" not in prompt:
    raise SystemExit("missing policy audit constraints")
if "Do not run mypy" not in prompt:
    raise SystemExit("missing cache-producing tool constraint")
if "You choose the next hypothesis for compiler H" not in prompt:
    raise SystemExit("missing RSI hypothesis contract")
if "re.compile and re.findall inside functions are allowed" not in prompt:
    raise SystemExit("missing re.compile allowance")
if "LAST_INVALID_SUBMISSION_BEGIN" not in prompt:
    raise SystemExit("missing invalid-submission feedback")
start = prompt.index("MANIFEST_TEMPLATE_BEGIN\\n") + len("MANIFEST_TEMPLATE_BEGIN\\n")
end = prompt.index("\\nMANIFEST_TEMPLATE_END", start)
manifest = json.loads(prompt[start:end])
if manifest["candidate_name"].endswith("r1"):
    if "PRIOR_CANDIDATE_VISIBLE_OUTCOMES_BEGIN" not in prompt or '"prediction"' not in prompt:
        raise SystemExit("missing prior candidate item feedback")
workspace = pathlib.Path.cwd()
POLICY_WRITE
(workspace / "manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\\n",
    encoding="utf-8",
)
CONTRACT_MUTATION
print(json.dumps({
    "type": "item.completed",
    "item": {"type": "agent_message", "text": "TRACE-SECRET"},
}))
print("STDERR-SECRET", file=sys.stderr)
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 17, "output_tokens": 5}}))
"""
    generic_write = f"""(workspace / "policy" / "policy.py").write_text(
    {policy_literal},
    encoding="utf-8",
)"""
    hardcoded_write = """(workspace / "policy" / "policy.py").write_text(
    "ITEM = " + repr(manifest["predictions"][0]["item_id"]) + "\\n",
    encoding="utf-8",
)"""
    contract_mutation = (
        "(workspace.parents[2] / 'run_contract.json').write_text('{}', encoding='utf-8')"
        if mutate_contract
        else ""
    )
    executable.write_text(
        script.replace("POLICY_WRITE", hardcoded_write if hardcode else generic_write).replace(
            "CONTRACT_MUTATION", contract_mutation
        ),
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable


def _failing_codex(tmp_path: Path, *, mutate_executable: bool = False) -> Path:
    executable = tmp_path / "failing-codex"
    mutation = (
        "import pathlib\npathlib.Path(sys.argv[0]).write_text('# changed\\n', encoding='utf-8')\n"
        if mutate_executable
        else ""
    )
    executable.write_text(
        (
            "#!/usr/bin/python3\n"
            "import sys\n"
            + mutation
            + 'print("FAILURE-SECRET", file=sys.stderr)\n'
            + "raise SystemExit(7)\n"
        ),
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable


def _json_failing_codex(tmp_path: Path) -> Path:
    executable = tmp_path / "json-failing-codex"
    executable.write_text(
        (
            "#!/usr/bin/python3\n"
            "import sys\n"
            "print('Traceback (most recent call last):', file=sys.stderr)\n"
            "print('APIResearcherError: API researcher response is not valid JSON', "
            "file=sys.stderr)\n"
            "raise SystemExit(1)\n"
        ),
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable


def _sleeping_codex(tmp_path: Path) -> Path:
    executable = tmp_path / "sleeping-codex"
    executable.write_text(
        "#!/usr/bin/python3\nimport time\ntime.sleep(5)\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable


def _fake_api_worker(tmp_path: Path) -> Path:
    executable = tmp_path / "fake-api-python"
    executable.write_text(
        "#!/usr/bin/python3\n"
        "import json\n"
        "import pathlib\n"
        "import sys\n"
        "prompt = sys.stdin.read()\n"
        "if 'Return exactly one JSON artifact' not in prompt:\n"
        "    raise SystemExit('missing API artifact delivery contract')\n"
        "start = prompt.index('MANIFEST_TEMPLATE_BEGIN\\n') + len('MANIFEST_TEMPLATE_BEGIN\\n')\n"
        "end = prompt.index('\\nMANIFEST_TEMPLATE_END', start)\n"
        "manifest = json.loads(prompt[start:end])\n"
        "workspace = pathlib.Path.cwd()\n"
        "(workspace / 'policy' / 'policy.py').write_text(\n"
        "    'from rsicontext.policy import LexicalPolicy\\n\\n'\n"
        "    'class Policy(LexicalPolicy):\\n    pass\\n',\n"
        "    encoding='utf-8',\n"
        ")\n"
        "(workspace / 'manifest.json').write_text(\n"
        "    json.dumps(manifest, indent=2, sort_keys=True) + '\\n', encoding='utf-8'\n"
        ")\n"
        "print(json.dumps({'type': 'turn.completed', 'usage': "
        "{'input_tokens': 23, 'output_tokens': 7}}))\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable


def test_visible_feedback_contains_only_visible_item_provenance(tmp_path: Path) -> None:
    seed = "feedback-boundary"
    dataset = generate_dynamic_long_context_dataset(seed=seed, items_per_profile=1)
    reader = GoldEvidenceReader(seed=seed, items_per_profile=1)
    evaluator = DynamicFreshEvaluator(
        items=tuple(item.evaluation_item for item in dataset.visible_items()),
        reader=reader,
        budget=Budget(8_192),
        entrypoint="seed.py",
    )

    feedback = build_visible_feedback(
        dataset.visible_items(),
        evaluator.evaluate_directory(_seed_policy(tmp_path), round_index=-1),
        baseline_predictions=evaluator.observations[-1].predictions,
    )
    payload = json.dumps([item.to_dict() for item in feedback], sort_keys=True)

    for item in dataset.visible_items():
        assert item.evaluation_item.item_id in payload
        assert item.evaluation_item.query in payload
        assert item.evaluation_item.answer in payload
        assert item.evaluation_item.gold_chunk_ids
        assert item.evaluation_item.gold_chunk_ids <= {
            chunk.chunk_id for visible in feedback for chunk in visible.gold_evidence
        }
    for split_item in (
        *dataset.evaluator_items(Split.GATE),
        *dataset.evaluator_items(Split.SEALED),
    ):
        assert split_item.evaluation_item.item_id not in payload
        assert split_item.evaluation_item.query not in payload


def test_dynamic_fresh_evaluator_accounts_one_reader_call_per_item(tmp_path: Path) -> None:
    seed = "fresh-evaluator"
    dataset = generate_dynamic_long_context_dataset(seed=seed, items_per_profile=1)
    reader = GoldEvidenceReader(seed=seed, items_per_profile=1)
    evaluator = DynamicFreshEvaluator(
        items=tuple(item.evaluation_item for item in dataset.visible_items()),
        reader=reader,
        budget=Budget(8_192),
    )
    policy = tmp_path / "policy"
    policy.mkdir()
    (policy / "policy.py").write_text(
        "from rsicontext.policy import LexicalPolicy\n\nclass Policy(LexicalPolicy):\n    pass\n",
        encoding="utf-8",
    )

    result = evaluator(policy, round_index=0)

    assert tuple(item_id for item_id, _ in result.item_scores) == tuple(
        item.evaluation_item.item_id for item in dataset.visible_items()
    )
    assert evaluator.observations[-1].reader_calls == len(dataset.visible_items())
    assert reader.calls == len(dataset.visible_items())
    assert result.reader_input_tokens == evaluator.observations[-1].reader_input_tokens


def test_dynamic_reader_identity_is_built_from_one_api_profile() -> None:
    profile = load_api_profiles(Path(__file__).parents[1] / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )

    identity = DynamicReaderIdentity.from_profile(profile, max_output_tokens=128)

    assert identity.profile_id == profile.id
    assert identity.profile_hash == profile.profile_hash
    assert identity.max_output_tokens == 128
    assert identity.serving_profile_id is None
    assert identity.serving_profile_hash is None


def test_dynamic_reader_identity_rejects_boolean_output_limit() -> None:
    profile = load_api_profiles(Path(__file__).parents[1] / "configs" / "api_profiles.json").get(
        "tencent-copilot-hy3-ioa"
    )

    with pytest.raises((TypeError, ValueError), match="output limit"):
        DynamicReaderIdentity.from_profile(profile, max_output_tokens=True)


def test_api_research_prompt_requests_artifact_instead_of_workspace_edits(tmp_path: Path) -> None:
    policy_directory = tmp_path / "policy"
    policy_directory.mkdir()
    (policy_directory / "seed.py").write_text(
        "from rsicontext.policy import LexicalPolicy\n\nclass Policy(LexicalPolicy):\n    pass\n",
        encoding="utf-8",
    )
    feedback = (
        VisibleItemFeedback(
            item_id="visible-0",
            query="Which code is present?",
            reference_answer="amber",
            baseline_score=0.0,
            baseline_prediction="",
            gold_evidence=(),
        ),
    )
    request = ResearchRoundRequest(
        round_index=0,
        workspace=tmp_path,
        policy_directory=policy_directory,
        manifest_path=tmp_path / "manifest.json",
        parent_artifact_id="a" * 64,
        incumbent_artifact_id=None,
        previous_score=0.0,
        incumbent_score=0.0,
        prediction_item_ids=(feedback[0].item_id,),
        last_invalid_reason=None,
    )

    prompt = _build_research_prompt(request, feedback, None, artifact_delivery="api-json")

    assert "Return exactly one JSON artifact" in prompt
    assert "Do not modify the workspace" in prompt
    assert "Modify only policy/*.py" not in prompt
    assert "artifact.chunks" in prompt
    assert "budget.max_tokens" in prompt
    assert "return a ContextPack" in prompt
    assert "PARENT_POLICY_BEGIN" in prompt
    assert "class Policy(LexicalPolicy)" in prompt
    assert "ContextPack(spans=" in prompt


def test_api_researcher_runs_through_campaign_with_distinct_profile_identity(
    tmp_path: Path,
) -> None:
    seed = "api-researcher-campaign"
    result = run_autonomous_dynamic_pilot(
        initial_policy_directory=_seed_policy(tmp_path),
        output_directory=tmp_path / "api-result",
        reader=GoldEvidenceReader(seed=seed, items_per_profile=1),
        researcher_kind="api",
        researcher_executable=str(_fake_api_worker(tmp_path)),
        researcher_api_profiles_path=Path(__file__).parents[1] / "configs" / "api_profiles.json",
        researcher_api_profile_id="tencent-copilot-hy3-ioa-researcher",
        dataset_seed=seed,
        items_per_profile=1,
        rounds=1,
        process_limits=ProcessLimits(timeout_seconds=2),
    )

    assert result.campaign.rounds[0].valid is True
    assert result.researcher_usage[0].input_tokens == 23
    assert result.researcher_identity.kind == "api"
    assert result.researcher_identity.profile_id == "tencent-copilot-hy3-ioa-researcher"
    assert result.researcher_identity.profile_hash
    assert result.researcher_identity.system_prompt_sha256
    assert result.researcher_identity.model == "hy3-ioa"


def test_api_command_preserves_virtual_environment_launcher(tmp_path: Path) -> None:
    launcher = tmp_path / "venv-python"
    launcher.symlink_to(_fake_api_worker(tmp_path))
    result = run_autonomous_dynamic_pilot(
        initial_policy_directory=_seed_policy(tmp_path),
        output_directory=tmp_path / "symlink-result",
        reader=GoldEvidenceReader(seed="symlink-launcher", items_per_profile=1),
        researcher_kind="api",
        researcher_executable=str(launcher),
        researcher_api_profiles_path=Path(__file__).parents[1] / "configs" / "api_profiles.json",
        researcher_api_profile_id="tencent-copilot-hy3-ioa-researcher",
        dataset_seed="symlink-launcher",
        items_per_profile=1,
        rounds=1,
        process_limits=ProcessLimits(timeout_seconds=2),
    )

    assert result.researcher_identity.executable_path == str(launcher.absolute())


def test_two_round_codex_micro_pilot_records_usage_and_refuses_overwrite(tmp_path: Path) -> None:
    seed = "autonomous-pilot-test"
    reader = GoldEvidenceReader(seed=seed, items_per_profile=1)
    output = tmp_path / "result"

    result = run_autonomous_dynamic_pilot(
        initial_policy_directory=_seed_policy(tmp_path),
        output_directory=output,
        reader=reader,
        researcher_kind="codex",
        researcher_executable=str(_fake_codex(tmp_path)),
        dataset_seed=seed,
        items_per_profile=1,
        rounds=2,
        process_limits=ProcessLimits(timeout_seconds=2),
        reader_identity=DynamicReaderIdentity(
            profile_id="local-reader",
            profile_hash="a" * 64,
            provider="vllm-0.25.1",
            requested_model="Qwen/Qwen3.6-27B",
            provider_revision="b" * 40,
            max_model_len=131_072,
            max_output_tokens=512,
            seed=42,
            temperature=0.0,
            chat_template_enable_thinking=False,
            serving_profile_id="qwen-local",
            serving_profile_hash="c" * 64,
        ),
    )

    assert result.split == "visible"
    assert result.schema_version == 4
    assert result.run_contract.rounds == 2
    assert result.run_contract.max_reader_calls == 6
    assert result.run_contract_sha256 == result.run_contract.contract_sha256
    assert (tmp_path / "result" / "run_contract.json").is_file()
    assert result.qualification_only is True
    assert result.autonomous_researcher is True
    assert result.formal_sealed_isolation is False
    assert result.reader_calls == 6
    assert reader.calls == 6
    assert [usage.input_tokens for usage in result.researcher_usage] == [17, 17]
    assert len(result.campaign.rounds) == 2
    stored = json.loads((output / "pilot_summary.json").read_text(encoding="utf-8"))
    assert stored["artifact_summary"]["selected_round"] == result.campaign.selected_round
    assert stored["researcher_usage"][0]["output_tokens"] == 5
    assert stored["reader_identity"]["chat_template_enable_thinking"] is False
    assert stored["reader_identity"]["serving_profile_hash"] == "c" * 64
    assert stored["researcher_identity"]["kind"] == "codex"
    assert stored["researcher_identity"]["executable_sha256"]
    assert len(stored["researcher_traces"]) == 2
    assert stored["researcher_traces"][0]["round_index"] == 0
    assert "VISIBLE_FEEDBACK_BEGIN" in stored["researcher_traces"][0]["prompt"]
    assert stored["researcher_traces"][0]["prompt_sha256"]
    assert stored["researcher_traces"][0]["process"]["events"][-1]["kind"] == "complete"
    serialized_process = json.dumps(stored["researcher_traces"][0]["process"])
    assert "TRACE-SECRET" not in serialized_process
    assert "STDERR-SECRET" not in serialized_process
    assert stored["researcher_traces"][0]["process"]["events"][0]["payload_sha256"]
    assert stored["researcher_traces"][0]["process"]["stderr_sha256"]
    assert [item["round_index"] for item in stored["evaluation_observations"]] == [-1, 0, 1]
    assert stored["evaluation_observations"][0]["predictions"]
    assert "autonomous-pilot-test" not in json.dumps(stored)

    with pytest.raises(FileExistsError):
        run_autonomous_dynamic_pilot(
            initial_policy_directory=_seed_policy(tmp_path / "again"),
            output_directory=output,
            reader=reader,
            researcher_executable=str(_fake_codex(tmp_path / "again-executable")),
            dataset_seed=seed,
            items_per_profile=1,
            rounds=1,
            process_limits=ProcessLimits(timeout_seconds=2),
        )


def test_pilot_rejects_candidate_that_hardcodes_visible_identifiers(tmp_path: Path) -> None:
    executable = _fake_codex(tmp_path, hardcode=True)
    output = tmp_path / "result"

    with pytest.raises(ValueError, match="hardcode"):
        run_autonomous_dynamic_pilot(
            initial_policy_directory=_seed_policy(tmp_path),
            output_directory=output,
            reader=GoldEvidenceReader(seed="hardcode", items_per_profile=1),
            researcher_executable=str(executable),
            dataset_seed="hardcode",
            items_per_profile=1,
            rounds=1,
            process_limits=ProcessLimits(timeout_seconds=2),
        )

    failure = json.loads((output / "failure.json").read_text(encoding="utf-8"))
    assert failure["status"] == "failed"
    assert failure["schema_version"] == 4
    assert failure["dataset_fingerprint"]
    assert "reader_identity" in failure
    assert failure["error_type"] == "ValueError"
    assert failure["researcher_prompts"][0]["round_index"] == 0
    assert failure["processes"][0]["usage"]["input_tokens"] == 17


def test_process_failure_consumes_slot_without_raw_output(tmp_path: Path) -> None:
    output = tmp_path / "failed-process"
    reader = GoldEvidenceReader(seed="process-failure", items_per_profile=1)

    result = run_autonomous_dynamic_pilot(
        initial_policy_directory=_seed_policy(tmp_path),
        output_directory=output,
        reader=reader,
        researcher_executable=str(_failing_codex(tmp_path)),
        dataset_seed="process-failure",
        items_per_profile=1,
        rounds=1,
        process_limits=ProcessLimits(timeout_seconds=2),
    )

    assert result.campaign.rounds[0].valid is False
    assert result.campaign.selected_round is None
    assert result.cost_accounting_complete is False
    assert result.process_failures[0].round_index == 0
    assert result.process_failures[0].stderr_bytes is not None
    assert result.process_failures[0].stderr_bytes > 0
    assert reader.calls == 2
    assert not (output / "failure.json").exists()
    stored = json.loads((output / "pilot_summary.json").read_text(encoding="utf-8"))
    assert stored["cost_accounting_complete"] is False
    assert stored["process_failures"][0]["round_index"] == 0
    assert stored["researcher_traces"][0]["process"] is None
    assert stored["researcher_traces"][0]["failure"]["stderr_bytes"] > 0
    assert stored["process_failures"][0]["diagnostic"] == (
        "researcher process exited with status 7"
    )
    assert "FAILURE-SECRET" not in json.dumps(stored)


def test_process_failure_exposes_exception_line_to_the_next_prompt(tmp_path: Path) -> None:
    output = tmp_path / "json-failed-process"
    reader = GoldEvidenceReader(seed="json-process-failure", items_per_profile=1)

    result = run_autonomous_dynamic_pilot(
        initial_policy_directory=_seed_policy(tmp_path),
        output_directory=output,
        reader=reader,
        researcher_executable=str(_json_failing_codex(tmp_path)),
        dataset_seed="json-process-failure",
        items_per_profile=1,
        rounds=1,
        process_limits=ProcessLimits(timeout_seconds=2),
    )

    reason = result.campaign.rounds[0].invalid_reason or ""
    assert "APIResearcherError: API researcher response is not valid JSON" in reason
    assert result.process_failures[0].diagnostic == (
        "APIResearcherError: API researcher response is not valid JSON"
    )
    stored = json.loads((output / "pilot_summary.json").read_text(encoding="utf-8"))
    assert stored["process_failures"][0]["diagnostic"].startswith("APIResearcherError")


def test_researcher_timeout_consumes_slot_without_reader_call(tmp_path: Path) -> None:
    seed = "researcher-timeout"
    reader = GoldEvidenceReader(seed=seed, items_per_profile=1)

    result = run_autonomous_dynamic_pilot(
        initial_policy_directory=_seed_policy(tmp_path),
        output_directory=tmp_path / "researcher-timeout-result",
        reader=reader,
        researcher_executable=str(_sleeping_codex(tmp_path)),
        dataset_seed=seed,
        items_per_profile=1,
        rounds=1,
        process_limits=ProcessLimits(timeout_seconds=0.05),
    )

    assert result.campaign.rounds[0].valid is False
    assert "timed out" in (result.campaign.rounds[0].invalid_reason or "")
    assert result.process_failures[0].error_type == "ResearcherProcessError"
    assert result.reader_calls == 2
    assert reader.calls == 2


def test_failed_researcher_cannot_change_its_locked_executable(tmp_path: Path) -> None:
    seed = "failed-researcher-mutation"
    output = tmp_path / "failed-researcher-mutation-result"
    reader = GoldEvidenceReader(seed=seed, items_per_profile=1)

    with pytest.raises(RuntimeError, match="locked run inputs changed"):
        run_autonomous_dynamic_pilot(
            initial_policy_directory=_seed_policy(tmp_path),
            output_directory=output,
            reader=reader,
            researcher_executable=str(_failing_codex(tmp_path, mutate_executable=True)),
            dataset_seed=seed,
            items_per_profile=1,
            rounds=1,
            process_limits=ProcessLimits(timeout_seconds=2),
        )

    failure = json.loads((output / "failure.json").read_text(encoding="utf-8"))
    assert failure["locked_run_inputs_unchanged"] is False
    assert reader.calls == 2


def test_prompt_budget_consumes_slot_without_researcher_or_reader_call(tmp_path: Path) -> None:
    seed = "prompt-budget"
    reader = GoldEvidenceReader(seed=seed, items_per_profile=1)

    result = run_autonomous_dynamic_pilot(
        initial_policy_directory=_seed_policy(tmp_path),
        output_directory=tmp_path / "prompt-budget-result",
        reader=reader,
        researcher_executable=str(_fake_codex(tmp_path)),
        dataset_seed=seed,
        items_per_profile=1,
        rounds=1,
        max_researcher_prompt_bytes=1,
        process_limits=ProcessLimits(timeout_seconds=2),
    )

    assert result.campaign.rounds[0].valid is False
    assert "frozen byte budget" in (result.campaign.rounds[0].invalid_reason or "")
    assert result.researcher_processes == ()
    assert result.reader_calls == 2
    assert reader.calls == 2


def test_run_contract_exists_before_first_reader_call(tmp_path: Path) -> None:
    seed = "contract-before-reader"
    output = tmp_path / "contract-before-reader-result"
    inner = GoldEvidenceReader(seed=seed, items_per_profile=1)

    class ContractAwareReader:
        def read(self, query: str, context: ContextPack) -> ReaderOutput:
            assert (output / "run_contract.json").is_file()
            return inner.read(query, context)

    run_autonomous_dynamic_pilot(
        initial_policy_directory=_seed_policy(tmp_path),
        output_directory=output,
        reader=ContractAwareReader(),
        researcher_executable=str(_fake_codex(tmp_path)),
        dataset_seed=seed,
        items_per_profile=1,
        rounds=1,
        process_limits=ProcessLimits(timeout_seconds=2),
    )


def test_locked_qualification_rejects_unattested_reader(tmp_path: Path) -> None:
    seed = "unattested-reader"
    reader = GoldEvidenceReader(seed=seed, items_per_profile=1)

    with pytest.raises(ValueError, match="attested reader identity"):
        run_autonomous_dynamic_pilot(
            initial_policy_directory=_seed_policy(tmp_path),
            output_directory=tmp_path / "unattested-reader-result",
            reader=reader,
            researcher_executable=str(_fake_codex(tmp_path)),
            dataset_seed=seed,
            items_per_profile=1,
            rounds=1,
            token_axis_identity={"attested": True, "label": "unit-token-axis"},
            require_attested_identities=True,
            process_limits=ProcessLimits(timeout_seconds=2),
        )

    assert reader.calls == 0


@pytest.mark.parametrize(
    "token_axis_identity",
    [None, {"attested": False}, {"attested": "yes"}],
)
def test_locked_qualification_rejects_unattested_token_axis(
    tmp_path: Path,
    token_axis_identity: dict[str, object] | None,
) -> None:
    seed = "unattested-token-axis"
    reader = GoldEvidenceReader(seed=seed, items_per_profile=1)

    with pytest.raises(ValueError, match="attested token axis"):
        run_autonomous_dynamic_pilot(
            initial_policy_directory=_seed_policy(tmp_path),
            output_directory=tmp_path / "unattested-token-axis-result",
            reader=reader,
            researcher_executable=str(_fake_codex(tmp_path)),
            dataset_seed=seed,
            items_per_profile=1,
            rounds=1,
            token_axis_identity=token_axis_identity,
            require_attested_identities=True,
            process_limits=ProcessLimits(timeout_seconds=2),
        )

    assert reader.calls == 0


@pytest.mark.parametrize("mismatch", ["model", "transport"])
def test_locked_qualification_rejects_reader_runtime_mismatch(
    tmp_path: Path,
    mismatch: str,
) -> None:
    def retrying_transport(request: urllib.request.Request, timeout: float) -> bytes:
        del request, timeout
        raise AssertionError("transport must not run during attestation")

    if mismatch == "transport":
        reader = OpenAICompatibleReader(
            endpoint="http://127.0.0.1:8000/v1/chat/completions",
            model="actual-reader",
            max_tokens=64,
            max_model_len=131_072,
            chat_template_enable_thinking=False,
            transport=retrying_transport,
        )
    else:
        reader = OpenAICompatibleReader(
            endpoint="http://127.0.0.1:8000/v1/chat/completions",
            model="actual-reader",
            max_tokens=64,
            max_model_len=131_072,
            chat_template_enable_thinking=False,
        )
    declared_model = "wrong-reader" if mismatch == "model" else "actual-reader"

    with pytest.raises(ValueError, match="attested reader identity"):
        run_autonomous_dynamic_pilot(
            initial_policy_directory=_seed_policy(tmp_path),
            output_directory=tmp_path / f"reader-{mismatch}-result",
            reader=reader,
            reader_identity=_declared_reader_identity(declared_model),
            researcher_executable=str(_fake_codex(tmp_path)),
            dataset_seed=f"reader-{mismatch}",
            items_per_profile=1,
            rounds=1,
            token_axis_identity={"attested": True, "label": "unit-token-axis"},
            require_attested_identities=True,
            process_limits=ProcessLimits(timeout_seconds=2),
        )


def test_h0_partial_reader_failure_records_every_attempt(tmp_path: Path) -> None:
    output = tmp_path / "h0-reader-failure"

    class FailingReader:
        def __init__(self) -> None:
            self.calls = 0

        def read(self, query: str, context: ContextPack) -> ReaderOutput:
            del query
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("reader endpoint failed")
            return ReaderOutput("", context.token_count, 0)

    reader = FailingReader()
    with pytest.raises(RuntimeError, match="reader endpoint failed"):
        run_autonomous_dynamic_pilot(
            initial_policy_directory=_seed_policy(tmp_path),
            output_directory=output,
            reader=reader,
            researcher_executable=str(_fake_codex(tmp_path)),
            dataset_seed="h0-reader-failure",
            items_per_profile=1,
            rounds=1,
            process_limits=ProcessLimits(timeout_seconds=2),
        )

    failure = json.loads((output / "failure.json").read_text(encoding="utf-8"))
    assert reader.calls == 2
    assert failure["reader_calls_attempted"] == 2
    assert failure["cost_accounting_complete"] is False
    assert failure["reader_usage_accounting_complete"] is False
    assert failure["evaluation_observations"] == []
    assert failure["processes"] == []


def test_initial_policy_snapshot_is_stable_when_source_changes(tmp_path: Path) -> None:
    seed = "source-policy-mutation"
    source_policy = _seed_policy(tmp_path)
    inner = GoldEvidenceReader(seed=seed, items_per_profile=1)

    class SourceMutatingReader:
        def read(self, query: str, context: ContextPack) -> ReaderOutput:
            if inner.calls == 0:
                (source_policy / "seed.py").write_text("VALUE = 'mutated'\n", encoding="utf-8")
            return inner.read(query, context)

    output = tmp_path / "source-policy-mutation-result"
    result = run_autonomous_dynamic_pilot(
        initial_policy_directory=source_policy,
        output_directory=output,
        reader=SourceMutatingReader(),
        researcher_executable=str(_fake_codex(tmp_path)),
        dataset_seed=seed,
        items_per_profile=1,
        rounds=1,
        process_limits=ProcessLimits(timeout_seconds=2),
    )

    snapshot_source = (output / "initial-policy-snapshot" / "seed.py").read_text(encoding="utf-8")
    assert snapshot_source.startswith("from rsicontext.policy")
    assert (source_policy / "seed.py").read_text(encoding="utf-8") == "VALUE = 'mutated'\n"
    assert result.run_contract.initial_policy_sha256


def test_researcher_cannot_mutate_locked_contract(tmp_path: Path) -> None:
    seed = "contract-mutation"
    output = tmp_path / "contract-mutation-result"
    reader = GoldEvidenceReader(seed=seed, items_per_profile=1)

    with pytest.raises(RuntimeError, match="locked run inputs changed"):
        run_autonomous_dynamic_pilot(
            initial_policy_directory=_seed_policy(tmp_path),
            output_directory=output,
            reader=reader,
            researcher_executable=str(_fake_codex(tmp_path, mutate_contract=True)),
            dataset_seed=seed,
            items_per_profile=1,
            rounds=1,
            process_limits=ProcessLimits(timeout_seconds=2),
        )

    failure = json.loads((output / "failure.json").read_text(encoding="utf-8"))
    assert failure["locked_run_inputs_unchanged"] is False
    assert failure["reader_calls_attempted"] == 2
    assert reader.calls == 2


def test_runtime_invalid_policy_consumes_slot_without_reader_call(tmp_path: Path) -> None:
    seed = "runtime-invalid"
    reader = GoldEvidenceReader(seed=seed, items_per_profile=1)

    result = run_autonomous_dynamic_pilot(
        initial_policy_directory=_seed_policy(tmp_path),
        output_directory=tmp_path / "runtime-invalid-result",
        reader=reader,
        researcher_executable=str(
            _fake_codex(
                tmp_path,
                policy_source="class Policy:\n    def assemble(self, artifact, query, budget):\n"
                "        return ''\n",
            )
        ),
        dataset_seed=seed,
        items_per_profile=1,
        rounds=1,
        process_limits=ProcessLimits(timeout_seconds=2),
    )

    assert result.campaign.rounds[0].valid is False
    assert "ContextPack" in (result.campaign.rounds[0].invalid_reason or "")
    assert reader.calls == 2
    assert result.reader_calls == 2


def test_short_visible_answers_are_not_treated_as_hardcoded_lookups(tmp_path: Path) -> None:
    item = EvaluationItem(
        item_id="public-poet",
        query="What is Tadhg Dall's occupation?",
        answer="poet",
        artifact=Artifact(
            "doc",
            (DocumentChunk("ck-0000-0000", "doc", 0, 12, "Tadhg Dall was an Irish poet.", 6),),
        ),
        gold_chunk_ids=frozenset({"ck-0000-0000"}),
    )
    fingerprint = public_visible_items_fingerprint(
        cell_id="helmet-rag-popqa-k1000-to-8k",
        items=(item,),
        pack_budget_tokens=8192,
        scorer_name="extractive_span_match",
        token_axis_id="unit-token-axis",
    )
    result = run_autonomous_dynamic_pilot(
        initial_policy_directory=_seed_policy(tmp_path),
        output_directory=tmp_path / "short-answer",
        reader=_PhraseReader(),
        researcher_executable=str(
            _fake_codex(
                tmp_path,
                policy_source=(
                    "from rsicontext.policy import LexicalPolicy\n\n"
                    "class Policy(LexicalPolicy):\n"
                    "    def assemble(self, artifact, query, budget):\n"
                    "        ignored = {'poet', 'singer'}\n"
                    "        return super().assemble(artifact, query, budget)\n"
                ),
            )
        ),
        visible_items=(item,),
        dataset_fingerprint=fingerprint,
        scorer=extractive_span_match,
        rounds=1,
        process_limits=ProcessLimits(timeout_seconds=2),
    )
    assert result.qualification_only is True
    assert (tmp_path / "short-answer" / "pilot_summary.json").is_file()


def _public_item() -> EvaluationItem:
    chunk = DocumentChunk(
        "ck-0000-0000",
        "doc",
        0,
        24,
        "Ottawa is the capital of Canada.",
        8,
    )
    return EvaluationItem(
        item_id="public-0",
        query="What is the capital of Canada?",
        answer="Ottawa",
        artifact=Artifact("doc", (chunk,)),
        gold_chunk_ids=frozenset({"ck-0000-0000"}),
    )


class _PhraseReader:
    def __init__(self) -> None:
        self.calls = 0

    def read(self, query: str, context: ContextPack) -> ReaderOutput:
        del query
        self.calls += 1
        return ReaderOutput("The capital is Ottawa.", context.token_count + 3, 5)


def test_public_visible_fingerprint_binds_cell_query_and_chunk_bytes() -> None:
    item = _public_item()
    fingerprint = public_visible_items_fingerprint(
        cell_id="helmet-rag-hotpot-k1000-to-8k",
        items=(item,),
        pack_budget_tokens=8192,
        scorer_name="extractive_span_match",
        token_axis_id="unit-token-axis",
    )
    mutated = EvaluationItem(
        item_id=item.item_id,
        query=item.query,
        answer=item.answer,
        artifact=Artifact(
            "doc",
            (
                DocumentChunk(
                    "ck-0000-0000",
                    "doc",
                    0,
                    24,
                    "Toronto is the capital of Canada.",
                    8,
                ),
            ),
        ),
        gold_chunk_ids=item.gold_chunk_ids,
    )
    assert fingerprint != public_visible_items_fingerprint(
        cell_id="helmet-rag-hotpot-k1000-to-8k",
        items=(mutated,),
        pack_budget_tokens=8192,
        scorer_name="extractive_span_match",
        token_axis_id="unit-token-axis",
    )


def test_public_items_pilot_uses_extractive_span_match(tmp_path: Path) -> None:
    item = _public_item()
    reader = _PhraseReader()
    fingerprint = public_visible_items_fingerprint(
        cell_id="helmet-rag-hotpot-k1000-to-8k",
        items=(item,),
        pack_budget_tokens=8192,
        scorer_name="extractive_span_match",
        token_axis_id="unit-token-axis",
    )
    result = run_autonomous_dynamic_pilot(
        initial_policy_directory=_seed_policy(tmp_path),
        output_directory=tmp_path / "public-result",
        reader=reader,
        researcher_kind="codex",
        researcher_executable=str(_fake_codex(tmp_path)),
        visible_items=(item,),
        dataset_fingerprint=fingerprint,
        scorer=extractive_span_match,
        rounds=1,
        process_limits=ProcessLimits(timeout_seconds=2),
    )
    assert result.dataset_fingerprint == fingerprint
    assert result.items_per_profile == 1
    assert result.baseline_score == 1.0
    assert result.qualification_only is True
    assert result.formal_sealed_isolation is False
    assert reader.calls == 2


def test_public_items_require_fingerprint(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="dataset_fingerprint"):
        run_autonomous_dynamic_pilot(
            initial_policy_directory=_seed_policy(tmp_path),
            output_directory=tmp_path / "missing-fingerprint",
            reader=_PhraseReader(),
            researcher_executable=str(_fake_codex(tmp_path)),
            visible_items=(_public_item(),),
            rounds=1,
            process_limits=ProcessLimits(timeout_seconds=2),
        )
