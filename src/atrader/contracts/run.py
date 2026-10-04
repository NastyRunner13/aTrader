"""Run-level contracts: the request, model-call records and the published report."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from atrader.contracts.agents import (
    AgentReport,
    DebateTurn,
    JudgeVerdict,
    Reason,
    RiskReview,
    StrategyPlan,
    Synthesis,
    Veto,
)
from atrader.contracts.common import Assessment, Horizon, Mode, RunStatus
from atrader.contracts.evidence import CoverageEntry, EvidencePack


class ResearchRequest(BaseModel):
    symbol: str
    exchange: Literal["NSE"] = "NSE"
    horizon: Horizon = Horizon.SWING
    mode: Mode = Mode.COMPACT
    cutoff: date | None = Field(
        default=None, description="Knowledge cutoff; None means the latest completed data."
    )


class ModelCall(BaseModel):
    call_id: str
    run_id: str
    node: str
    attempt: int
    requested_model: str
    served_model: str | None = None
    provider: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost: float | None = None
    status: Literal["ok", "invalid_output", "error", "blocked"]
    error: str | None = None
    latency_ms: int | None = None
    started_at: datetime


class ResearchReport(BaseModel):
    report_id: str
    run_id: str
    generated_at: datetime
    status: RunStatus
    request: ResearchRequest
    pack: EvidencePack | None
    # None for data-only runs, which make no AI assessment.
    assessment: Assessment | None
    assessment_before_vetoes: Assessment | None = None
    vetoes: list[Veto] = Field(default_factory=list)
    coverage: list[CoverageEntry] = Field(default_factory=list)
    analyst_reports: list[AgentReport] = Field(default_factory=list)
    debate: list[DebateTurn] = Field(default_factory=list)
    research_decision: JudgeVerdict | None = None
    trader_plan: StrategyPlan | None = None
    risk_reviews: list[RiskReview] = Field(default_factory=list)
    final_synthesis: Synthesis | None = None
    model_calls: list[ModelCall] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @property
    def top_reasons(self) -> list[Reason]:
        return self.final_synthesis.top_reasons if self.final_synthesis else []
