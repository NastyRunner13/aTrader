"""The scorecard: rule scores, weights, missing data, vetoes, signals and price ranges."""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from atrader.analytics.ranges import price_range
from atrader.analytics.scoring import (
    CAP_SCORE,
    WEIGHTS,
    base_scores,
    build_scorecard,
    news_score,
    signal_for,
)
from atrader.contracts import (
    AgentReport,
    AgentStatus,
    Confidence,
    EventRating,
    Horizon,
    HorizonNote,
    Pillar,
    PillarScore,
    Signal,
    Veto,
)
from atrader.verification import verify_events
from tests.conftest import make_bars, make_facts, make_pack


def _pillars(**scores: int | None) -> dict[str, PillarScore]:
    return {p.value: PillarScore(pillar=p, score=scores.get(p.value), base=scores.get(p.value),
                                 confidence=Confidence.MEDIUM) for p in Pillar}


def test_weights_cover_every_area_and_sum_to_100():
    for weights in WEIGHTS.values():
        assert set(weights) == set(Pillar) and sum(weights.values()) == 100
    # short horizons lean on price action, long ones on the business
    assert WEIGHTS[Horizon.ONE_MONTH][Pillar.TECHNICAL] > WEIGHTS[Horizon.TWO_YEARS][
        Pillar.TECHNICAL]
    assert WEIGHTS[Horizon.TWO_YEARS][Pillar.GROWTH_QUALITY] > WEIGHTS[Horizon.ONE_MONTH][
        Pillar.GROWTH_QUALITY]


@pytest.mark.parametrize(("score", "signal"), [
    (0, Signal.STRONG_BEARISH), (29, Signal.STRONG_BEARISH), (30, Signal.BEARISH),
    (44, Signal.BEARISH), (45, Signal.NEUTRAL), (55, Signal.NEUTRAL), (56, Signal.BULLISH),
    (70, Signal.BULLISH), (71, Signal.STRONG_BULLISH), (100, Signal.STRONG_BULLISH),
    (None, Signal.INSUFFICIENT_DATA)])
def test_signal_bands(score, signal):
    assert signal_for(score) == signal


def test_technical_score_follows_the_trend_and_cites_evidence():
    rising = base_scores(make_pack(bars=make_bars(drift=0.002)))["technical"]
    falling = base_scores(make_pack(bars=make_bars(drift=-0.002)))["technical"]
    assert rising.score is not None and falling.score is not None
    assert rising.score > 60 and falling.score < 40
    assert rising.confidence == Confidence.HIGH  # 260 sessions, fresh
    ids = make_pack().evidence_ids()
    assert all(f.evidence_ids and set(f.evidence_ids) <= ids for f in rising.factors)


def test_short_history_leaves_technical_unscored():
    score = base_scores(make_pack(bars=make_bars(sessions=40)))["technical"]
    assert score.score is None and "60 sessions" in (score.note or "")


def test_growth_and_valuation_from_reported_results():
    scores = base_scores(make_pack())
    growth, valuation = scores["growth_quality"], scores["valuation"]
    # revenue +20% and profit +36% YoY with a wider margin: clearly above par
    assert growth.score is not None and growth.score > 70
    assert {i[0] for f in growth.factors for i in f.evidence_ids} <= {"M", "S", "F"}
    # no Nifty P/E in the synthetic pack: only the P/E-to-growth rule applies
    assert valuation.score is not None and valuation.confidence == Confidence.LOW
    assert scores["news"].score is None  # needs the news analyst


def test_loss_making_company_scores_low_on_valuation():
    facts = [f.model_copy(update={"value": -abs(f.value or Decimal(0))})
             if f.metric.startswith("BasicEarnings") else f for f in make_facts()]
    valuation = base_scores(make_pack(facts=facts))["valuation"]
    assert valuation.score == 25


def test_missing_area_is_left_out_not_counted_as_50():
    card = build_scorecard(make_pack(), _pillars(technical=80, growth_quality=60,
                                                 valuation=40), [])
    month = card.horizon(Horizon.ONE_MONTH)
    assert month.weight_covered == 70  # news (30%) had no score
    assert month.score == round((80 * 45 + 60 * 15 + 40 * 10) / 70)
    assert month.driven_by == Pillar.TECHNICAL


