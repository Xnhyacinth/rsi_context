from __future__ import annotations

from pathlib import Path

import pytest

import rsicontext.campaign.researcher as researcher_campaign
from rsicontext.analysis.process import process_from_campaign_directory
from rsicontext.artifacts import (
    ArtifactStore,
    CostEstimate,
    EvidenceClaim,
    FlipProbabilities,
    Manifest,
    ManifestError,
    MechanismClaim,
    PromotionRecommendation,
    QuestionPrediction,
    write_manifest_atomic,
)
from rsicontext.campaign.researcher import (
    CampaignConfig,
    CampaignError,
    ResearcherTurnError,
    ResearchRoundRequest,
    RoundEvaluation,
    run_researcher_campaign,
)
from rsicontext.eval import EvaluationItem, PolicyFactory, ToyFrozenReader, evaluate
from rsicontext.policy import Artifact, Budget, DocumentChunk, LexicalPolicy, TruncationPolicy
from rsicontext.security import AuditReport, PolicyAuditor, PolicySecurityError


def _seed_policy(tmp_path: Path, name: str = "seed-policy") -> Path:
    policy = tmp_path / name
    policy.mkdir()
    (policy / "policy.py").write_text('MODE = "seed"\n', encoding="utf-8")
    return policy


def _manifest(request: ResearchRoundRequest, *, item_ids: tuple[str, ...] | None = None) -> None:
    mechanism_id = f"mechanism-{request.round_index}"
    evidence_id = f"evidence-{request.round_index}"
    predictions = tuple(
        QuestionPrediction(
            item_id=item_id,
            probabilities=FlipProbabilities(0.5, 0.4, 0.1),
            mechanism_ids=(mechanism_id,),
            evidence_ids=(evidence_id,),
        )
        for item_id in (item_ids or request.prediction_item_ids)
    )
    manifest = Manifest(
        candidate_name=f"candidate-{request.round_index}",
        parent_artifact_id=request.parent_artifact_id,
        predictions=predictions,
        mechanisms=(
            MechanismClaim(
                mechanism_id=mechanism_id,
                description="Change the deterministic selection mode.",
                policy_paths=("policy/policy.py",),
            ),
        ),
        evidence=(
            EvidenceClaim(
                evidence_id=evidence_id,
                kind="visible-trace",
                reference=f"round-{request.round_index}",
                claim="The visible failure identifies a selection error.",
            ),
        ),
        cost=CostEstimate(10, 5, 0, 0, 0.0, 1.0),
        promotion=PromotionRecommendation(
            decision="reject",
            expected_score_delta=0.0,
            max_regression_probability=0.1,
            rationale="Deliberately wrong advice proves evaluator authority.",
        ),
    )
    write_manifest_atomic(request.manifest_path, manifest)


def _item() -> EvaluationItem:
    chunks = (
        DocumentChunk("head", "doc", 0, 10, "irrelevant head", 2),
        DocumentChunk("gold", "doc", 11, 50, "target fact\nANSWER: amber", 4),
        DocumentChunk("tail", "doc", 51, 65, "irrelevant tail", 2),
    )
    return EvaluationItem(
        item_id="visible-1",
        query="What is the target fact?",
        answer="amber",
        artifact=Artifact("doc", chunks),
        gold_chunk_ids=frozenset({"gold"}),
    )


class FakeResearcher:
    """Scripted callback for harness qualification, not autonomous discovery."""

    modes = ("head", "lexical", "tail", "lexical", "head")

    def __init__(self) -> None:
        self.starting_modes: list[str] = []

    def __call__(self, request: ResearchRoundRequest) -> None:
        assert {path.name for path in request.workspace.iterdir()} == {"policy"}
        source_path = request.policy_directory / "policy.py"
        self.starting_modes.append(source_path.read_text(encoding="utf-8").split('"')[1])
        source_path.write_text(f'MODE = "{self.modes[request.round_index]}"\n', encoding="utf-8")
        _manifest(request)


