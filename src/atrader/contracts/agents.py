"""Agent output contracts.

Two layers per role:

* `*Output` models are what a model is asked to return. They stay small, because
  free models follow small schemas more reliably, and they never contain IDs that
  code is responsible for (claim IDs, call IDs, statuses).
* Stored models (`AgentReport`, `DebateTurn`, ...) add those fields after the
  output has been validated and its citations checked.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from atrader.contracts.common import AgentStatus, Assessment, ClaimKind, ClaimStatus

# ---------------------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------------------


class ClaimDraft(BaseModel):
    statement: str = Field(description="One specific, checkable sentence.")
    kind: ClaimKind = Field(
        description="fact = reported figure or event; calculation = derived number; "
        "interpretation = reasoned judgement; scenario = conditional possibility."
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="IDs from the evidence pack (e.g. F3, M12, A2). Facts and "
        "calculations need at least one. Never invent an ID.",
    )
    assumptions: list[str] = Field(default_factory=list)


class Claim(ClaimDraft):
    claim_id: str
    agent: str
    status: ClaimStatus
    issues: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------------------
# Analysts
# ---------------------------------------------------------------------------------------


class AnalystOutput(BaseModel):
    stance: Assessment = Field(
        description="What the evidence in your area suggests for the horizon. Use "
        "insufficient_evidence when your sections are too thin to judge."
    )
    summary: str = Field(description="Three to five sentences. No claims without IDs.")
    claims: list[ClaimDraft] = Field(default_factory=list, max_length=10)
    gaps: list[str] = Field(
        default_factory=list, description="Data you needed but the pack does not contain."
    )


class AgentReport(BaseModel):
    agent: str
    roles: list[str]
    status: AgentStatus
    stance: Assessment | None = None
    summary: str = ""
    claims: list[Claim] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    model_call_ids: list[str] = Field(default_factory=list)
    prompt_version: str = ""
    error: str | None = None

    @property
    def supported_claims(self) -> list[Claim]:
        return [c for c in self.claims if c.status != ClaimStatus.UNSUPPORTED]


# ---------------------------------------------------------------------------------------
# Bull / bear debate
# ---------------------------------------------------------------------------------------


class Challenge(BaseModel):
    target_claim_id: str = Field(description="The claim ID you dispute, e.g. C-bull-1-2.")
    dispute: Literal["fact", "assumption", "mechanism", "valuation"]
    argument: str
    evidence_ids: list[str] = Field(default_factory=list)


class DebateOutput(BaseModel):
    thesis: str = Field(description="Your side's strongest supported case, 3-5 sentences.")
    claims: list[ClaimDraft] = Field(default_factory=list, max_length=8)
    challenges: list[Challenge] = Field(default_factory=list, max_length=6)
    falsifiers: list[str] = Field(
        default_factory=list, description="Observable events that would prove your side wrong."
    )
    unresolved_questions: list[str] = Field(default_factory=list)


class DebateTurn(BaseModel):
    turn_index: int
    side: Literal["bull", "bear"]
    phase: Literal["opening", "rebuttal"]
    status: AgentStatus
    thesis: str = ""
    claims: list[Claim] = Field(default_factory=list)
    challenges: list[Challenge] = Field(default_factory=list)
    falsifiers: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    model_call_ids: list[str] = Field(default_factory=list)
    prompt_version: str = ""
    error: str | None = None


# ---------------------------------------------------------------------------------------
# Research judge
# ---------------------------------------------------------------------------------------


class JudgeOutput(BaseModel):
    stronger_side: Literal["bull", "bear", "balanced"]
    assessment: Assessment
    resolved: list[str] = Field(default_factory=list, description="Disputes settled by evidence.")
    unresolved: list[str] = Field(default_factory=list)
    decisive_claim_ids: list[str] = Field(default_factory=list)
    rationale: str


class JudgeVerdict(JudgeOutput):
    status: AgentStatus = AgentStatus.COMPLETED
    model_call_ids: list[str] = Field(default_factory=list)
    prompt_version: str = ""


# ---------------------------------------------------------------------------------------
# Hypothetical strategy (never an order)
# ---------------------------------------------------------------------------------------


class Scenario(BaseModel):
    name: str
    description: str
    triggers: list[str] = Field(default_factory=list)


class StrategyOutput(BaseModel):
    stance: Literal["consider_long", "watch", "avoid", "no_view"]
    conditions_to_consider: list[str] = Field(default_factory=list)
    invalidation: list[str] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list, max_length=4)
    evidence_ids: list[str] = Field(default_factory=list)


class StrategyPlan(StrategyOutput):
    status: AgentStatus = AgentStatus.COMPLETED
    model_call_ids: list[str] = Field(default_factory=list)
    prompt_version: str = ""


# ---------------------------------------------------------------------------------------
# Risk reviewers
# ---------------------------------------------------------------------------------------


class RiskOutput(BaseModel):
    verdict: Literal["support", "caution", "oppose"]
    objections: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str


class RiskReview(RiskOutput):
    perspective: Literal["aggressive", "conservative", "neutral"]
    status: AgentStatus = AgentStatus.COMPLETED
    model_call_ids: list[str] = Field(default_factory=list)
    prompt_version: str = ""


# ---------------------------------------------------------------------------------------
# Final synthesis
# ---------------------------------------------------------------------------------------


class Reason(BaseModel):
    statement: str
    evidence_ids: list[str] = Field(default_factory=list)


class SynthesisOutput(BaseModel):
    assessment: Assessment
    summary: str = Field(description="Four to six sentences for a careful reader.")
    top_reasons: list[Reason] = Field(default_factory=list, max_length=5)
    key_risks: list[Reason] = Field(default_factory=list, max_length=5)
    strengthen_if: list[str] = Field(default_factory=list)
    weaken_if: list[str] = Field(default_factory=list)
    invalidate_if: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


class Synthesis(SynthesisOutput):
    status: AgentStatus = AgentStatus.COMPLETED
    dropped_reasons: list[str] = Field(default_factory=list)
    model_call_ids: list[str] = Field(default_factory=list)
    prompt_version: str = ""


# ---------------------------------------------------------------------------------------
# Deterministic risk vetoes
# ---------------------------------------------------------------------------------------


class Veto(BaseModel):
    """A code-enforced constraint. `block` forces insufficient evidence; `cap` limits
    a supportive assessment to mixed. A persuasive narrative cannot lift either."""

    code: str
    severity: Literal["block", "cap", "note"]
    message: str
