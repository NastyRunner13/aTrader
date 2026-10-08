"""Every computed metric for a pack, from its bars, facts and comparison indices.

One function, so the evidence builder and the signal-flip search compute metrics the
same way.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite, sqrt

from atrader.analytics.flows import flow_metrics
from atrader.analytics.fundamentals import fundamental_metrics
from atrader.analytics.levels import level_metrics
from atrader.analytics.patterns import detect_patterns
from atrader.analytics.technicals import technical_metrics
from atrader.contracts import (
    Announcement,
    DerivedMetric,
    FinancialFact,
    IndexSeries,
    InstitutionalActivity,
    NewsItem,
    PriceBar,
    ShareholdingSnapshot,
)


def pack_metrics(bars: Sequence[PriceBar], facts: Sequence[FinancialFact],
                 indices: Sequence[IndexSeries] = (), *,
                 levels: bool = True) -> list[DerivedMetric]:
    benchmark = next((i for i in indices if i.role == "benchmark"), None)
    sector = next((i for i in indices if i.role == "sector"), None)
    metrics = technical_metrics(bars, benchmark, sector) + detect_patterns(list(bars))
    metrics += flow_metrics(bars)
    if levels:
        metrics += level_metrics(bars, facts)
    last = bars[-1] if bars else None
    metrics += fundamental_metrics(list(facts), last.close if last else None,
                                   last.session if last else None)
    for name, index in (("benchmark_pe", benchmark), ("sector_pe", sector)):
        if index is not None and index.pe is not None and index.pe_as_of is not None:
            metrics.append(DerivedMetric(
                name=name, label=f"{index.name} P/E (as published by NSE)", value=index.pe,
                unit="x", as_of=index.pe_as_of, formula="published by NSE indices",
                inputs=("nse.index_close",), category="market", detail=index.name))
    by_name = {m.name: m for m in metrics}
    pe = by_name.get("pe_ttm")
    reference = next((by_name[name] for name in ("sector_pe", "benchmark_pe")
                      if name in by_name and by_name[name].value is not None
                      and isfinite(by_name[name].value or 0) and (by_name[name].value or 0) > 0),
                     None)
    if pe and pe.value is not None and isfinite(pe.value) and pe.value > 0 \
            and reference and reference.value and last:
        # An explicit sensitivity assumption, not management guidance or a forecast.
        annual_return = 0.10
        metrics.append(DerivedMetric(
            name="price_implied_eps_growth_2y", label="EPS growth required for a 10% annual return",
            value=round((sqrt(pe.value / reference.value) * (1 + annual_return) - 1) * 100, 2),
            unit="%", as_of=last.session, category="valuation",
            formula="((pe_ttm / assumed_exit_pe) ** (1 / 2) * 1.10 - 1) * 100",
            inputs=("M:pe_ttm", f"M:{reference.name}"),
            detail=f"Assumptions: 2 years, 10% annual price return, exit P/E "
                   f"{reference.value:.2f}x ({reference.detail}, published {reference.as_of}); "
                   "dividends excluded. Compare with reported growth, not a forecast.",
            quality_flags=("exit multiple and required return are our assumptions",
                           "trailing EPS is not normalised; no cash-flow or reinvestment model"),
        ))
    return resolve_metric_ids(metrics)


def resolve_metric_ids(metrics: list[DerivedMetric]) -> list[DerivedMetric]:
    """Number metrics M1..Mn and replace `M:<name>` input placeholders with real IDs."""
    numbered = number(metrics, "M")
    by_name = {m.name: m.evidence_id for m in numbered}
    return [
        m.model_copy(update={"inputs": tuple(
            by_name.get(i[2:], i) if i.startswith("M:") else i for i in m.inputs)})
        for m in numbered
    ]


def number[T: (FinancialFact, DerivedMetric, Announcement, ShareholdingSnapshot, NewsItem,
                InstitutionalActivity)](
    items: list[T], prefix: str,
) -> list[T]:
    return [item.model_copy(update={"evidence_id": f"{prefix}{i}"})
            for i, item in enumerate(items, start=1)]
