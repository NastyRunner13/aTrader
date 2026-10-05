"""The scorecard: code-computed area scores, horizon weights and signals.

Each area ("pillar") starts at 50, meaning no lean either way. Rules add or subtract
points for what the evidence shows, and every rule names the evidence it read, so each
score can be traced. An analyst may then move its own area by up to ±15 points with a
cited reason; the news area is built from the news analyst's event ratings instead.
Each horizon weights the areas differently, the portfolio manager may move a horizon
by up to ±5, and the vetoes cap or block the result.

Technical rules come in groups (trend, momentum, performance, breakout, flows). Rules
in one group read the same underlying move, so each group's total is capped; otherwise
one price drop would count once per indicator that sees it.

The rules and weights are starting priors, not values fitted to returns. The
`--cutoff` backtest (docs/09) is how they should be tuned.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from math import copysign, log2

from atrader.analytics.levels import build_levels
from atrader.analytics.ranges import MetricValue, known_metrics, price_range
from atrader.analytics.vetoes import (
    MIN_SESSIONS_FOR_TECHNICALS,
    STALE_PRICE_DAYS,
    STALE_RESULTS_DAYS,
)
from atrader.contracts import (
    AgentReport,
    AgentStatus,
    Confidence,
    EvidencePack,
    Factor,
    Horizon,
    HorizonNote,
    HorizonView,
    Pillar,
    PillarScore,
    Scorecard,
    Signal,
    Veto,
)

VERSION = "scorecard/2"

# Percent weight of each area per horizon. Short horizons lean on price action and
# news; long ones on the business and the price paid for it.
WEIGHTS: dict[Horizon, dict[Pillar, int]] = {
    Horizon.ONE_MONTH: {Pillar.TECHNICAL: 45, Pillar.GROWTH_QUALITY: 15,
                        Pillar.VALUATION: 10, Pillar.NEWS: 30},
    Horizon.SIX_MONTHS: {Pillar.TECHNICAL: 20, Pillar.GROWTH_QUALITY: 35,
                         Pillar.VALUATION: 25, Pillar.NEWS: 20},
    Horizon.TWO_YEARS: {Pillar.TECHNICAL: 5, Pillar.GROWTH_QUALITY: 45,
                        Pillar.VALUATION: 35, Pillar.NEWS: 15},
}

# The lowest score in each signal band.
SIGNAL_BANDS = ((71, Signal.STRONG_BULLISH), (56, Signal.BULLISH), (45, Signal.NEUTRAL),
                (30, Signal.BEARISH), (0, Signal.STRONG_BEARISH))

# The most each group of technical rules can move the technical score, either way.
TECHNICAL_GROUPS = {"trend": 10, "momentum": 6, "performance": 8, "breakout": 6, "flows": 10}
RISING_VOLUME = 1.2  # volume EMA20 / EMA50 at or above this counts as rising participation

MAX_ANALYST_ADJUSTMENT = 15
MAX_MANAGER_ADJUSTMENT = 5
MIN_WEIGHT_COVERED = 60  # percent of a horizon's weight that needs a score, or no signal
CAP_SCORE = 55  # a `cap` veto holds every horizon at Neutral or below
GROWTH_PAR = 8.0  # % a year: growth below this counts against a business, above for it
NEWS_POINTS = {"low": 2, "medium": 4, "high": 7}  # per step of impact (-2..+2)
NEWS_MAX_SWING = 40
HEADLINE_ONLY = 0.5  # a headline reports that something happened; it is not proof

_LEVELS = {Confidence.LOW: 1, Confidence.MEDIUM: 2, Confidence.HIGH: 3}


def signal_for(score: int | None) -> Signal:
    if score is None:
        return Signal.INSUFFICIENT_DATA
    return next(signal for floor, signal in SIGNAL_BANDS if score >= floor)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# --- base scores (code only) ----------------------------------------------------------


def base_scores(pack: EvidencePack) -> dict[str, PillarScore]:
    """The code-computed score of every area, keyed by pillar value."""
    metrics = known_metrics(pack)
    scores = [
        _technical(pack, metrics),
        _growth_quality(pack, metrics),
        _valuation(metrics),
        PillarScore(pillar=Pillar.NEWS, note="needs the news analyst to rate events"),
    ]
    return {s.pillar.value: s for s in scores}


class _Rules:
    """Collects the points each rule adds to one area."""

    def __init__(self, pillar: Pillar) -> None:
        self.pillar = pillar
        self.factors: list[Factor] = []

    def add(self, label: str, points: float, *evidence_ids: str,
            group: str | None = None) -> None:
        self.factors.append(Factor(label=label, points=round(points, 1),
                                   evidence_ids=list(evidence_ids), group=group))

    def cap_groups(self, caps: Mapping[str, float]) -> None:
        """Hold each group's total within its cap. The cut is its own factor, so the
        factors still add up to the score."""
        for group, cap in caps.items():
            members = [f for f in self.factors if f.group == group]
            total = sum(f.points for f in members)
            if abs(total) <= cap:
                continue
            ids = list(dict.fromkeys(i for f in members for i in f.evidence_ids))
            self.factors.append(Factor(
                label=f"{group.title()} rules capped at {copysign(cap, total):+.0f}: they read "
                      "the same move", points=round(copysign(cap, total) - total, 1),
                evidence_ids=ids, group=group, kind="cap"))

    def result(self, confidence: Confidence, note: str | None = None,
               max_swing: float = 50) -> PillarScore:
        swing = clamp(sum(f.points for f in self.factors), -max_swing, max_swing)
        score = round(clamp(50 + swing, 0, 100))
        return PillarScore(pillar=self.pillar, score=score, base=score, factors=self.factors,
                           confidence=confidence, note=note)


def _scaled(value: float, full: float, max_points: float) -> float:
    """Points proportional to `value`, reaching `max_points` at `full`, then capped."""
    return clamp(value / full * max_points, -max_points, max_points)


def _technical(pack: EvidencePack, m: dict[str, MetricValue]) -> PillarScore:
    if len(pack.bars) < MIN_SESSIONS_FOR_TECHNICALS or "close" not in m:
        return PillarScore(pillar=Pillar.TECHNICAL, note=f"needs at least "
                           f"{MIN_SESSIONS_FOR_TECHNICALS} sessions of prices")
    rules = _Rules(Pillar.TECHNICAL)
    # trend: where the price sits against its long averages
    if trend := m.get("ma_trend"):
        rules.add(f"Moving-average trend: {trend.detail}", 6 * trend.value, trend.evidence_id,
                  group="trend")
    for window, points, group in ((200, 4, "trend"), (50, 3, "trend"), (20, 3, "momentum")):
        if gap := m.get(f"close_vs_sma{window}"):
            above = gap.value > 0
            rules.add(f"Close {'above' if above else 'below'} its {window}-day average "
                      f"({gap.value:+.1f}%)", points if above else -points, gap.evidence_id,
                      group=group)
    # momentum: the last few weeks
    if macd := m.get("macd_hist"):
        positive = macd.value > 0
        rules.add(f"MACD histogram {'positive' if positive else 'negative'}",
                  4 if positive else -4, macd.evidence_id, group="momentum")
    if rsi := m.get("rsi14"):
        label, rsi_points = _rsi_rule(rsi.value)
        rules.add(label, rsi_points, rsi.evidence_id, group="momentum")
    # performance: the 3-month return, alone and against the market and the sector
    if returns := m.get("return_3m"):
        rules.add(f"3-month return {returns.value:+.1f}%", _scaled(returns.value, 15, 6),
                  returns.evidence_id, group="performance")
    for name in ("rel_strength_3m", "rel_strength_3m_sector"):
        if relative := m.get(name):
            rules.add(f"{relative.value:+.1f} pp vs {relative.detail} over 3 months",
                      _scaled(relative.value, 10, 6), relative.evidence_id, group="performance")
    if (breakout := m.get("range_breakout")) and breakout.value:
        rules.add(f"Confirmed range breakout {'up' if breakout.value > 0 else 'down'}",
                  6 * breakout.value, breakout.evidence_id, group="breakout")
    _flow_rules(rules, m)
    rules.cap_groups(TECHNICAL_GROUPS)

    age = (pack.cutoff - pack.bars[-1].session).days
    confidence = (Confidence.LOW if age > STALE_PRICE_DAYS
                  else Confidence.HIGH if len(pack.bars) >= 200 else Confidence.MEDIUM)
    return rules.result(confidence)


def _flow_rules(rules: _Rules, m: dict[str, MetricValue]) -> None:
    """Volume and delivery: which side of the tape the shares are on."""
    if delivery := m.get("delivery_updown20"):
        rules.add(f"Average delivered volume on up days {delivery.value:.2f}x down days "
                  "(20 sessions)", _scaled(log2(delivery.value), 1, 5), delivery.evidence_id,
                  group="flows")
    if volume := m.get("updown_volume20"):
        rules.add(f"Average volume on up days {volume.value:.2f}x down days (20 sessions)",
                  _scaled(log2(volume.value), 1, 4), volume.evidence_id, group="flows")
    trend, month = m.get("volume_ema_ratio"), m.get("return_1m")
    if trend and month and trend.value >= RISING_VOLUME and abs(month.value) >= 2:
        rising = month.value > 0
        rules.add(f"Volume rising (EMA20 {trend.value:.2f}x EMA50) behind the 1-month "
                  f"{'gain' if rising else 'fall'}", 2 if rising else -2, trend.evidence_id,
                  month.evidence_id, group="flows")


def _rsi_rule(rsi: float) -> tuple[str, float]:
    if rsi >= 70:
        return f"RSI {rsi:.0f}: overbought, stretched", -3
    if rsi >= 55:
        return f"RSI {rsi:.0f}: firm momentum", 5
    if rsi > 45:
        return f"RSI {rsi:.0f}: neutral", 0
    if rsi > 30:
        return f"RSI {rsi:.0f}: weak momentum", -5
    return f"RSI {rsi:.0f}: oversold; weak but stretched", -2


def _growth_quality(pack: EvidencePack, m: dict[str, MetricValue]) -> PillarScore:
    revenue, profit = m.get("revenue_yoy"), m.get("profit_yoy")
    if revenue is None and profit is None:
        return PillarScore(pillar=Pillar.GROWTH_QUALITY,
                           note="needs the same quarter a year earlier to compare")
    rules = _Rules(Pillar.GROWTH_QUALITY)
    if revenue:
        rules.add(f"Revenue {revenue.value:+.1f}% year on year",
                  _scaled(revenue.value - GROWTH_PAR, 12, 10), revenue.evidence_id)
    if profit:
        rules.add(f"Profit {profit.value:+.1f}% year on year",
                  _scaled(profit.value - GROWTH_PAR, 20, 12), profit.evidence_id)
    if margin := m.get("pbt_margin_change_yoy"):
        rules.add(f"Pre-tax margin {margin.value:+.1f} pp year on year",
                  _scaled(margin.value, 3, 6), margin.evidence_id)
    if (other := m.get("other_income_share")) and other.value > 15:
        rules.add(f"Other income is {other.value:.0f}% of pre-tax profit",
                  -6 if other.value > 25 else -3, other.evidence_id)
    holdings = sorted((s for s in pack.shareholding if s.promoter_pct is not None),
                      key=lambda s: s.period_end)
    if len(holdings) >= 2:
        first, last = holdings[0], holdings[-1]
        change = (last.promoter_pct or 0) - (first.promoter_pct or 0)
        if change <= -2 or change >= 1:
            rules.add(f"Promoter holding {'down' if change < 0 else 'up'} {abs(change):.1f} pp "
                      f"since {first.period_end:%b %Y}", -4 if change < 0 else 3,
                      first.evidence_id, last.evidence_id)

    latest = max(f.period_end for f in pack.facts)
    stale = (pack.cutoff - latest).days > STALE_RESULTS_DAYS
    confidence = Confidence.LOW if stale or not (revenue and profit) else Confidence.MEDIUM
    return rules.result(confidence, note="one quarter's year-on-year comparison; multi-year "
                        "history is not loaded yet")


def _valuation(m: dict[str, MetricValue]) -> PillarScore:
    eps = m.get("eps_ttm")
    if eps is None:
        return PillarScore(pillar=Pillar.VALUATION,
                           note="needs four consecutive quarters of EPS and a price")
    rules = _Rules(Pillar.VALUATION)
    if eps.value <= 0:
        rules.add("Loss-making over the last four quarters", -25, eps.evidence_id)
        return rules.result(Confidence.MEDIUM)

    pe, profit = m.get("pe_ttm"), m.get("profit_yoy")
    market, sector = _positive(m.get("benchmark_pe")), _positive(m.get("sector_pe"))
    if pe and sector:
        # The sector is the like-for-like comparison. The market comparison stays at a
        # third of the weight, so a whole sector priced far above the market still counts.
        rules.add(f"P/E {pe.value:.1f}x vs {sector.detail} {sector.value:.1f}x",
                  _pe_points(pe.value, sector.value, 12, 15), pe.evidence_id,
                  sector.evidence_id)
        if market:
            rules.add(f"P/E {pe.value:.1f}x vs {market.detail} {market.value:.1f}x (market "
                      "context)", _pe_points(pe.value, market.value, 4, 5), pe.evidence_id,
                      market.evidence_id)
    elif pe and market:
        rules.add(f"P/E {pe.value:.1f}x vs {market.detail} {market.value:.1f}x",
                  _pe_points(pe.value, market.value, 12, 15), pe.evidence_id,
                  market.evidence_id)
    if pe and profit:
        if profit.value <= 0:
            rules.add(f"P/E {pe.value:.1f}x while profit fell {profit.value:.1f}%", -5,
                      pe.evidence_id, profit.evidence_id)
        else:
            peg = pe.value / profit.value
            points = 8 if peg < 1 else 4 if peg < 1.5 else 0 if peg <= 2.5 else -5
            rules.add(f"P/E to profit growth {peg:.1f} (one quarter's growth)", points,
                      pe.evidence_id, profit.evidence_id)
    if not rules.factors:
        return PillarScore(pillar=Pillar.VALUATION,
                           note="no index P/E or profit growth to compare the P/E with")
    if sector:
        note = (f"P/E is compared with {sector.detail} (NSE-published, today's industry "
                "classification; a large company can dominate its own sector index) and the "
                "market; own-history comparison is not built yet")
    else:
        note = ("P/E is compared with the market only (no sector index for this stock); "
                "own-history comparison is not built yet")
    return rules.result(Confidence.MEDIUM if pe and (sector or market) else Confidence.LOW,
                        note=note)


def _positive(metric: MetricValue | None) -> MetricValue | None:
    return metric if metric is not None and metric.value > 0 else None


def _pe_points(pe: float, reference: float, per_doubling: float, cap: float) -> float:
    """Points for a P/E against a reference: minus `per_doubling` each time it doubles."""
    return clamp(-log2(pe / reference) * per_doubling, -cap, cap)


# --- analyst adjustments and news -------------------------------------------------------


def score_pillars(base: dict[str, PillarScore],
                  reports: dict[str, AgentReport]) -> dict[str, PillarScore]:
    """Apply each analyst's verified adjustment, and build the news score from its events."""
    scored = dict(base)
    for key, pillar_score in base.items():
        pillar = pillar_score.pillar
        report = reports.get(pillar.agent)
        if report is None:
            continue
        if pillar == Pillar.NEWS:
            scored[key] = news_score(report)
            continue
        adjustment = next((a for a in report.score_adjustments if a.pillar == pillar), None)
        if adjustment and pillar_score.base is not None:
            points = round(clamp(adjustment.points, -MAX_ANALYST_ADJUSTMENT,
                                 MAX_ANALYST_ADJUSTMENT))
            scored[key] = pillar_score.model_copy(update={
                "score": round(clamp(pillar_score.base + points, 0, 100)),
                "adjustment": points, "adjustment_reason": adjustment.reason,
                "adjustment_evidence": adjustment.evidence_ids})
    return scored


