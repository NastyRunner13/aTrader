"""Request and response shapes of the web API. The report itself is the `ResearchReport`
contract; everything here is what surrounds it."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from atrader.contracts import Confidence, Mode, RunStatus, Signal


class ErrorOut(BaseModel):
    code: str
    message: str


class RunBody(BaseModel):
    symbol: str = Field(min_length=1, max_length=24, description="NSE symbol or ISIN")
    mode: Mode = Mode.COMPACT
    cutoff: date | None = None
    dry_run: bool = Field(default=False, description="Placeholder model output; no requests")


class InstrumentOut(BaseModel):
    symbol: str
    name: str
    isin: str


class StageOut(BaseModel):
    key: str
    label: str
    nodes: list[str]
    state: Literal["pending", "running", "partial", "done", "skipped", "error"]


class RunRequestOut(BaseModel):
    symbol: str
    mode: Mode
    cutoff: date | None


class RunOut(BaseModel):
    run_id: str
    status: RunStatus
    detail: str | None = None
    request: RunRequestOut
    dry_run: bool
    created_at: datetime
    updated_at: datetime
    report_id: str | None = None
    cancel_requested: bool = False
    stages: list[StageOut] = []
    last_event_id: int = 0


class HorizonSummary(BaseModel):
    horizon: str
    score: int | None
    signal: Signal
    confidence: Confidence


class ReportSummary(BaseModel):
    report_id: str
    run_id: str
    symbol: str
    name: str | None
    cutoff: date | None
    mode: Mode
    status: RunStatus
    generated_at: datetime
    model_adjusted: bool
    dry_run: bool = False
    close: float | None
    horizons: list[HorizonSummary]


class Quote(BaseModel):
    close: float
    session: date
    change_pct: float | None


class WatchlistItem(BaseModel):
    symbol: str
    name: str
    quote: Quote | None
    latest_report: ReportSummary | None


class Bar(BaseModel):
    session: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    delivery_pct: float | None = Field(description="Delivery share of traded quantity, %")


class Adjustment(BaseModel):
    session: date
    factor: float


class BarsOut(BaseModel):
    symbol: str
    name: str
    isin: str
    adjusted: bool
    adjustments: list[Adjustment]
    bars: list[Bar]
    averages: dict[str, list[float | None]] = Field(
        description="Simple moving averages (sma20, sma50, sma200), one value per bar")


class Usage(BaseModel):
    used_today: int
    usable: int
    remaining: int
    daily_limit: int
    reserve: int


class ModelStatus(BaseModel):
    api_key_set: bool
    quick: str
    deep: str


class StatusOut(BaseModel):
    version: str
    latest_session: date | None
    model: ModelStatus
    active_runs: int
    usage: Usage


class EvidenceOut(BaseModel):
    kind: Literal["facts", "metrics", "announcements", "shareholding", "news",
                  "institutional_activity", "documents", "ownership", "sector_flows",
                  "corporate_actions"]
    item: dict[str, object]
