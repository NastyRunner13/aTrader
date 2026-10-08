"""Agent output contracts.

Two layers per role:

* `*Output` models are what a model is asked to return. They stay small, because
  free models follow small schemas more reliably, and they never contain IDs that
  code is responsible for (claim IDs, call IDs, statuses).
* Stored models (`AgentReport`, `DebateTurn`, ...) add those fields after the
  output has been validated and its citations checked.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atrader.contracts.common import (
    AgentStatus,
    Assessment,
    ClaimKind,
    ClaimStatus,
    Horizon,
    Pillar,
)

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


class ScoreAdjustment(BaseModel):
    pillar: Pillar = Field(description="The code-computed score you are adjusting (your own).")
    points: int = Field(description="Between -15 and +15. Code clamps anything outside.")
    reason: str = Field(description="One sentence: what the scoring rules missed.")
    evidence_ids: list[str] = Field(default_factory=list, description="At least one ID.")


class EventRating(BaseModel):
    event: str = Field(description="One sentence naming the event.")
    impact: int = Field(
        description="-2 clearly negative, -1, 0 neutral, +1, +2 clearly positive for the "
        "company's prospects."
    )
    materiality: Literal["low", "medium", "high"] = Field(
        description="How much the event matters relative to the company's size."
    )
    evidence_ids: list[str] = Field(default_factory=list, description="A or N IDs.")


class _AnalystFields(BaseModel):
    stance: Assessment = Field(
        description="What the evidence in your area suggests overall. Use "
        "insufficient_evidence when your sections are too thin to judge."
    )
    summary: str = Field(description="Three to five sentences. No claims without IDs.")
    claims: list[ClaimDraft] = Field(default_factory=list, max_length=10)
    gaps: list[str] = Field(
        default_factory=list, description="Data you needed but the pack does not contain."
    )


class AnalystOutput(_AnalystFields):
    score_adjustments: list[ScoreAdjustment] = Field(
        default_factory=list, max_length=2,
        description="Usually empty. Adjust a code-computed score only for something its "
        "rules miss.",
    )


class NewsAnalystOutput(_AnalystFields):
    """The news analyst rates events; code turns the ratings into the news score."""

    events: list[EventRating] = Field(default_factory=list, max_length=8)


class AgentReport(BaseModel):
    agent: str
    roles: list[str]
    status: AgentStatus
    stance: Assessment | None = None
    summary: str = ""
    claims: list[Claim] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    score_adjustments: list[ScoreAdjustment] = Field(default_factory=list)  # verified
    events: list[EventRating] = Field(default_factory=list)  # verified
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
# Risk reviewers
# ---------------------------------------------------------------------------------------


class RiskOutput(BaseModel):
    verdict: Literal["too_high", "fair", "too_low"] = Field(
        description="Are the draft scores too optimistic (too_high), fair, or too "
        "pessimistic (too_low) given the risks you see?"
    )
    objections: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(
        default_factory=list, description="Conditions that should hold before relying on "
        "the signal."
    )
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


class HorizonNote(BaseModel):
    horizon: Horizon
    adjustment: int = Field(
        default=0, description="Between -5 and +5 points on the draft score, only where the "
        "debate or risk reviews show it misses something material. Usually 0."
    )
    adjustment_reason: str = ""
    drivers: list[str] = Field(
        default_factory=list, max_length=3,
        description="What most drives this horizon's view, one short line each.",
    )
    up_if: list[str] = Field(
        default_factory=list, max_length=3,
        description="Observable events that would raise the signal.",
    )
    down_if: list[str] = Field(
        default_factory=list, max_length=3,
        description="Observable events that would lower the signal.",
    )


class ThesisTest(BaseModel):
    """A thesis assumption paired with an observable falsifier and a disclosed next event."""

    model_config = ConfigDict(str_strip_whitespace=True)

    assumption: str = Field(min_length=1, max_length=600)
    evidence_ids: list[str] = Field(default_factory=list,
                                    description="Evidence for the assumption.")
    invalidated_by: str = Field(min_length=1, max_length=600,
                                description="Observable condition that would disprove it.")
    next_event: str | None = Field(default=None, max_length=600,
                                   description="Next disclosed event; null when unknown.")
    next_event_date: date | None = None
    next_event_evidence_ids: list[str] = Field(
        default_factory=list, description="Official disclosure A IDs supporting the next event.")


class SynthesisOutput(BaseModel):
    summary: str = Field(description="Two or three plain sentences a non-expert understands.")
    pros: list[Reason] = Field(default_factory=list, max_length=5)
    cons: list[Reason] = Field(default_factory=list, max_length=5)
    horizons: list[HorizonNote] = Field(
        default_factory=list, max_length=3, description="One note each for 1m, 6m and 2y."
    )
    unresolved: list[str] = Field(default_factory=list)
    thesis_tests: list[ThesisTest] = Field(
        default_factory=list, max_length=3,
        description="Three decisive assumptions with falsifiers when supported; missing ones "
        "belong in unresolved. Never invent a disclosed next event.")


class Synthesis(SynthesisOutput):
    status: AgentStatus = AgentStatus.COMPLETED
    dropped_reasons: list[str] = Field(default_factory=list)
    model_call_ids: list[str] = Field(default_factory=list)
    prompt_version: str = ""


# ---------------------------------------------------------------------------------------
# Deterministic risk vetoes
# ---------------------------------------------------------------------------------------


class Veto(BaseModel):
    """A code-enforced constraint. `block` withholds every signal; `cap` holds each
    horizon's score at Neutral or below. A persuasive narrative cannot lift either."""

    code: str
    severity: Literal["block", "cap", "note"]
    message: str
