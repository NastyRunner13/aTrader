"""Volume and delivery metrics, price levels, grouped technical rules, sector-relative
valuation and signal-flip prices. All synthetic."""

from __future__ import annotations

import math
from datetime import date, datetime

import pytest

from atrader.analytics.flips import _with_next_session, signal_flips
from atrader.analytics.flows import flow_metrics
from atrader.analytics.levels import (
    anchored_vwap,
    build_levels,
    cluster,
    level_metrics,
    swing_points,
)
from atrader.analytics.prices import bars_frame
from atrader.analytics.scoring import TECHNICAL_GROUPS, base_scores, build_scorecard
from atrader.contracts import Horizon, PriceBar, Signal
from atrader.timeutil import IST, weekdays_back
from tests.conftest import CUTOFF, make_bars, make_facts, make_index, make_pack


def _tape(sessions: int = 120, *, up_volume: int = 3_000_000, down_volume: int = 1_000_000,
          up_delivery: float | None = 70.0, down_delivery: float | None = 30.0
          ) -> list[PriceBar]:
    """Alternating up and down days with different volume and delivery on each side."""
    bars: list[PriceBar] = []
    close = 100.0
    for i, session in enumerate(weekdays_back(CUTOFF, sessions)):
        up = i % 2 == 0
        close *= 1.01 if up else 0.995
        volume = up_volume if up else down_volume
        bars.append(PriceBar(
            session=session, open=close, high=close * 1.01, low=close * 0.99, close=close,
            prev_close=bars[-1].close if bars else None, volume=volume,
            turnover_inr=close * volume, trades=volume // 100,
            delivery_pct=up_delivery if up else down_delivery))
    return bars


# --- volume and delivery ---------------------------------------------------------------------


def test_flows_read_volume_and_delivery_by_side():
    metrics = {m.name: m for m in flow_metrics(_tape())}
    # 10 up days at 3m shares, 10 down days at 1m
    assert metrics["updown_volume20"].value == pytest.approx(3.0)
    # delivered: 3m x 70% on up days vs 1m x 30% on down days
    assert metrics["delivery_updown20"].value == pytest.approx(7.0)
    assert metrics["delivery_pct20"].value == pytest.approx((2.1 + 0.3) / 4 * 100)
    assert metrics["delivery_pct_change"].value == pytest.approx(0.0)  # same pattern before
    assert metrics["volume_ema_ratio"].value == pytest.approx(1.0, abs=0.1)
    assert all(m.category in ("flow", "liquidity") for m in metrics.values())


def test_flows_skip_delivery_when_it_is_missing():
    names = {m.name for m in flow_metrics(_tape(up_delivery=None, down_delivery=None))}
    assert "updown_volume20" in names
    assert not {"delivery_pct20", "delivery_updown20", "delivery_pct_change"} & names


def test_distribution_lowers_the_technical_score_through_flows_only():
    accumulation = base_scores(make_pack(bars=_tape()))["technical"]
    distribution = base_scores(make_pack(bars=_tape(up_volume=1_000_000, down_volume=3_000_000,
                                                    up_delivery=30, down_delivery=70)))
    flows = [f for f in distribution["technical"].factors if f.group == "flows"]
    assert sum(f.points for f in flows) == pytest.approx(-9.0)  # -5 delivery, -4 volume
    assert accumulation.score is not None and distribution["technical"].score is not None
    assert accumulation.score - distribution["technical"].score == pytest.approx(18, abs=1)


# --- grouped technical rules -----------------------------------------------------------------


def test_each_technical_group_stays_within_its_cap():
    falling = base_scores(make_pack(bars=make_bars(drift=-0.004)))["technical"]
    for group, cap in TECHNICAL_GROUPS.items():
        total = sum(f.points for f in falling.factors if f.group == group)
        assert abs(total) <= cap + 1e-9, group
    caps = [f for f in falling.factors if f.kind == "cap"]
    assert caps and all(f.evidence_ids for f in caps)
    assert falling.score == round(50 + sum(f.points for f in falling.factors))


# --- sector-relative valuation and strength --------------------------------------------------


def test_valuation_compares_with_the_sector_first():
    sector = make_index("Nifty Capital Goods", "sector", pe=40.0, drift=0.002)
    market = make_index(pe=20.0)
    pack = make_pack(indices=(market, sector))
    pe = next(m.value for m in pack.metrics if m.name == "pe_ttm")
    assert pe is not None
    valuation = base_scores(pack)["valuation"]
    labels = [f.label for f in valuation.factors]
    assert any("vs Nifty Capital Goods 40.0x" in label for label in labels)
    assert any("vs Nifty 50 20.0x (market context)" in label for label in labels)
    vs_sector = next(f for f in valuation.factors if "Capital Goods" in f.label)
    assert vs_sector.points == pytest.approx(
        round(max(-15, min(15, -math.log2(pe / 40.0) * 12)), 1))
    assert "Nifty Capital Goods" in (valuation.note or "")

    technical = base_scores(pack)["technical"]
    assert any("vs Nifty Capital Goods over 3 months" in f.label for f in technical.factors)