class ToyIsolatedEvaluator:
    """Uses audited source as configuration; it never imports candidate code."""

    def __call__(self, policy_directory: Path, *, round_index: int) -> RoundEvaluation:
        del round_index
        assert policy_directory.parent.parent.name == "evaluation-workspaces"
        source = (policy_directory / "policy.py").read_text(encoding="utf-8")
        factory: PolicyFactory
        if 'MODE = "lexical"' in source:
            factory = LexicalPolicy
        elif 'MODE = "tail"' in source:
            factory = _tail_policy
        else:
            factory = _head_policy
        result = evaluate(factory, [_item()], ToyFrozenReader(), Budget(4, max_chunks=1))
        return RoundEvaluation(
            score=result.score,
            item_scores=(("visible-1", result.item_scores[0]),),
            reader_input_tokens=sum(result.reader_input_tokens),
            reader_output_tokens=sum(result.reader_output_tokens),
            wall_seconds=0.25,
        )


def _head_policy() -> TruncationPolicy:
    return TruncationPolicy("head")


def _tail_policy() -> TruncationPolicy:
    return TruncationPolicy("tail")


def test_five_round_callback_campaign_records_clean_audited_lineage(tmp_path: Path) -> None:
    researcher = FakeResearcher()
    output = tmp_path / "campaign"

    result = run_researcher_campaign(
        initial_policy_directory=_seed_policy(tmp_path),
        output_directory=output,
        researcher=researcher,
        evaluator=ToyIsolatedEvaluator(),
        config=CampaignConfig(rounds=5, prediction_item_ids=("visible-1",)),
    )

    assert [round_.score for round_ in result.rounds] == [0.0, 1.0, 0.0, 1.0, 0.0]
    assert [round_.promoted for round_ in result.rounds] == [True, True, False, False, False]
    assert result.selected_round == 1
    assert result.callback_only is True
    assert result.formal_process_isolation is False
    assert researcher.starting_modes == ["seed", "head", "lexical", "tail", "lexical"]

    store = ArtifactStore(output / "store")
    lineage = store.lineage(result.rounds[-1].candidate_artifact_id)
    assert [record.artifact_id for record in lineage] == [
        result.seed_artifact_id,
        *(round_.candidate_artifact_id for round_ in result.rounds),
    ]
    for round_ in result.rounds:
        assert store.get_record(round_.manifest_artifact_id).kind == "research-manifest"
        assert store.get_record(round_.evaluation_artifact_id).kind == "evaluation"
        promotion_record = store.get_record(round_.promotion_artifact_id)
        assert promotion_record.kind == "promotion"
        assert promotion_record.parents == (
            round_.candidate_artifact_id,
            round_.manifest_artifact_id,
            round_.evaluation_artifact_id,
        )
        assert round_.researcher_recommendation == "reject"
    assert (output / "summary.json").is_file()


def test_seed_evaluation_is_the_initial_historical_best(tmp_path: Path) -> None:
    researcher = FakeResearcher()
    seed_evaluation = RoundEvaluation(0.5, (("visible-1", 0.5),), 7, 1, 0.1)

    result = run_researcher_campaign(
        initial_policy_directory=_seed_policy(tmp_path),
        initial_evaluation=seed_evaluation,
        output_directory=tmp_path / "campaign",
        researcher=researcher,
        evaluator=ToyIsolatedEvaluator(),
        config=CampaignConfig(rounds=1, prediction_item_ids=("visible-1",)),
    )

    assert result.rounds[0].score == 0.0
    assert result.rounds[0].promoted is False
    assert result.rounds[0].incumbent_artifact_id == result.seed_artifact_id
    assert result.selected_round is None
    assert result.seed_evaluation_artifact_id is not None
    assert result.process is not None
    assert result.process.scores == (0.5, 0.0)
    assert result.process.selected_score == pytest.approx(0.5)
    assert result.process.post_peak_regression is True
    assert process_from_campaign_directory(tmp_path / "campaign") == result.process


