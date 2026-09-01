from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from rsicontext.artifacts import (
    CostEstimate,
    EvidenceClaim,
    FlipProbabilities,
    Manifest,
    MechanismClaim,
    PromotionRecommendation,
    QuestionPrediction,
    write_manifest_atomic,
)
from rsicontext.campaign.researcher import (
    CampaignConfig,
    ResearchRoundRequest,
    RoundEvaluation,
    run_researcher_campaign,
)
from rsicontext.eval import (
    AuditedPolicyBundle,
    EvaluationItem,
    FreshProcessPolicyFactory,
    ToyFrozenReader,
    evaluate,
    exact_match,
)
from rsicontext.experiment.rsi_run import policy_tree_sha256
from rsicontext.open_s import (
    OPEN_S_TRACK_ID,
    OpenSSeedError,
    materialize_isolated_seed,
    open_s_researcher_prompt,
    reader_window_pack_budget,
    reject_unchanged_open_s_tree,
    repository_open_s_seed,
    resolve_pack_budget_tokens,
    seed_tree_digest,
    validate_open_s_seed,
)
from rsicontext.policy import Artifact, Budget, DocumentChunk
from rsicontext.policy.open_s import (
    map_shards,
    merge_ranked,
    pack_spans,
    record_working_set,
    retrieve_by_query,
    route_skill,
)
from rsicontext.security import PolicyAuditor, PolicySecurityError, local_module_names

ROOT = Path(__file__).parents[1]
SEED = ROOT / "seeds" / "open_s_v1"
SCRIPT_PATH = ROOT / "scripts" / "open_s_hy3_h0.py"


def _artifact() -> Artifact:
    texts = (
        ("head", "irrelevant opening prose"),
        ("gold", "mars has two moons\nANSWER: two"),
        ("tail", "irrelevant closing prose"),
    )
    return Artifact(
        document_id="doc",
        chunks=tuple(
            DocumentChunk(
                chunk_id=chunk_id,
                document_id="doc",
                start=index * 40,
                end=index * 40 + len(text),
                text=text,
                token_count=len(text.split()),
            )
            for index, (chunk_id, text) in enumerate(texts)
        ),
    )


