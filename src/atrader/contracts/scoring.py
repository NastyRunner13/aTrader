"""The scorecard: what a reader sees first. Built by code in `analytics/scoring.py`."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from atrader.contracts.common import Confidence, Horizon, Pillar, Signal


class Factor(BaseModel):
    """One rule's contribution to a pillar score, with the evidence it read.

    Rules in the same group read the same underlying move, so a group's total is
    capped; the cap shows up as its own factor (`kind="cap"`) so the factors still add
    up to the score."""

    label: str
    points: float
    evidence_ids: list[str] = Field(default_factory=list)
    group: str | None = None
    kind: Literal["rule", "cap"] = "rule"


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


class Level(BaseModel):
    """A price the stock turned from or traded heavily at before. Not a target."""

    kind: Literal["resistance", "support", "average", "vwap", "volume", "range"]
    label: str
    price: float
    detail: str = ""
    evidence_id: str


class SignalFlip(BaseModel):
    """The nearest next-session close that would change a horizon's signal, with
    every other input held as it is."""

    horizon: Horizon
    direction: Literal["up", "down"]
    price: float | None  # None: the signal did not change within the searched range
    signal: Signal | None = None  # the signal at that price
    searched_pct: float


class PriceLevels(BaseModel):
    close: float
    as_of: date
    levels: list[Level] = Field(default_factory=list)  # highest price first
    support_break: Level | None = None  # a close below this breaks the nearest support
    flips: list[SignalFlip] = Field(default_factory=list)


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
    levels: PriceLevels | None = None

    def pillar(self, pillar: Pillar) -> PillarScore:
        return next(p for p in self.pillars if p.pillar == pillar)

    def horizon(self, horizon: Horizon) -> HorizonView:
        return next(h for h in self.horizons if h.horizon == horizon)