def test_valuation_without_a_sector_uses_the_market_at_full_weight():
    valuation = base_scores(make_pack(indices=(make_index(pe=20.0),)))["valuation"]
    market = next(f for f in valuation.factors if "Nifty 50" in f.label)
    assert "market context" not in market.label
    assert "market only" in (valuation.note or "")


# --- price levels ----------------------------------------------------------------------------


def _wave(sessions: int = 260) -> list[PriceBar]:
    """A price swinging between about 90 and 110 on a 40-session cycle."""
    bars: list[PriceBar] = []
    for i, session in enumerate(weekdays_back(CUTOFF, sessions)):
        close = 100 + 10 * math.sin(2 * math.pi * i / 40)
        bars.append(PriceBar(
            session=session, open=close, high=close + 1, low=close - 1, close=close,
            prev_close=bars[-1].close if bars else None, volume=1_000_000,
            turnover_inr=close * 1_000_000, trades=10_000))
    return bars


def test_swing_points_cluster_into_zones():
    frame = bars_frame(_wave())
    points = swing_points(frame)
    highs = [p for _, p in points if p > 105]
    assert len(highs) >= 5 and all(p == pytest.approx(111, abs=0.2) for p in highs)
    zones = cluster(points, tolerance=1.0)
    assert len(zones) == 2  # every peak in one zone, every trough in another
    assert {round(z.mid) for z in zones} == {89, 111}
    assert all(z.touches >= 5 for z in zones)


def test_level_metrics_put_support_below_and_resistance_above():
    bars = _wave()
    metrics = {m.name: m for m in level_metrics(bars, make_facts())}
    close = bars[-1].close
    assert metrics["support_1"].value < close < metrics["resistance_1"].value
    assert metrics["support_break"].value < metrics["support_1"].value
    assert "swing points" in (metrics["support_1"].detail or "")
    assert metrics["volume_node"].category == "level"
    assert {"avwap_results", "avwap_52w_high", "avwap_52w_low"} <= set(metrics)


def test_anchored_vwap_starts_at_the_first_tradable_session():
    bars = make_bars()
    frame = bars_frame(bars)
    anchor = date(2026, 9, 1)
    expected = (frame.loc[anchor:, "turnover"].sum() / frame.loc[anchor:, "volume"].sum())
    assert anchored_vwap(frame, anchor) == pytest.approx(expected)

    facts = make_facts()
    after_close = [f.model_copy(update={"filed_at": datetime(2026, 9, 1, 18, 0, tzinfo=IST)})
                   for f in facts]
    during = [f.model_copy(update={"filed_at": datetime(2026, 9, 1, 11, 0, tzinfo=IST)})
              for f in facts]
    late = {m.name: m for m in level_metrics(bars, after_close)}["avwap_results"]
    early = {m.name: m for m in level_metrics(bars, during)}["avwap_results"]
    assert "since 2026-09-02" in (late.detail or "")  # filed after the close: next session
    assert "since 2026-09-01" in (early.detail or "")


def test_card_levels_are_sorted_and_cite_metrics():
    pack = make_pack(bars=_wave())
    levels = build_levels(pack)
    assert levels is not None
    prices = [level.price for level in levels.levels]
    assert prices == sorted(prices, reverse=True)
    ids = pack.evidence_ids()
    assert all(level.evidence_id in ids for level in levels.levels)
    assert levels.support_break is not None and levels.support_break.price < levels.close


# --- signal flips ----------------------------------------------------------------------------


def test_signal_flips_land_where_the_signal_changes():
    pack = make_pack(bars=make_bars(drift=-0.0005))
    card = build_scorecard(pack, base_scores(pack), [])
    flips = signal_flips(pack, card, {}, [])
    found = [f for f in flips if f.price is not None]
    assert found
    close = pack.bars[-1].close
    for flip in found:
        assert (flip.price > close) == (flip.direction == "up")
        trial = _with_next_session(pack, flip.price)
        trial_card = build_scorecard(trial, base_scores(trial), [])
        assert trial_card.horizon(flip.horizon).signal == flip.signal
        assert flip.signal != card.horizon(flip.horizon).signal


def test_no_flip_search_beyond_the_end_of_the_scale():
    pack = make_pack()
    card = build_scorecard(pack, base_scores(pack), [])
    month = card.horizon(Horizon.ONE_MONTH).model_copy(
        update={"signal": Signal.STRONG_BULLISH})
    card = card.model_copy(update={"horizons": [month, *card.horizons[1:]]})
    flips = signal_flips(pack, card, {}, [])
    assert [f.direction for f in flips if f.horizon == Horizon.ONE_MONTH] == ["down"]
