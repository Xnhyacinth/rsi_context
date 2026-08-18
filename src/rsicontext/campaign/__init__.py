"""Benchmark-controlled research campaign orchestration."""

from rsicontext.campaign.api_policy_pilot import (
    APIPolicyObservation,
    APIPolicyPilotResult,
    run_api_policy_pilot,
    write_api_policy_pilot,
)
from rsicontext.campaign.researcher import (
    CampaignConfig,
    CampaignError,
    IsolatedEvaluatorCallback,
    ResearchCampaignResult,
    ResearchCampaignRound,
    ResearcherCallback,
    ResearcherTurnError,
    ResearchRoundRequest,
    RoundEvaluation,
    run_researcher_campaign,
)
from rsicontext.campaign.toy import ToyCampaignResult, run_toy_campaign

__all__ = [
    "APIPolicyObservation",
    "APIPolicyPilotResult",
    "CampaignConfig",
    "CampaignError",
    "IsolatedEvaluatorCallback",
    "ResearchCampaignResult",
    "ResearchCampaignRound",
    "ResearchRoundRequest",
    "ResearcherCallback",
    "ResearcherTurnError",
    "RoundEvaluation",
    "ToyCampaignResult",
    "run_api_policy_pilot",
    "run_researcher_campaign",
    "run_toy_campaign",
    "write_api_policy_pilot",
]
