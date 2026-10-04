"""Price ranges for the outlook horizons, computed in code (never by a model).

1 month and 6 months: the last close plus or minus one standard deviation of the past
year's volatility over the horizon. 2 years: bear, base and bull scenarios from stated
growth and P/E assumptions; the bear case always sits below today's price. Both describe
uncertainty; neither predicts direction.
"""

from __future__ import annotations

import math
from statistics import mean
from typing import NamedTuple

from atrader.contracts import Confidence, EvidencePack, Horizon, PriceRange


class MetricValue(NamedTuple):
    value: float
    evidence_id: str
    detail: str


def known_metrics(pack: EvidencePack) -> dict[str, MetricValue]:
    """Metrics that have a value, by name."""
    return {m.name: MetricValue(m.value, m.evidence_id, m.detail or "")
            for m in pack.metrics if m.value is not None}


def price_range(pack: EvidencePack, horizon: Horizon) -> PriceRange | None:
    metrics = known_metrics(pack)
    if horizon == Horizon.TWO_YEARS:
        return _scenarios(metrics)
    return _volatility_band(metrics, horizon)


def _volatility_band(metrics: dict[str, MetricValue], horizon: Horizon) -> PriceRange | None:
    close, vol = metrics.get("close"), metrics.get("volatility_1y")
    if not close or not vol:
        return None
    sigma = vol.value / 100 * math.sqrt(horizon.sessions / 252)
    return PriceRange(
        method="volatility", low=close.value * math.exp(-sigma),
        high=close.value * math.exp(sigma), confidence=Confidence.MEDIUM,
        detail=(f"Last close ±1 standard deviation of its past volatility "
                f"({vol.value:.0f}% a year) over {horizon.sessions} sessions. About 2 in 3 "
                "outcomes land inside if volatility stays the same; it says nothing about "
                "direction."),
        evidence_ids=[close.evidence_id, vol.evidence_id],
    )


def _scenarios(metrics: dict[str, MetricValue]) -> PriceRange | None:
    eps, pe = metrics.get("eps_ttm"), metrics.get("pe_ttm")
    high, low = metrics.get("high_52w"), metrics.get("low_52w")
    growth = [g for g in (metrics.get("revenue_yoy"), metrics.get("profit_yoy")) if g]
    if not (eps and pe and high and low and growth) or eps.value <= 0:
        return None
    base = max(0.0, min(20.0, mean(g.value for g in growth))) / 100
    # Bear: earnings stall or shrink and the multiple de-rates by at least a fifth, so the
    # bear case always sits below today's price. Bull: faster growth at the year's top
    # multiple.
    rates = (max(-0.10, min(0.0, base - 0.15)), base, min(base + 0.06, 0.30))
    multiples = (min(low.value / eps.value, pe.value * 0.8), pe.value,
                 max(high.value / eps.value, pe.value))
    bear, middle, bull = (eps.value * (1 + g) ** 2 * x for g, x in zip(rates, multiples,
                                                                        strict=True))
    return PriceRange(
        method="scenario", low=bear, base=middle, high=bull, confidence=Confidence.LOW,
        detail=(f"Trailing EPS ₹{eps.value:.2f} grown {rates[0]:.0%} / {rates[1]:.0%} / "
                f"{rates[2]:.0%} a year for two years, times a P/E of {multiples[0]:.1f}x / "
                f"{multiples[1]:.1f}x / {multiples[2]:.1f}x (bear: the lower of the 52-week-low "
                "multiple and a 20% de-rating; base: today's; bull: the 52-week-high "
                "multiple). Base growth averages the latest quarter's revenue and profit growth "
                "year on year, held between 0% and 20%. One quarter is a thin base, so treat "
                "this as a rough sketch."),
        evidence_ids=[eps.evidence_id, pe.evidence_id, low.evidence_id, high.evidence_id,
                      *(g.evidence_id for g in growth)],
    )