def _item() -> EvaluationItem:
    return EvaluationItem(
        item_id="visible-open-s",
        query="How many moons does Mars have?",
        answer="two",
        artifact=_artifact(),
        gold_chunk_ids=frozenset({"gold"}),
    )


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("open_s_hy3_h0_script_test", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load open-S hy3 H0 script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_policy_surface_is_unchanged() -> None:
    report = PolicyAuditor().audit_tree(ROOT / "policy")
    assert report.safe
    assert report.files == ("seed.py",)


def test_canonical_seed_is_byte_identical_and_audited() -> None:
    validate_open_s_seed(SEED, exact_layout=True)
    assert (SEED / "seed.py").read_bytes() == (SEED / "policy.py").read_bytes()
    report = PolicyAuditor().audit_tree(SEED)
    assert report.safe
    assert set(report.files) == {
        "memory.py",
        "policy.py",
        "retrieval.py",
        "seed.py",
        "skills.py",
        "task.py",
    }
    assert repository_open_s_seed() == SEED.resolve()
    assert seed_tree_digest(SEED) == policy_tree_sha256(SEED)


def test_isolated_copies_start_from_the_same_digest(tmp_path: Path) -> None:
    first = materialize_isolated_seed(SEED, tmp_path / "traj-a")
    second = materialize_isolated_seed(SEED, tmp_path / "traj-b")
    assert first == second == seed_tree_digest(SEED)
    mutated = tmp_path / "traj-a" / "policy" / "policy.py"
    mutated.write_text(mutated.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")
    assert seed_tree_digest(tmp_path / "traj-b" / "policy") == first
    assert seed_tree_digest(SEED) == first


def test_seed_rejects_non_python_and_existing_destination(tmp_path: Path) -> None:
    dirty = tmp_path / "dirty-seed"
    dirty.mkdir()
    (dirty / "policy.py").write_text("VALUE = 1\n", encoding="utf-8")
    (dirty / "NOTES.md").write_text("not python\n", encoding="utf-8")
    with pytest.raises(OpenSSeedError, match="only Python"):
        validate_open_s_seed(dirty)
    destination = tmp_path / "already"
    destination.mkdir()
    with pytest.raises(OpenSSeedError, match="must not exist"):
        materialize_isolated_seed(SEED, destination)


def test_local_module_names_follow_the_policy_tree() -> None:
    names = local_module_names(("policy.py", "memory.py", "skills/router.py", "pkg/__init__.py"))
    assert names == frozenset({"policy", "memory", "skills", "skills.router", "pkg"})


def test_tree_audit_allows_sibling_modules_and_policy_submodules(tmp_path: Path) -> None:
    root = tmp_path / "policy"
    root.mkdir()
    (root / "retrieval.py").write_text("def rank():\n    return ()\n", encoding="utf-8")
    (root / "policy.py").write_text(
        "from collections.abc import Iterable\n"
        "from retrieval import rank\n"
        "from rsicontext.policy.open_s import pack_spans\n"
        "from rsicontext.policy import ContextPack\n"
        "def assemble(chunks: Iterable[object]) -> object:\n"
        "    return rank() or pack_spans or ContextPack\n",
        encoding="utf-8",
    )
    report = PolicyAuditor().audit_tree(root)
    assert report.safe


def test_sibling_import_without_the_module_file_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "policy"
    root.mkdir()
    (root / "policy.py").write_text("from retrieval import rank\n", encoding="utf-8")
    with pytest.raises(PolicySecurityError, match="IMPORT_NOT_ALLOWED"):
        PolicyAuditor().audit_tree(root).require_safe()
    assert "IMPORT_NOT_ALLOWED" in {
        violation.code
        for violation in PolicyAuditor().audit_source("from retrieval import rank\n").violations
    }


def test_tree_audit_rejects_forbidden_local_module_shadows(tmp_path: Path) -> None:
    root = tmp_path / "policy"
    root.mkdir()
    (root / "os.py").write_text("VALUE = 1\n", encoding="utf-8")
    report = PolicyAuditor().audit_tree(root)
    assert "LOCAL_MODULE_FORBIDDEN" in {violation.code for violation in report.violations}


def test_open_s_operators_are_deterministic_and_budget_safe() -> None:
    artifact = _artifact()
    ranked = retrieve_by_query(artifact.chunks, "How many moons does Mars have?")
    assert ranked[0].chunk_id == "gold"
    shards = map_shards(artifact.chunks, shard_count=2)
    assert shards == ((artifact.chunks[0], artifact.chunks[2]), (artifact.chunks[1],))
    merged = merge_ranked(shards)
    assert tuple(chunk.chunk_id for chunk in merged) == ("head", "gold", "tail")
    pack = pack_spans(ranked, artifact, Budget(max_tokens=6))
    assert pack.token_count <= 6
    assert "gold" in pack.ordering
    assert route_skill("") == "head"
    assert route_skill("Who wrote it?") == "retrieve"
    assert record_working_set("q", ranked)[0] == "q"


def test_seed_h0_packs_source_order_when_the_window_fits() -> None:
    bundle = AuditedPolicyBundle.from_directory(SEED, entrypoint="seed.py")
    factory = FreshProcessPolicyFactory(bundle, timeout_seconds=5.0)
    result = evaluate(
        factory,
        (_item(),),
        ToyFrozenReader(),
        Budget(max_tokens=20),
        exact_match,
    )
    assert result.score == 1.0
    assert result.predictions == ("two",)


def test_seed_h0_keeps_prefix_under_a_tight_budget() -> None:
    bundle = AuditedPolicyBundle.from_directory(SEED, entrypoint="seed.py")
    factory = FreshProcessPolicyFactory(bundle, timeout_seconds=5.0)
    result = evaluate(
        factory,
        (_item(),),
        ToyFrozenReader(),
        Budget(max_tokens=3),
        exact_match,
    )
    assert result.score == 0.0


def test_isolated_seed_survives_campaign_snapshot_and_fresh_eval(tmp_path: Path) -> None:
    workspace_root = tmp_path / "campaign-seed"
    materialize_isolated_seed(SEED, workspace_root)
    seed_policy = workspace_root / "policy"
    item = _item()

    def researcher(request: ResearchRoundRequest) -> None:
        write_manifest_atomic(
            request.manifest_path,
            Manifest(
                candidate_name="open-s-h0-copy",
                parent_artifact_id=request.parent_artifact_id,
                predictions=(
                    QuestionPrediction(
                        item_id=item.item_id,
                        probabilities=FlipProbabilities(0.6, 0.3, 0.1),
                        mechanism_ids=("mechanism-0",),
                        evidence_ids=("evidence-0",),
                    ),
                ),
                mechanisms=(
                    MechanismClaim(
                        mechanism_id="mechanism-0",
                        description="Keep the isolated open-S seed composition.",
                        policy_paths=("policy/policy.py",),
                    ),
                ),
                evidence=(
                    EvidenceClaim(
                        evidence_id="evidence-0",
                        kind="visible-trace",
                        reference="round-0",
                        claim="H0 should remain scorable after isolation.",
                    ),
                ),
                cost=CostEstimate(8, 1, 0, 0, 0.0, 1.0),
                promotion=PromotionRecommendation(
                    decision="hold",
                    expected_score_delta=0.0,
                    max_regression_probability=0.1,
                    rationale="Identity copy of the byte-identical seed.",
                ),
            ),
        )

    def evaluator(policy_directory: Path, *, round_index: int) -> RoundEvaluation:
        del round_index
        bundle = AuditedPolicyBundle.from_directory(policy_directory, entrypoint="policy.py")
        result = evaluate(
            FreshProcessPolicyFactory(bundle, timeout_seconds=5.0),
            (item,),
            ToyFrozenReader(),
            Budget(max_tokens=20),
            exact_match,
        )
        return RoundEvaluation(
            score=result.score,
            item_scores=((item.item_id, result.item_scores[0]),),
            reader_input_tokens=result.reader_input_tokens[0],
            reader_output_tokens=result.reader_output_tokens[0],
            wall_seconds=0.1,
        )

    campaign = run_researcher_campaign(
        initial_policy_directory=seed_policy,
        output_directory=tmp_path / "campaign-out",
        researcher=researcher,
        evaluator=evaluator,
        config=CampaignConfig(prediction_item_ids=(item.item_id,), rounds=1),
    )
    assert campaign.rounds[0].valid is True
    assert campaign.rounds[0].score == 1.0


def test_open_s_prompt_keeps_the_frozen_boundary() -> None:
    prompt = open_s_researcher_prompt()
    assert OPEN_S_TRACK_ID in prompt
    assert "byte-identical seed" in prompt
    assert "one target-model call" in prompt
    assert "Do not call the reader" in prompt
    assert "Do not use the network" in prompt
    assert "PolicySpecV1" in prompt
    assert "separate leaderboard" in prompt
    assert "policy/task.py" in prompt
    assert "full-as-fits" in prompt
    assert "not an 8K cap" in prompt
    assert "Identical parent copies are invalid" in prompt
    assert "Operate autonomously" in prompt
    assert "no prescribed method catalog" in prompt
    assert "complete freedom" in prompt
    assert "Search MODE" not in prompt
    assert "do not spend the next round only retuning" not in prompt
    assert "Prefer composing" not in prompt


def test_reader_window_pack_budget_fills_the_frozen_window() -> None:
    assert reader_window_pack_budget(max_model_len=131072, max_output_tokens=64) == 114624
    assert (
        resolve_pack_budget_tokens(
            pack_tokens=None,
            policy_track="open-s",
            max_model_len=131072,
            max_output_tokens=64,
        )
        == 114624
    )
    assert (
        resolve_pack_budget_tokens(
            pack_tokens=None,
            policy_track="restricted",
            max_model_len=131072,
            max_output_tokens=64,
        )
        == 8192
    )


def test_unchanged_open_s_tree_is_rejected(tmp_path: Path) -> None:
    policy = tmp_path / "policy"
    policy.mkdir()
    (policy / "policy.py").write_text("class Policy:\n    pass\n", encoding="utf-8")
    parent = policy_tree_sha256(policy)
    with pytest.raises(ValueError, match="identical parent copies are invalid"):
        reject_unchanged_open_s_tree(parent, policy)
    (policy / "retrieval.py").write_text("RANKED = True\n", encoding="utf-8")
    reject_unchanged_open_s_tree(parent, policy)


def test_open_s_campaign_prompt_prefixes_the_harness_contract(tmp_path: Path) -> None:
    from rsicontext.campaign.autonomous_dynamic import (
        VisibleItemFeedback,
        _build_research_prompt,
    )

    policy_directory = tmp_path / "policy"
    policy_directory.mkdir()
    (policy_directory / "policy.py").write_text("class Policy:\n    pass\n", encoding="utf-8")
    (policy_directory / "task.py").write_text('TASK = "evolve S"\n', encoding="utf-8")
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
    prompt = _build_research_prompt(
        request,
        feedback,
        None,
        artifact_delivery="workspace",
        policy_track="open-s",
        candidate_slots=5,
    )
    assert OPEN_S_TRACK_ID in prompt
    assert "pack envelope" in prompt
    assert "sibling .py modules" in prompt
    assert "8192-token budget" not in prompt
    assert "Operate autonomously" in prompt
    assert "Candidate slots: 1 of 5 (remaining after this turn: 4)" in prompt
    assert "do not ask for a strategy" in prompt
    api_prompt = _build_research_prompt(
        request,
        feedback,
        None,
        artifact_delivery="api-json",
        policy_track="open-s",
        candidate_slots=5,
    )
    assert "must change" in api_prompt
    assert "Choose any composition" in api_prompt
    assert "retrieve_by_query(chunks, query)" in api_prompt
    assert "Do not default to LexicalPolicy" not in api_prompt
    assert "LexicalPolicy implementations from rsicontext.policy" not in api_prompt
    assert "Prefer composing" not in api_prompt


def test_hy3_h0_script_skips_without_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _load_script()
    monkeypatch.delenv("COPILOT_API_KEY", raising=False)
    monkeypatch.delenv("COPILOT_BASE_URL", raising=False)
    output = tmp_path / "hy3-skip"
    assert script.main(["--output", str(output)]) == 0
    summary = (output / "summary.json").read_text(encoding="utf-8")
    assert "credentials_missing" in summary
    assert "qualification_only" in summary
    assert "rsi_launch_eligible" in summary
