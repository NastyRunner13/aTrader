"""Evidence records and the frozen evidence pack every agent in a run reads.

Each item in a pack carries a short evidence ID (`F3`, `M12`, `A2`, ...). Agents cite
those IDs; the verifier resolves them against the same pack. IDs are only meaningful
together with `EvidencePack.pack_id`.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from atrader.contracts.common import Coverage, Horizon, StatementBasis
from atrader.contracts.instruments import Listing


class EvidenceKind(StrEnum):
    """Prefix of an evidence ID."""

    FINANCIAL_FACT = "F"
    METRIC = "M"
    ANNOUNCEMENT = "A"
    SHAREHOLDING = "S"
    NEWS = "N"


class SourceRef(BaseModel):
    """Where a piece of evidence came from and when it became public."""

    model_config = ConfigDict(frozen=True)

    provider: str
    url: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    content_hash: str | None = None


class PriceBar(BaseModel):
    """One end-of-day bar. Provider and adjustment basis are part of its identity."""

    model_config = ConfigDict(frozen=True)

    session: date
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    prev_close: float | None = None
    volume: int = Field(ge=0)
    turnover_inr: float | None = None
    trades: int | None = None
    provider: str = "nse.bhavcopy"
    adjustment: Literal["unadjusted", "split_bonus_adjusted"] = "unadjusted"

    @model_validator(mode="after")
    def _consistent_range(self) -> PriceBar:
        too_low_high = self.high < max(self.open, self.close, self.low)
        if too_low_high or self.low > min(self.open, self.close):
            raise ValueError(f"impossible OHLC on {self.session}: {self.open=} "
                             f"{self.high=} {self.low=} {self.close=}")
        return self


class FinancialFact(BaseModel):
    """A reported figure, stored in base units (INR, not crore) with its reporting context."""

    model_config = ConfigDict(frozen=True)

    evidence_id: str = ""
    isin: str
    metric: str  # XBRL element name, e.g. "RevenueFromOperations"
    label: str
    value: Decimal | None
    unit: str  # "INR", "INR/share", "pure", "shares"
    period_start: date | None
    period_end: date
    duration: Literal["quarter", "half_year", "nine_months", "annual", "instant", "other"]
    basis: StatementBasis
    audited: bool | None = None
    rounding: str | None = None  # as declared by the filer, e.g. "Crores"
    filed_at: datetime
    source: SourceRef
    missing_reason: str | None = None
    revision_note: str | None = None  # set when a later filing restated this figure


class DerivedMetric(BaseModel):
    """A value computed in Python from stored inputs. Reproducible from `inputs`."""

    model_config = ConfigDict(frozen=True)

    evidence_id: str = ""
    name: str
    label: str
    value: float | None
    unit: str  # "INR", "%", "ratio", "x", "shares", "signal", "INR/share"
    as_of: date
    formula: str
    formula_version: str = "1"
    inputs: tuple[str, ...] = ()  # evidence IDs or a provider description
    detail: str | None = None
    quality_flags: tuple[str, ...] = ()
    category: Literal["fundamental", "valuation", "technical", "liquidity", "pattern",
                      "market"] = "fundamental"


class Announcement(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str = ""
    isin: str | None
    symbol: str
    category: str
    summary: str
    published_at: datetime
    attachment_url: str | None = None
    source: SourceRef


class ShareholdingSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str = ""
    period_end: date
    promoter_pct: float | None
    public_pct: float | None
    employee_trust_pct: float | None = None
    published_at: datetime | None
    remarks: str | None = None
    source: SourceRef


class NewsItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str = ""
    title: str
    url: str
    domain: str
    published_at: datetime
    language: str | None = None
    source: SourceRef


class CoverageEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: str
    status: Coverage
    detail: str = ""
    as_of: date | None = None


class EvidencePack(BaseModel):
    """Everything a run may cite, frozen before interpretation starts."""

    model_config = ConfigDict(frozen=True)

    listing: Listing
    cutoff: date
    horizon: Horizon
    built_at: datetime
    facts: tuple[FinancialFact, ...] = ()
    metrics: tuple[DerivedMetric, ...] = ()
    announcements: tuple[Announcement, ...] = ()
    shareholding: tuple[ShareholdingSnapshot, ...] = ()
    news: tuple[NewsItem, ...] = ()
    bars: tuple[PriceBar, ...] = ()
    coverage: tuple[CoverageEntry, ...] = ()

    @property
    def pack_id(self) -> str:
        payload = self.model_dump_json(exclude={"built_at"}).encode()
        return hashlib.sha256(payload).hexdigest()[:16]

    def items_by_id(self) -> dict[str, EvidenceItem]:
        items: dict[str, EvidenceItem] = {}
        for group in (self.facts, self.metrics, self.announcements, self.shareholding, self.news):
            for item in group:
                items[item.evidence_id] = item
        return items

    def evidence_ids(self) -> frozenset[str]:
        return frozenset(self.items_by_id())

    def coverage_for(self, category: str) -> CoverageEntry | None:
        return next((c for c in self.coverage if c.category == category), None)

    @property
    def has_core_evidence(self) -> bool:
        """Minimum for an AI conclusion: some prices or some reported financials."""
        return bool(self.bars) or bool(self.facts)


EvidenceItem = FinancialFact | DerivedMetric | Announcement | ShareholdingSnapshot | NewsItem
