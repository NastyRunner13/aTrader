"""Segment economics with intact dimensional and reporting-period identities."""

from collections.abc import Sequence
from itertools import pairwise

from atrader.analytics.fundamentals import EPS
from atrader.contracts import DerivedMetric, FinancialFact


def segment_metrics(facts: Sequence[FinancialFact]) -> list[DerivedMetric]:
    rows = [
        f
        for f in facts
        if f.dimensions
        and f.unit == "INR"
        and f.value is not None
        and f.value.is_finite()
        and f.duration in {"annual", "quarter"}
    ]
    out = []
    for revenue in rows:
        if revenue.metric not in {"SegmentRevenue", "SegmentRevenueFromOperations"}:
            continue
        if revenue.value is None or revenue.value <= 0:
            continue
        # NSE uses separate revenue and finance-cost axes for the same segment members.
        # Canonicalise only this verified axis pair; retain the raw axes on every fact.
        identity = tuple(
            (axis.replace("ReportableSegmentsFinanceCostsAxis", "ReportableSegmentsAxis"), member)
            for axis, member in revenue.dimensions
        )
        matching = [
            f
            for f in rows
            if (
                f.isin,
                f.basis,
                tuple(
                    (
                        axis.replace(
                            "ReportableSegmentsFinanceCostsAxis", "ReportableSegmentsAxis"
                        ),
                        member,
                    )
                    for axis, member in f.dimensions
                ),
                f.period_start,
                f.period_end,
            )
            == (revenue.isin, revenue.basis, identity, revenue.period_start, revenue.period_end)
            and f.metric in {"SegmentProfitBeforeTax", "SegmentProfitLossBeforeTaxAndFinanceCosts"}
        ]
        if len(matching) != 1:
            continue
        profit = matching[0]
        assert profit.value is not None
        label = dict(revenue.dimensions).get("ReportedSegment", str(dict(revenue.dimensions)))
        out.append(
            DerivedMetric(
                name=f"segment_margin_{revenue.evidence_id}",
                label=f"{label}: reported segment profit / revenue ({revenue.duration})",
                value=round(float(profit.value / revenue.value * 100), 4),
                unit="%",
                as_of=revenue.period_end,
                category="segment",
                inputs=(profit.evidence_id, revenue.evidence_id),
                formula=f"{profit.metric} / {revenue.metric} * 100",
                quality_flags=(
                    "segment revenue may include intersegment sales; do not sum to group sales",
                    "profit definition follows the filer; not automatically EBIT",
                ),
            )
        )
    return out


def per_share_history(facts: Sequence[FinancialFact]) -> list[DerivedMetric]:
    """EPS history from a single filing's comparatives avoids mixing split restatements."""
    groups: dict[tuple[object, ...], list[FinancialFact]] = {}
    for f in facts:
        if (
            f.metric == EPS
            and f.duration == "annual"
            and not f.dimensions
            and f.unit == "INR/share"
            and f.value is not None
            and f.value.is_finite()
        ):
            groups.setdefault((f.isin, f.basis, f.source.url, f.filed_at), []).append(f)
    out = []
    seen = set()
    for rows in groups.values():
        for old, new in pairwise(sorted(rows, key=lambda f: f.period_end)):
            if (
                old.value is None
                or old.value <= 0
                or new.value is None
                or not 355 <= (new.period_end - old.period_end).days <= 375
                or new.period_end in seen
            ):
                continue
            seen.add(new.period_end)
            out.append(
                DerivedMetric(
                    name=f"annual_eps_growth_{new.period_end}",
                    label="Annual growth per share",
                    value=round(float(new.value / old.value - 1) * 100, 4),
                    unit="%",
                    as_of=new.period_end,
                    category="capital",
                    inputs=(old.evidence_id, new.evidence_id),
                    formula="(annual EPS / prior annual EPS - 1) * 100, same-filing comparatives",
                    quality_flags=(
                        "relies on filer's comparative EPS restatement; not cycle-normalised",
                    ),
                )
            )
    return out
