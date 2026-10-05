"""Every computed metric for a pack, from its bars, facts and comparison indices.

One function, so the evidence builder and the signal-flip search compute metrics the
same way.
"""

from __future__ import annotations

from collections.abc import Sequence

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


def number[T: (FinancialFact, DerivedMetric, Announcement, ShareholdingSnapshot, NewsItem)](
    items: list[T], prefix: str,
) -> list[T]:
    return [item.model_copy(update={"evidence_id": f"{prefix}{i}"})
            for i, item in enumerate(items, start=1)]
