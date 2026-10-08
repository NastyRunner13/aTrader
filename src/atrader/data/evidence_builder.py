"""The data steward: collect, validate and freeze the evidence pack for one run.

Each source is collected independently. A failure becomes a coverage entry, never an
exception, so a missing optional source yields an honest partial pack. Only data
public on or before the cutoff date (IST) is admitted.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from typing import Literal, Protocol

from atrader.analytics.flows import MIN_SESSIONS as MIN_DELIVERY_SESSIONS
from atrader.analytics.flows import WINDOW as FLOW_WINDOW
from atrader.analytics.institutional import institutional_metrics
from atrader.analytics.metrics import number, pack_metrics, resolve_metric_ids
from atrader.analytics.prices import split_bonus_adjust
from atrader.config import Settings
from atrader.contracts import (
    Announcement,
    Coverage,
    CoverageEntry,
    DerivedMetric,
    EvidencePack,
    FinancialFact,
    IndexSeries,
    InstitutionalActivity,
    Listing,
    NewsItem,
    PriceBar,
    ResearchRequest,
    ShareholdingSnapshot,
    SourceRef,
)
from atrader.data.http import FetchError, PoliteClient
from atrader.data.providers import (
    gdelt_news,
    nse_announcements,
    nse_bhavcopy,
    nse_institutional,
    nse_sectors,
    nse_shareholding,
)
from atrader.data.providers.nse_filings import FilingRef, list_result_filings, select_filings
from atrader.data.providers.nse_instruments import InstrumentMaster
from atrader.data.store import MarketStore
from atrader.data.xbrl import KEY_LABELS, XbrlParseError, parse_results_xbrl
from atrader.timeutil import end_of_day_ist, now_utc, today_ist

logger = logging.getLogger(__name__)

QUARTERS_OF_RESULTS = 8  # two non-overlapping trailing years, when available
MAX_ANNOUNCEMENTS = 25
MAX_SHAREHOLDING = 4
MAX_NEWS = 20
BENCHMARK = "Nifty 50"

__all__ = ["EvidenceSource", "NseEvidenceBuilder", "resolve_metric_ids"]


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

        self._progress("sector")
        industry, sector, sector_coverage = self._sector(listing, cutoff)
        coverage.append(sector_coverage)
        benchmark = self._index_series(BENCHMARK, "benchmark", cutoff)
        indices = [i for i in (benchmark, sector) if i is not None]

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

        self._progress("institutional market activity")
        activity, activity_metrics, activity_coverage = self._institutional(cutoff)
        coverage.append(activity_coverage)

        for category, detail in (
            ("business_economics", "Structured segments, customer concentration, competitive "
             "advantage and reinvestment economics are not collected yet."),
            ("financial_resilience", "Cash-flow statements, debt maturities and bank/NBFC "
             "asset-quality and funding metrics are not collected yet."),
            ("institutional_sector_activity", "Fortnightly sector FPI net investment and "
             "assets under custody are not collected; holding-value changes are not flows."),
            ("institutional_ownership", "Detailed company FPI and mutual-fund shares and "
             "percentages are not collected; volume/delivery cannot identify institutions."),
        ):
            coverage.append(CoverageEntry(category=category, status=Coverage.NOT_REQUESTED,
                                          detail=detail))

        coverage.append(CoverageEntry(category="macro", status=Coverage.NOT_REQUESTED,
                                      detail="Macro/geopolitics adapters (RBI, MoSPI) are not "
                                             "built yet."))
        coverage.append(CoverageEntry(category="community", status=Coverage.NOT_REQUESTED,
                                      detail="Reddit access is disabled until approved access "
                                             "and permitted processing are confirmed."))

        facts = number(facts, "F")
        return EvidencePack(
            listing=listing,
            cutoff=cutoff,
            built_at=now_utc(),
            facts=tuple(facts),
            metrics=tuple(resolve_metric_ids([*pack_metrics(bars, facts, indices),
                                              *activity_metrics])),
            institutional_activity=tuple(activity),
            announcements=tuple(number(announcements, "A")),
            shareholding=tuple(number(shareholding, "S")),
            news=tuple(number(news, "N")),
            bars=tuple(bars),
            indices=tuple(indices),
            industry=industry,
            coverage=tuple(coverage),
        )

    # --- sources -------------------------------------------------------------------------

    def _institutional(self, cutoff: date) -> tuple[list[InstitutionalActivity],
                                                   list[DerivedMetric], CoverageEntry]:
        errors: list[str] = []
        if cutoff >= today_ist():
            _, errors = nse_institutional.collect_activity(self._client, self._store)
        rows = number(self._store.institutional_activity(cutoff), "I")
        # Price/index archives supply the session calendar; activity alone cannot prove
        # there were no missing trading days between the observations we happened to save.
        sessions = sorted({d for dataset in ("equity", "index")
                           for d, status in self._store.known_sessions(dataset).items()
                           if status == "ok" and d <= cutoff})
        metrics = institutional_metrics(rows, sessions)
        expected = {f"{participant}_{scope}_provisional_nse.institutional_net_{window}s"
                    for participant in ("fpi", "dii") for scope in ("nse", "combined")
                    for window in (5, 20, 60)}
        complete = sum(m.value is not None and m.name in expected for m in metrics)
        latest = max((r.session for r in rows), default=None)
        status = Coverage.AVAILABLE if complete == 12 and not errors else Coverage.PARTIAL
        if not rows:
            status = Coverage.ACCESS_BLOCKED if errors else Coverage.MISSING
        elif latest and (cutoff - latest).days > 7:
            status = Coverage.STALE
        detail = (f"{len(rows)} stored observations; {complete}/12 complete 5/20/60-session "
                  "trends across FPI/DII and NSE-only/combined scopes. Provisional cash "
                  "activity, no company-level attribution or scoring weight. History "
                  "accumulates on collection; availability uses observation timestamps, "
                  "not backdated session dates. Custodian-confirmed data is not collected.")
        if errors:
            detail += " Collection issues: " + "; ".join(errors)
        return rows, metrics, CoverageEntry(category="institutional_market_activity",
                                             status=status, detail=detail, as_of=latest)

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
        recent = bars[-FLOW_WINDOW:]
        delivered = sum(1 for b in recent if b.delivery_pct is not None)
        entries.append(CoverageEntry(
            category="delivery",
            status=(Coverage.AVAILABLE if delivered == len(recent) else Coverage.PARTIAL
                    if delivered >= MIN_DELIVERY_SESSIONS else Coverage.MISSING),
            detail=f"NSE delivery position for {delivered} of the last {len(recent)} sessions",
            as_of=next((b.session for b in reversed(bars) if b.delivery_pct is not None),
                       None)))
        benchmark = self._store.index_closes(BENCHMARK, cutoff, 2)
        entries.append(CoverageEntry(
            category="benchmark", status=Coverage.AVAILABLE if benchmark else Coverage.MISSING,
            detail=f"{BENCHMARK} daily closes (price index)",
            as_of=benchmark[-1][0] if benchmark else None))
        return bars, entries

    def _index_series(self, name: str, role: Literal["benchmark", "sector"],
                      cutoff: date) -> IndexSeries | None:
        closes = self._store.index_closes(name, cutoff,
                                          self._settings.price_history_sessions + 10)
        if not closes:
            return None
        try:
            pe_session, pe = self._store.latest_index_valuation(name, cutoff)
        except LookupError:
            pe_session, pe = None, None
        return IndexSeries(name=name, role=role, closes=tuple(closes), pe=pe,
                           pe_as_of=pe_session if pe is not None else None)

    def _sector(self, listing: Listing, cutoff: date) -> tuple[str | None, IndexSeries | None,
                                                               CoverageEntry]:
        try:
            industries = nse_sectors.fetch_industries(self._client)
        except (FetchError, ValueError) as exc:
            return None, None, CoverageEntry(category="sector", status=Coverage.ACCESS_BLOCKED,
                                             detail=str(exc))
        industry = industries.get(listing.isin)
        if industry is None:
            return None, None, CoverageEntry(
                category="sector", status=Coverage.MISSING,
                detail="Not in the Nifty Total Market list, so no NSE industry to compare with.")
        index_name = nse_sectors.SECTOR_INDEX.get(industry)
        series = self._index_series(index_name, "sector", cutoff) if index_name else None
        if series is None:
            reason = (f"no stored closes for {index_name}" if index_name
                      else "no close-fitting NSE sector index")
            return industry, None, CoverageEntry(category="sector", status=Coverage.PARTIAL,
                                                 detail=f"NSE industry {industry}; {reason}.")
        pe = (f"P/E {series.pe:.1f}x on {series.pe_as_of}" if series.pe is not None
              else "no published P/E")
        return industry, series, CoverageEntry(
            category="sector", status=Coverage.AVAILABLE, as_of=series.closes[-1][0],
            detail=f"NSE industry {industry} (today's classification), compared with "
                   f"{series.name}: {len(series.closes)} sessions, {pe}")

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
        candidates = sorted((a for a in eligible if a not in routine),
                            key=lambda a: a.published_at, reverse=True)
        kept = candidates[:MAX_ANNOUNCEMENTS]
        truncated = len(candidates) - len(kept)
        orders = sum(1 for a in kept if a.category in nse_announcements.ORDER_CATEGORIES)
        detail = (f"{len(kept)} disclosures in {self._settings.announcement_lookback_days} days "
                  f"({orders} order/contract intimations); {len(routine)} routine filings "
                  f"omitted from prompts; {truncated} additional disclosures omitted by "
                  "the prompt limit. Broad Updates are retained for content review; "
                  "attachment contents are not loaded.")
        status = (Coverage.PARTIAL if truncated else Coverage.AVAILABLE if eligible
                  else Coverage.MISSING)
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