def test_invalid_audit_consumes_a_round_without_reader_or_promotion(
    tmp_path: Path,
) -> None:
    reasons: list[str | None] = []

    def researcher(request: ResearchRoundRequest) -> None:
        reasons.append(request.last_invalid_reason)
        source_path = request.policy_directory / "policy.py"
        if request.round_index == 1:
            source_path.write_text("result = compile('1', '<policy>', 'eval')\n", encoding="utf-8")
        else:
            source_path.write_text('MODE = "lexical"\n', encoding="utf-8")
        _manifest(request)

    calls = 0

    def evaluator(policy_directory: Path, *, round_index: int) -> RoundEvaluation:
        nonlocal calls
        calls += 1
        del policy_directory
        return RoundEvaluation(
            1.0,
            (("visible-1", 1.0),),
            4,
            1,
            0.1,
        )

    result = run_researcher_campaign(
        initial_policy_directory=_seed_policy(tmp_path),
        initial_evaluation=RoundEvaluation(0.5, (("visible-1", 0.5),), 7, 1, 0.1),
        output_directory=tmp_path / "campaign",
        researcher=researcher,
        evaluator=evaluator,
        config=CampaignConfig(rounds=3, prediction_item_ids=("visible-1",)),
    )

    assert calls == 2
    assert [round_.valid for round_ in result.rounds] == [True, False, True]
    assert result.rounds[1].promoted is False
    assert result.rounds[1].invalid_reason is not None
    assert "compile" in result.rounds[1].invalid_reason
    assert result.rounds[2].parent_artifact_id == result.rounds[0].candidate_artifact_id
    assert result.selected_round == 0
    assert result.process is not None
    assert result.process.scores == (0.5, 1.0, 1.0)
    assert reasons[2] is not None and "compile" in reasons[2]
    store = ArtifactStore(tmp_path / "campaign" / "store")
    assert store.get_record(result.rounds[1].candidate_artifact_id).kind == "rejected-policy"
    assert store.get_record(result.rounds[1].evaluation_artifact_id).kind == "invalid-submission"
    assert process_from_campaign_directory(tmp_path / "campaign") == result.process


def test_researcher_process_abort_consumes_slot_without_manifest(tmp_path: Path) -> None:
    calls = 0

    def researcher(request: ResearchRoundRequest) -> None:
        if request.round_index == 1:
            raise ResearcherTurnError("researcher process exited with status 1")
        source_path = request.policy_directory / "policy.py"
        source_path.write_text('MODE = "lexical"\n', encoding="utf-8")
        _manifest(request)

    def evaluator(policy_directory: Path, *, round_index: int) -> RoundEvaluation:
        nonlocal calls
        calls += 1
        del policy_directory, round_index
        return RoundEvaluation(1.0, (("visible-1", 1.0),), 4, 1, 0.1)

    result = run_researcher_campaign(
        initial_policy_directory=_seed_policy(tmp_path),
        initial_evaluation=RoundEvaluation(0.5, (("visible-1", 0.5),), 7, 1, 0.1),
        output_directory=tmp_path / "campaign",
        researcher=researcher,
        evaluator=evaluator,
        config=CampaignConfig(rounds=3, prediction_item_ids=("visible-1",)),
    )

    assert calls == 2
    assert [round_.valid for round_ in result.rounds] == [True, False, True]
    assert result.rounds[1].candidate_name == "missing-submission-r1"
    assert result.rounds[1].invalid_reason == "researcher process exited with status 1"
    assert result.rounds[2].parent_artifact_id == result.rounds[0].candidate_artifact_id
    assert result.selected_round == 0
    assert result.process is not None
    assert result.process.scores == (0.5, 1.0, 1.0)
    store = ArtifactStore(tmp_path / "campaign" / "store")
    assert store.get_record(result.rounds[1].candidate_artifact_id).kind == "rejected-policy"
    assert store.get_record(result.rounds[1].evaluation_artifact_id).kind == "invalid-submission"
    assert process_from_campaign_directory(tmp_path / "campaign") == result.process


def test_re_compile_inside_functions_is_evaluated(tmp_path: Path) -> None:
    calls = 0

    def researcher(request: ResearchRoundRequest) -> None:
        (request.policy_directory / "policy.py").write_text(
            "import re\n"
            'MODE = "lexical"\n\n'
            "def tokens(query: str) -> list[str]:\n"
            "    pattern = re.compile(r'[A-Za-z]+')\n"
            "    return pattern.findall(query)\n",
            encoding="utf-8",
        )
        _manifest(request)

    def evaluator(policy_directory: Path, *, round_index: int) -> RoundEvaluation:
        nonlocal calls
        del policy_directory, round_index
        calls += 1
        return RoundEvaluation(1.0, (("visible-1", 1.0),), 4, 1, 0.1)

    result = run_researcher_campaign(
        initial_policy_directory=_seed_policy(tmp_path),
        initial_evaluation=RoundEvaluation(0.5, (("visible-1", 0.5),), 7, 1, 0.1),
        output_directory=tmp_path / "campaign",
        researcher=researcher,
        evaluator=evaluator,
        config=CampaignConfig(rounds=1, prediction_item_ids=("visible-1",)),
    )

    assert calls == 1
    assert result.rounds[0].valid is True
    assert result.rounds[0].score == 1.0
    assert result.selected_round == 0