def news_score(report: AgentReport) -> PillarScore:
    unrated = report.status == AgentStatus.ABSTAINED and not report.events
    if report.status in (AgentStatus.SKIPPED, AgentStatus.FAILED) or unrated:
        return PillarScore(pillar=Pillar.NEWS,
                           note=report.error or "the news analyst found too little to rate")
    rules = _Rules(Pillar.NEWS)
    disclosed = False
    for event in report.events:
        headline_only = all(i.startswith("N") for i in event.evidence_ids)
        disclosed |= not headline_only
        points = clamp(event.impact, -2, 2) * NEWS_POINTS[event.materiality]
        rules.add(event.event + (" (headline only)" if headline_only else ""),
                  points * (HEADLINE_ONLY if headline_only else 1), *event.evidence_ids)
    note = None if report.events else "no material events in the disclosures or headlines"
    return rules.result(Confidence.MEDIUM if disclosed else Confidence.LOW, note,
                        max_swing=NEWS_MAX_SWING)


# --- horizons -----------------------------------------------------------------------------


def build_scorecard(pack: EvidencePack, pillars: dict[str, PillarScore], vetoes: list[Veto],
                    notes: Iterable[HorizonNote] = (), *,
                    model_adjusted: bool = True) -> Scorecard:
    by_horizon: dict[Horizon, HorizonNote] = {}
    for note in notes:
        by_horizon.setdefault(note.horizon, note)
    blocked = any(v.severity == "block" for v in vetoes)
    caps = [v.code for v in vetoes if v.severity == "cap"]
    views = [_horizon_view(pack, horizon, weights, pillars, by_horizon.get(horizon), blocked,
                           caps) for horizon, weights in WEIGHTS.items()]
    return Scorecard(version=VERSION, pillars=[pillars[p.value] for p in Pillar],
                     horizons=views, model_adjusted=model_adjusted, levels=build_levels(pack))


