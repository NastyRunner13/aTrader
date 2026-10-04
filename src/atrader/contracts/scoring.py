"""The scorecard: what a reader sees first. Built by code in `analytics/scoring.py`."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from atrader.contracts.common import Confidence, Horizon, Pillar, Signal


class Factor(BaseModel):
    """One rule's contribution to a pillar score, with the evidence it read."""

    label: str
    points: float
    evidence_ids: list[str] = Field(default_factory=list)


class PillarScore(BaseModel):
    """A 0-100 score for one area. Every area starts at 50 (no lean either way)."""

    pillar: Pillar
    score: int | None = None  # None: not enough data to score this area
    base: int | None = None  # the code-computed score before the analyst's adjustment
    adjustment: int = 0
    adjustment_reason: str | None = None
    adjustment_evidence: list[str] = Field(default_factory=list)
    factors: list[Factor] = Field(default_factory=list)
    confidence: Confidence = Confidence.LOW
    note: str | None = None


class PriceRange(BaseModel):
    """How far the price has typically moved, or what stated scenarios imply. Not a
    forecast."""

    method: Literal["volatility", "scenario"]
    low: float
    high: float
    base: float | None = None  # scenario ranges only
    confidence: Confidence
    detail: str
    evidence_ids: list[str] = Field(default_factory=list)


class HorizonView(BaseModel):
    horizon: Horizon
    score: int | None
    signal: Signal
    confidence: Confidence
    weights: dict[str, int]  # pillar value -> nominal weight in percent (sums to 100)
    weight_covered: int  # percent of the nominal weight whose pillar had a score
    driven_by: Pillar | None = None
    manager_adjustment: int = 0
    manager_reason: str | None = None
    capped_by: list[str] = Field(default_factory=list)  # veto codes that lowered the score
    price_range: PriceRange | None = None
    drivers: list[str] = Field(default_factory=list)
    up_if: list[str] = Field(default_factory=list)
    down_if: list[str] = Field(default_factory=list)


class Scorecard(BaseModel):
    version: str
    pillars: list[PillarScore]
    horizons: list[HorizonView]
    model_adjusted: bool  # False for code-only scorecards (data_only runs)

    def pillar(self, pillar: Pillar) -> PillarScore:
        return next(p for p in self.pillars if p.pillar == pillar)

    def horizon(self, horizon: Horizon) -> HorizonView:
        return next(h for h in self.horizons if h.horizon == horizon)