def test_all_invalid_rounds_keep_h0_without_calling_the_reader(tmp_path: Path) -> None:
    calls = 0

    def researcher(request: ResearchRoundRequest) -> None:
        (request.policy_directory / "policy.py").write_text("import os\n", encoding="utf-8")
        _manifest(request)

    def evaluator(policy_directory: Path, *, round_index: int) -> RoundEvaluation:
        nonlocal calls
        del policy_directory, round_index
        calls += 1
        return RoundEvaluation(1.0, (("visible-1", 1.0),), 1, 1, 0.1)

    result = run_researcher_campaign(
        initial_policy_directory=_seed_policy(tmp_path),
        initial_evaluation=RoundEvaluation(0.5, (("visible-1", 0.5),), 7, 1, 0.1),
        output_directory=tmp_path / "campaign",
        researcher=researcher,
        evaluator=evaluator,
        config=CampaignConfig(rounds=2, prediction_item_ids=("visible-1",)),
    )

    assert calls == 0
    assert all(round_.valid is False for round_ in result.rounds)
    assert result.selected_round is None
    assert result.process is not None
    assert result.process.scores == (0.5,)
    assert process_from_campaign_directory(tmp_path / "campaign") == result.process


def test_campaign_rejects_researcher_workspace_pollution_before_evaluation(
    tmp_path: Path,
) -> None:
    evaluated = False

    def polluting_researcher(request: ResearchRoundRequest) -> None:
        (request.workspace / "notes.txt").write_text("stale", encoding="utf-8")
        _manifest(request)

    def evaluator(policy_directory: Path, *, round_index: int) -> RoundEvaluation:
        nonlocal evaluated
        del policy_directory, round_index
        evaluated = True
        return RoundEvaluation(1.0, (("visible-1", 1.0),), 1, 1, 0.1)

    with pytest.raises(CampaignError, match="unexpected workspace entries"):
        run_researcher_campaign(
            initial_policy_directory=_seed_policy(tmp_path, "coverage-seed-policy"),
            output_directory=tmp_path / "campaign",
            researcher=polluting_researcher,
            evaluator=evaluator,
            config=CampaignConfig(rounds=1, prediction_item_ids=("visible-1",)),
        )
    assert evaluated is False


def test_campaign_rejects_unsafe_policy_and_manifest_coverage(tmp_path: Path) -> None:
    evaluation_calls = 0

    def evaluator(policy_directory: Path, *, round_index: int) -> RoundEvaluation:
        nonlocal evaluation_calls
        del policy_directory, round_index
        evaluation_calls += 1
        return RoundEvaluation(1.0, (("visible-1", 1.0),), 1, 1, 0.1)

    def unsafe_researcher(request: ResearchRoundRequest) -> None:
        (request.policy_directory / "policy.py").write_text("import os\n", encoding="utf-8")
        _manifest(request)

    unsafe = run_researcher_campaign(
        initial_policy_directory=_seed_policy(tmp_path, "parent-seed-policy"),
        output_directory=tmp_path / "unsafe-campaign",
        researcher=unsafe_researcher,
        evaluator=evaluator,
        config=CampaignConfig(rounds=1, prediction_item_ids=("visible-1",)),
    )
    assert evaluation_calls == 0
    assert unsafe.rounds[0].valid is False
    assert unsafe.selected_round is None
    assert unsafe.process is None

    def incomplete_researcher(request: ResearchRoundRequest) -> None:
        _manifest(request, item_ids=("wrong-item",))

    with pytest.raises(ManifestError, match="coverage mismatch"):
        run_researcher_campaign(
            initial_policy_directory=_seed_policy(tmp_path),
            output_directory=tmp_path / "coverage-campaign",
            researcher=incomplete_researcher,
            evaluator=evaluator,
            config=CampaignConfig(rounds=1, prediction_item_ids=("visible-1",)),
        )
    assert evaluation_calls == 0


