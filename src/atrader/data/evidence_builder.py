"""The data steward: collect, validate and freeze the evidence pack for one run.

Each source is collected independently. A failure becomes a coverage entry, never an
exception, so a missing optional source yields an honest partial pack. Only data
public on or before the cutoff date (IST) is admitted.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from typing import Protocol

from atrader.analytics.fundamentals import fundamental_metrics
from atrader.analytics.patterns import detect_patterns
from atrader.analytics.prices import split_bonus_adjust
from atrader.analytics.technicals import technical_metrics
from atrader.config import Settings
from atrader.contracts import (
    Announcement,
    Coverage,
    CoverageEntry,
    DerivedMetric,
    EvidencePack,
    FinancialFact,
    Listing,
    NewsItem,
    PriceBar,
    ResearchRequest,
    ShareholdingSnapshot,
    SourceRef,
)
from atrader.data.http import FetchError, PoliteClient
from atrader.data.providers import gdelt_news, nse_announcements, nse_bhavcopy, nse_shareholding
from atrader.data.providers.nse_filings import FilingRef, list_result_filings, select_filings
from atrader.data.providers.nse_instruments import InstrumentMaster
from atrader.data.store import MarketStore
from atrader.data.xbrl import KEY_LABELS, XbrlParseError, parse_results_xbrl
from atrader.timeutil import end_of_day_ist, now_utc, today_ist

logger = logging.getLogger(__name__)

QUARTERS_OF_RESULTS = 5  # latest + four earlier: enough for YoY and trailing EPS
MAX_ANNOUNCEMENTS = 25
MAX_SHAREHOLDING = 4
MAX_NEWS = 20
BENCHMARK = "Nifty 50"


class EvidenceSource(Protocol):
    def build(self, request: ResearchRequest) -> EvidencePack: ...


class NseEvidenceBuilder:
    def __init__(
        self,
        client: PoliteClient,
        store: MarketStore,
        settings: Settings,
        instruments: InstrumentMaster | None = None,
        on_progress: Callable[[str], None] | None = None,
    ) -> None:
        self._client = client
        self._store = store
        self._settings = settings
        self._instruments = instruments
        self._progress = on_progress or (lambda _msg: None)

    # --- public --------------------------------------------------------------------------

    def resolve(self, symbol: str) -> Listing:
        if self._instruments is None:
            self._instruments = InstrumentMaster.load(self._client)
        return self._instruments.resolve(symbol)

    def build(self, request: ResearchRequest) -> EvidencePack:
        listing = self.resolve(request.symbol)
        cutoff = request.cutoff or today_ist()
        coverage: list[CoverageEntry] = []

        self._progress("prices")
        bars, price_coverage = self._prices(listing, cutoff)
        coverage.extend(price_coverage)

        self._progress("financial results")
        facts, result_coverage = self._financials(listing, cutoff)
        coverage.append(result_coverage)

        self._progress("announcements")
        announcements, ann_coverage = self._announcements(listing, cutoff)
        coverage.append(ann_coverage)

        self._progress("shareholding")
        shareholding, sh_coverage = self._shareholding(listing, cutoff)
        coverage.append(sh_coverage)

        self._progress("news")
        news, news_coverage = self._news(listing, cutoff)
        coverage.append(news_coverage)

        coverage.append(CoverageEntry(category="macro", status=Coverage.NOT_REQUESTED,
                                      detail="Macro/geopolitics adapters (RBI, MoSPI) are not "
                                             "built yet."))
        coverage.append(CoverageEntry(category="community", status=Coverage.NOT_REQUESTED,
                                      detail="Reddit access is disabled until approved access "
                                             "and permitted processing are confirmed."))

        facts = _number(facts, "F")
        metrics = self._metrics(bars, facts, cutoff)
        return EvidencePack(
            listing=listing,
            cutoff=cutoff,
            built_at=now_utc(),
            facts=tuple(facts),
            metrics=tuple(metrics),
            announcements=tuple(_number(announcements, "A")),
            shareholding=tuple(_number(shareholding, "S")),
            news=tuple(_number(news, "N")),
            bars=tuple(bars),
            coverage=tuple(coverage),
        )

    # --- sources -------------------------------------------------------------------------

    def _prices(self, listing: Listing, cutoff: date) -> tuple[list[PriceBar],
                                                              list[CoverageEntry]]:
        sessions = self._settings.price_history_sessions
        try:
            nse_bhavcopy.ingest_sessions(self._client, self._store, cutoff, sessions + 20)
        except FetchError as exc:
            logger.warning("price ingestion incomplete: %s", exc)
        raw = self._store.bars_for(listing.isin, cutoff, sessions)
        bars, events = split_bonus_adjust(raw)
        if not bars:
            return [], [CoverageEntry(category="prices", status=Coverage.MISSING,
                                      detail="No NSE bhavcopy rows for this ISIN.")]
        age = (cutoff - bars[-1].session).days
        status = Coverage.STALE if age > 7 else (
            Coverage.PARTIAL if len(bars) < sessions * 0.9 else Coverage.AVAILABLE)
        detail = f"{len(bars)} sessions, NSE bhavcopy, {bars[-1].adjustment}"
        if events:
            detail += "; adjustments inferred on " + ", ".join(
                f"{e.session} (x{e.factor:.4f})" for e in events)
        entries = [CoverageEntry(category="prices", status=status, detail=detail,
                                 as_of=bars[-1].session)]
        benchmark = self._store.index_closes(BENCHMARK, cutoff, 2)
        entries.append(CoverageEntry(
            category="benchmark", status=Coverage.AVAILABLE if benchmark else Coverage.MISSING,
            detail=f"{BENCHMARK} daily closes (price index)",
            as_of=benchmark[-1][0] if benchmark else None))
        return bars, entries

    def _financials(self, listing: Listing, cutoff: date) -> tuple[list[FinancialFact],
                                                                  CoverageEntry]:
        refs, errors = list_result_filings(self._client, listing.symbol)
        selected = select_filings(refs, end_of_day_ist(cutoff), QUARTERS_OF_RESULTS)
        if not selected:
            status = Coverage.ACCESS_BLOCKED if errors else Coverage.MISSING
            return [], CoverageEntry(category="financial_results", status=status,
                                     detail="; ".join(errors) or "No result filings found.")
        facts: list[FinancialFact] = []
        failures: list[str] = []
        for ref in selected:
            try:
                facts.extend(self._facts_from_filing(listing, ref))
            except (FetchError, XbrlParseError) as exc:
                failures.append(f"{ref.period_end}: {exc}")
        facts = _merge_restatements(facts)
        latest = max((f.period_end for f in facts), default=None)
        curated = sum(1 for f in facts if f.period_end == latest and f.metric in KEY_LABELS)
        status = Coverage.AVAILABLE
        detail = (f"{len(selected)} quarters of {selected[0].basis.value} XBRL results; latest "
                  f"period {latest}, filed {selected[0].filed_at:%Y-%m-%d %H:%M} IST")
        if failures or errors:
            status = Coverage.PARTIAL
            detail += "; issues: " + "; ".join(failures + errors)
        if curated < 4:
            status = Coverage.PARTIAL
            detail += ("; few standard line items found (bank or insurer taxonomy is not "
                       "curated yet)")
        return facts, CoverageEntry(category="financial_results", status=status, detail=detail,
                                    as_of=latest)

    def _facts_from_filing(self, listing: Listing, ref: FilingRef) -> list[FinancialFact]:
        fetched = self._client.get(ref.xbrl_url)  # filings are immutable: cache forever
        parsed = parse_results_xbrl(fetched.content)
        if parsed.basis and parsed.basis != ref.basis:
            raise XbrlParseError(f"basis mismatch: index says {ref.basis}, file {parsed.basis}")
        source = SourceRef(provider=f"{ref.source_api} (XBRL)", url=ref.xbrl_url,
                           published_at=ref.filed_at, retrieved_at=fetched.retrieved_at,
                           content_hash=fetched.sha256)
        keep = [x for x in parsed.facts
                if x.metric in KEY_LABELS and x.duration in ("quarter", "annual")]
        if sum(1 for x in keep if x.duration == "quarter") < 4:
            keep = [x for x in parsed.facts if x.duration == "quarter"][:40]
        return [
            FinancialFact(
                isin=listing.isin, metric=x.metric, label=x.label, value=x.value, unit=x.unit,
                period_start=x.period_start, period_end=x.period_end, duration=x.duration,
                basis=parsed.basis or ref.basis,
                audited=parsed.audited if parsed.audited is not None else ref.audited,
                rounding=parsed.rounding, filed_at=ref.filed_at, source=source,
            )
            for x in keep
        ]

    def _announcements(self, listing: Listing, cutoff: date) -> tuple[list[Announcement],
                                                                     CoverageEntry]:
        try:
            items = nse_announcements.fetch_announcements(
                self._client, listing.symbol, cutoff, self._settings.announcement_lookback_days)
        except (FetchError, ValueError) as exc:
            return [], CoverageEntry(category="announcements", status=Coverage.ACCESS_BLOCKED,
                                     detail=str(exc))
        boundary = end_of_day_ist(cutoff)
        eligible = [a for a in items if a.published_at <= boundary]
        routine = [a for a in eligible if a.category in nse_announcements.LOW_SIGNAL_CATEGORIES]
        kept = [a for a in eligible if a not in routine][:MAX_ANNOUNCEMENTS]
        orders = sum(1 for a in kept if a.category in nse_announcements.ORDER_CATEGORIES)
        detail = (f"{len(kept)} disclosures in {self._settings.announcement_lookback_days} days "
                  f"({orders} order/contract intimations); {len(routine)} routine filings "
                  "omitted from prompts")
        status = Coverage.AVAILABLE if eligible else Coverage.MISSING
        return kept, CoverageEntry(category="announcements", status=status, detail=detail,
                                   as_of=cutoff)

    def _shareholding(self, listing: Listing, cutoff: date) -> tuple[list[ShareholdingSnapshot],
                                                                    CoverageEntry]:
        try:
            snapshots = nse_shareholding.fetch_shareholding(self._client, listing.symbol)
        except (FetchError, ValueError) as exc:
            return [], CoverageEntry(category="shareholding", status=Coverage.ACCESS_BLOCKED,
                                     detail=str(exc))
        boundary = end_of_day_ist(cutoff)
        eligible = [s for s in snapshots
                    if (s.published_at or end_of_day_ist(s.period_end)) <= boundary]
        kept = eligible[:MAX_SHAREHOLDING]
        if not kept:
            return [], CoverageEntry(category="shareholding", status=Coverage.MISSING)
        return kept, CoverageEntry(
            category="shareholding", status=Coverage.AVAILABLE,
            detail=f"{len(kept)} quarterly patterns (promoter/public split only; pledges not "
                   "yet parsed)", as_of=kept[0].period_end)

    def _news(self, listing: Listing, cutoff: date) -> tuple[list[NewsItem], CoverageEntry]:
        if not self._settings.enable_gdelt_news:
            return [], CoverageEntry(category="news", status=Coverage.NOT_REQUESTED)
        try:
            items = gdelt_news.fetch_company_news(
                self._client, listing.name, cutoff, self._settings.news_lookback_days)
        except (FetchError, ValueError) as exc:
            return [], CoverageEntry(category="news", status=Coverage.ACCESS_BLOCKED,
                                     detail=f"GDELT: {exc}")
        boundary = end_of_day_ist(cutoff)
        aliases = gdelt_news.company_aliases(listing.name, listing.symbol)
        dated = [n for n in items if n.published_at <= boundary]
        relevant = [n for n in dated
                    if gdelt_news.mentions_company(n.title, aliases)][:MAX_NEWS]
        status = Coverage.AVAILABLE if relevant else Coverage.MISSING
        return relevant, CoverageEntry(
            category="news", status=status,
            detail=f"{len(relevant)} of {len(dated)} GDELT headlines over "
                   f"{self._settings.news_lookback_days} days name the company "
                   f"({', '.join(aliases)}); headline metadata only, no article text",
            as_of=cutoff)

    def _metrics(self, bars: list[PriceBar], facts: list[FinancialFact],
                 cutoff: date) -> list[DerivedMetric]:
        benchmark = self._store.index_closes(BENCHMARK, cutoff, len(bars) + 10) if bars else []
        metrics = technical_metrics(bars, benchmark, BENCHMARK) + detect_patterns(bars)
        last_close = bars[-1].close if bars else None
        metrics += fundamental_metrics(facts, last_close, bars[-1].session if bars else None)
        try:
            session, pe = self._store.latest_index_valuation(BENCHMARK, cutoff)
            if pe is not None:
                metrics.append(DerivedMetric(
                    name="nifty50_pe", label=f"{BENCHMARK} P/E (as published by NSE)", value=pe,
                    unit="x", as_of=session, formula="published by NSE indices",
                    inputs=("nse.index_close",), category="market"))
        except LookupError:
            pass
        return resolve_metric_ids(metrics)


def resolve_metric_ids(metrics: list[DerivedMetric]) -> list[DerivedMetric]:
    """Number metrics M1..Mn and replace `M:<name>` input placeholders with real IDs."""
    numbered = _number(metrics, "M")
    by_name = {m.name: m.evidence_id for m in numbered}
    return [
        m.model_copy(update={"inputs": tuple(
            by_name.get(i[2:], i) if i.startswith("M:") else i for i in m.inputs)})
        for m in numbered
    ]


def _number[T: (FinancialFact, DerivedMetric, Announcement, ShareholdingSnapshot, NewsItem)](
    items: list[T], prefix: str,
) -> list[T]:
    return [item.model_copy(update={"evidence_id": f"{prefix}{i}"})
            for i, item in enumerate(items, start=1)]


def _merge_restatements(facts: list[FinancialFact]) -> list[FinancialFact]:
    """Keep the latest-filed value per period; note when an earlier filing differed."""
    groups: dict[tuple[str, date | None, date, str], list[FinancialFact]] = {}
    for fact in facts:
        groups.setdefault((fact.metric, fact.period_start, fact.period_end, fact.duration),
                          []).append(fact)
    merged: list[FinancialFact] = []
    for versions in groups.values():
        versions.sort(key=lambda f: f.filed_at)
        latest = versions[-1]
        earlier = [v for v in versions[:-1] if v.value != latest.value]
        if earlier:
            latest = latest.model_copy(update={"revision_note": (
                f"restated: filing of {earlier[-1].filed_at:%Y-%m-%d} reported "
                f"{earlier[-1].value}")})
        merged.append(latest)
    order = {name: i for i, name in enumerate(KEY_LABELS)}
    merged.sort(key=lambda f: (-f.period_end.toordinal(), f.duration != "quarter",
                               order.get(f.metric, len(order)), f.metric))
    return merged
