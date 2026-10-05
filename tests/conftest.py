"""Shared fixtures. Everything here is synthetic: no real company data, no network."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from atrader.analytics.metrics import pack_metrics
from atrader.config import Settings
from atrader.contracts import (
    Announcement,
    Coverage,
    CoverageEntry,
    EvidencePack,
    FinancialFact,
    IndexSeries,
    Listing,
    PriceBar,
    ResearchRequest,
    ShareholdingSnapshot,
    SourceRef,
    StatementBasis,
)
from atrader.timeutil import IST, weekdays_back

CUTOFF = date(2026, 9, 30)
LISTING = Listing(symbol="TESTCO", isin="INE000T01019", name="Test Company Limited")


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, data_dir=tmp_path / "data", reports_dir=tmp_path / "reports",
                    openrouter_api_key=None)


def make_bars(sessions: int = 260, end: date = CUTOFF, drift: float = 0.0015) -> list[PriceBar]:
    bars = []
    for i, session in enumerate(weekdays_back(end, sessions)):
        close = 100 * math.exp(drift * i) * (1 + 0.01 * math.sin(i / 3))
        bars.append(PriceBar(
            session=session, open=close * 0.995, high=close * 1.01, low=close * 0.985,
            close=close, prev_close=bars[-1].close if bars else None, volume=1_000_000 + 5_000 * i,
            turnover_inr=close * (1_000_000 + 5_000 * i)))
    return bars


def make_facts() -> list[FinancialFact]:
    quarters = [date(2025, 6, 30), date(2025, 9, 30), date(2025, 12, 31), date(2026, 3, 31),
                date(2026, 6, 30)]
    revenue = [1000, 1050, 1100, 1180, 1200]  # crore
    pbt = [150, 160, 170, 185, 200]
    other_income = [10, 12, 11, 15, 20]
    profit = [110, 118, 125, 136, 150]
    eps = [5.5, 5.9, 6.25, 6.8, 7.5]
    facts = []
    for i, end in enumerate(quarters):
        start = (end.replace(day=1) - timedelta(days=62)).replace(day=1)
        filed = datetime(end.year, end.month, end.day, 18, 0, tzinfo=IST) + timedelta(days=40)
        source = SourceRef(provider="test.xbrl", url=f"https://example.invalid/{end}.xml",
                           published_at=filed)
        for metric, label, value, unit in (
            ("RevenueFromOperations", "Revenue from operations", revenue[i] * 10**7, "INR"),
            ("ProfitBeforeTax", "Profit before tax", pbt[i] * 10**7, "INR"),
            ("OtherIncome", "Other income", other_income[i] * 10**7, "INR"),
            ("ProfitLossForPeriod", "Net profit for the period", profit[i] * 10**7, "INR"),
            ("BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations", "Basic EPS",
             eps[i], "INR/share"),
            ("PaidUpValueOfEquityShareCapital", "Paid-up equity share capital", 200 * 10**7,
             "INR"),
            ("FaceValueOfEquityShareCapital", "Face value per share", 10, "INR/share"),
        ):
            facts.append(FinancialFact(
                isin=LISTING.isin, metric=metric, label=label, value=Decimal(str(value)),
                unit=unit, period_start=start, period_end=end, duration="quarter",
                basis=StatementBasis.CONSOLIDATED, audited=end.month == 3, filed_at=filed,
                source=source))
    return [f.model_copy(update={"evidence_id": f"F{i}"}) for i, f in enumerate(facts, 1)]


def make_index(name: str = "Nifty 50", role: str = "benchmark", *, sessions: int = 260,
               drift: float = 0.0005, pe: float | None = 20.0) -> IndexSeries:
    days = weekdays_back(CUTOFF, sessions)
    closes = tuple((d, 20_000 * math.exp(drift * i)) for i, d in enumerate(days))
    return IndexSeries(name=name, role=role, closes=closes, pe=pe,  # type: ignore[arg-type]
                       pe_as_of=days[-1] if pe is not None else None)


def make_pack(*, bars: list[PriceBar] | None = None, facts: list[FinancialFact] | None = None,
              with_text: bool = True, indices: tuple[IndexSeries, ...] = ()) -> EvidencePack:
    bars = make_bars() if bars is None else bars
    facts = make_facts() if facts is None else facts
    metrics = pack_metrics(bars, facts, indices)
    announcements, shareholding = [], []
    if with_text:
        published = datetime(2026, 9, 15, 12, 0, tzinfo=IST)
        announcements = [Announcement(
            evidence_id="A1", isin=LISTING.isin, symbol="TESTCO",
            category="Bagging/Receiving of orders/contracts",
            summary="Test Company Limited has informed the Exchange about an order.",
            published_at=published, source=SourceRef(provider="test.announcements"))]
        shareholding = [ShareholdingSnapshot(
            evidence_id="S1", period_end=date(2026, 6, 30), promoter_pct=55.0, public_pct=45.0,
            published_at=published, source=SourceRef(provider="test.shareholding"))]
    return EvidencePack(
        listing=LISTING, cutoff=CUTOFF, built_at=datetime.now(UTC),
        facts=tuple(facts), metrics=tuple(metrics), announcements=tuple(announcements),
        shareholding=tuple(shareholding), bars=tuple(bars), indices=indices,
        coverage=(CoverageEntry(category="prices", status=Coverage.AVAILABLE),),
    )


class StaticEvidence:
    """An EvidenceSource that returns a prepared pack."""

    def __init__(self, pack: EvidencePack) -> None:
        self.pack = pack
        self.requests: list[ResearchRequest] = []

    def build(self, request: ResearchRequest) -> EvidencePack:
        self.requests.append(request)
        return self.pack