def test_campaign_rejects_evaluation_coverage_and_evaluator_policy_mutation(
    tmp_path: Path,
) -> None:
    def valid_researcher(request: ResearchRoundRequest) -> None:
        _manifest(request)

    def incomplete_evaluator(policy_directory: Path, *, round_index: int) -> RoundEvaluation:
        del policy_directory, round_index
        return RoundEvaluation(1.0, (("wrong-item", 1.0),), 1, 1, 0.1)

    with pytest.raises(CampaignError, match="evaluation coverage mismatch"):
        run_researcher_campaign(
            initial_policy_directory=_seed_policy(tmp_path, "evaluation-coverage-seed"),
            output_directory=tmp_path / "evaluation-coverage-campaign",
            researcher=valid_researcher,
            evaluator=incomplete_evaluator,
            config=CampaignConfig(rounds=1, prediction_item_ids=("visible-1",)),
        )

    def mutating_evaluator(policy_directory: Path, *, round_index: int) -> RoundEvaluation:
        del round_index
        (policy_directory / "policy.py").write_text("import os\n", encoding="utf-8")
        return RoundEvaluation(1.0, (("visible-1", 1.0),), 1, 1, 0.1)

    with pytest.raises(CampaignError, match="modified the candidate snapshot"):
        run_researcher_campaign(
            initial_policy_directory=_seed_policy(tmp_path, "evaluation-mutation-seed"),
            output_directory=tmp_path / "evaluation-mutation-campaign",
            researcher=valid_researcher,
            evaluator=mutating_evaluator,
            config=CampaignConfig(rounds=1, prediction_item_ids=("visible-1",)),
        )


def test_campaign_reaudits_the_exact_candidate_bytes_after_tree_audit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class TamperingAuditor(PolicyAuditor):
        calls = 0

        def audit_tree(self, root: str | Path) -> AuditReport:
            report = super().audit_tree(root)
            self.calls += 1
            if self.calls == 2:
                (Path(root) / "policy.py").write_text("import os\n", encoding="utf-8")
            return report

    evaluated = False

    def researcher(request: ResearchRoundRequest) -> None:
        _manifest(request)

    def evaluator(policy_directory: Path, *, round_index: int) -> RoundEvaluation:
        nonlocal evaluated
        del policy_directory, round_index
        evaluated = True
        return RoundEvaluation(1.0, (("visible-1", 1.0),), 1, 1, 0.1)

    monkeypatch.setattr(researcher_campaign, "PolicyAuditor", TamperingAuditor)
    with pytest.raises(PolicySecurityError):
        run_researcher_campaign(
            initial_policy_directory=_seed_policy(tmp_path, "toctou-seed"),
            output_directory=tmp_path / "toctou-campaign",
            researcher=researcher,
            evaluator=evaluator,
            config=CampaignConfig(rounds=1, prediction_item_ids=("visible-1",)),
        )
    assert evaluated is False


def test_campaign_requires_a_clean_output_directory_and_exact_manifest_parent(
    tmp_path: Path,
) -> None:
    dirty = tmp_path / "dirty"
    dirty.mkdir()
    (dirty / "prior.txt").write_text("prior", encoding="utf-8")
    with pytest.raises(CampaignError, match="empty"):
        run_researcher_campaign(
            initial_policy_directory=_seed_policy(tmp_path),
            output_directory=dirty,
            researcher=FakeResearcher(),
            evaluator=ToyIsolatedEvaluator(),
            config=CampaignConfig(rounds=1, prediction_item_ids=("visible-1",)),
        )

    def wrong_parent_researcher(request: ResearchRoundRequest) -> None:
        _manifest(request)
        path = request.manifest_path
        raw = path.read_text(encoding="utf-8").replace(request.parent_artifact_id, "a" * 64)
        path.write_text(raw, encoding="utf-8")

    with pytest.raises(CampaignError, match="parent_artifact_id"):
        run_researcher_campaign(
            initial_policy_directory=_seed_policy(tmp_path, "wrong-parent-seed-policy"),
            output_directory=tmp_path / "parent-campaign",
            researcher=wrong_parent_researcher,
            evaluator=ToyIsolatedEvaluator(),
            config=CampaignConfig(rounds=1, prediction_item_ids=("visible-1",)),
        )