def test_too_little_weight_gives_no_signal():
    card = build_scorecard(make_pack(), _pillars(growth_quality=70, valuation=60), [])
    month = card.horizon(Horizon.ONE_MONTH)  # 25% of the weight scored
    assert month.score is None and month.signal == Signal.INSUFFICIENT_DATA
    assert card.horizon(Horizon.TWO_YEARS).score is not None  # 80% scored


def test_block_withholds_and_cap_holds_at_neutral():
    pillars = _pillars(technical=90, growth_quality=90, valuation=90, news=20)
    block = Veto(code="no_core_evidence", severity="block", message="")
    assert all(h.score is None for h in build_scorecard(make_pack(), pillars, [block]).horizons)

    cap = Veto(code="low_liquidity", severity="cap", message="")
    card = build_scorecard(make_pack(), pillars, [cap])
    two_years = card.horizon(Horizon.TWO_YEARS)  # 80 before the cap
    assert two_years.score == CAP_SCORE and two_years.capped_by == ["low_liquidity"]
    low = build_scorecard(make_pack(), _pillars(technical=20, growth_quality=30,
                                                valuation=30, news=30), [cap])
    assert all(h.capped_by == [] and (h.score or 0) < CAP_SCORE for h in low.horizons)


def test_manager_adjustment_is_clamped_to_five():
    pillars = _pillars(technical=50, growth_quality=50, valuation=50, news=50)
    notes = [HorizonNote(horizon=Horizon.SIX_MONTHS, adjustment=40, adjustment_reason="x",
                         drivers=["d"])]
    card = build_scorecard(make_pack(), pillars, [], notes)
    six = card.horizon(Horizon.SIX_MONTHS)
    assert six.score == 55 and six.manager_adjustment == 5 and six.drivers == ["d"]
    assert card.horizon(Horizon.ONE_MONTH).score == 50


def test_news_score_from_rated_events():
    events = [EventRating(event="Large order", impact=2, materiality="high", evidence_ids=["A1"]),
              EventRating(event="Rumour", impact=-2, materiality="high", evidence_ids=["N1"])]
    report = AgentReport(agent="news_analyst", roles=[], status=AgentStatus.COMPLETED,
                         events=events)
    score = news_score(report)
    assert score.score == 50 + 14 - 7  # the headline-only event counts half
    assert score.confidence == Confidence.MEDIUM
    assert score.factors[1].label.endswith("(headline only)")

    flood = [events[0]] * 8
    assert news_score(report.model_copy(update={"events": flood})).score == 90  # capped ±40
    quiet = news_score(report.model_copy(update={"events": []}))
    assert quiet.score == 50 and quiet.confidence == Confidence.LOW
    skipped = AgentReport(agent="news_analyst", roles=[], status=AgentStatus.SKIPPED,
                          error="no disclosures")
    assert news_score(skipped).score is None


def test_news_events_must_cite_disclosures_or_headlines():
    pack = make_pack()
    events = [EventRating(event="a", impact=5, materiality="low", evidence_ids=["A1"]),
              EventRating(event="b", impact=1, materiality="low", evidence_ids=["F1"]),
              EventRating(event="c", impact=1, materiality="low", evidence_ids=["A99"])]
    kept = verify_events(events, pack)
    assert [(e.event, e.impact) for e in kept] == [("a", 2)]


def test_volatility_range_matches_its_formula():
    pack = make_pack()
    metrics = {m.name: m.value for m in pack.metrics}
    month = price_range(pack, Horizon.ONE_MONTH)
    assert month is not None and month.method == "volatility"
    sigma = metrics["volatility_1y"] / 100 * math.sqrt(21 / 252)
    assert month.low == pytest.approx(metrics["close"] * math.exp(-sigma))
    assert month.high == pytest.approx(metrics["close"] * math.exp(sigma))
    six = price_range(pack, Horizon.SIX_MONTHS)
    assert six is not None and six.high - six.low > month.high - month.low


def test_two_year_scenarios_are_ordered_and_low_confidence():
    pack = make_pack()  # fast growth (revenue +20%, profit +36%): the bear case must still fall
    close = next(m.value for m in pack.metrics if m.name == "close")
    scenario = price_range(pack, Horizon.TWO_YEARS)
    assert scenario is not None and scenario.method == "scenario"
    assert scenario.base is not None and scenario.low < scenario.base < scenario.high
    assert close is not None and scenario.low < close * 0.8 + 1e-9
    assert scenario.confidence == Confidence.LOW
    assert price_range(make_pack(facts=[]), Horizon.TWO_YEARS) is None  # no EPS