def _horizon_view(pack: EvidencePack, horizon: Horizon, weights: dict[Pillar, int],
                  pillars: dict[str, PillarScore], note: HorizonNote | None, blocked: bool,
                  caps: list[str]) -> HorizonView:
    scores = {p: s for p in weights if (s := pillars[p.value].score) is not None}
    covered = sum(weights[p] for p in scores)
    view = HorizonView(
        horizon=horizon, score=None, signal=Signal.INSUFFICIENT_DATA, confidence=Confidence.LOW,
        weights={p.value: w for p, w in weights.items()}, weight_covered=covered,
        price_range=price_range(pack, horizon), drivers=note.drivers if note else [],
        up_if=note.up_if if note else [], down_if=note.down_if if note else [],
    )
    if blocked or covered < MIN_WEIGHT_COVERED:
        return view

    raw = sum(scores[p] * weights[p] for p in scores) / covered
    adjustment = round(clamp(note.adjustment, -MAX_MANAGER_ADJUSTMENT,
                             MAX_MANAGER_ADJUSTMENT)) if note else 0
    score = round(clamp(raw + adjustment, 0, 100))
    capped_by = caps if caps and score > CAP_SCORE else []
    if capped_by:
        score = CAP_SCORE
    level = sum(_LEVELS[pillars[p.value].confidence] * weights[p] for p in scores) / covered
    if covered < 80:
        level -= 1  # a fifth or more of the weight had nothing to score
    confidence = (Confidence.HIGH if level >= 2.5
                  else Confidence.MEDIUM if level >= 1.75 else Confidence.LOW)
    return view.model_copy(update={
        "score": score, "signal": signal_for(score), "confidence": confidence,
        "driven_by": max(scores, key=lambda p: abs(scores[p] - 50) * weights[p]),
        "manager_adjustment": adjustment,
        "manager_reason": (note.adjustment_reason or None) if note and adjustment else None,
        "capped_by": capped_by,
    })
