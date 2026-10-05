"""Indicators, price adjustment, fundamentals and vetoes."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from atrader.analytics import indicators as ind
from atrader.analytics.fundamentals import fundamental_metrics
from atrader.analytics.prices import split_bonus_adjust
from atrader.analytics.technicals import technical_metrics
from atrader.analytics.vetoes import compute_vetoes
from atrader.contracts import PriceBar
from tests.conftest import make_bars, make_facts, make_pack


def test_rsi_is_100_without_losses_and_50_when_balanced():
    rising = pd.Series([float(i) for i in range(1, 40)])
    assert ind.last(ind.rsi(rising)) == pytest.approx(100.0)
    zigzag = pd.Series([100.0 + (1 if i % 2 else -1) for i in range(60)])
    assert ind.last(ind.rsi(zigzag)) == pytest.approx(50.0, abs=2)


def test_sma_and_period_return():
    close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert ind.last(ind.sma(close, 3)) == 4.0
    assert ind.period_return(close, 4) == pytest.approx(4.0)
    assert ind.period_return(close, 5) is None


def test_atr_of_constant_range_equals_range():
    n = 30
    high = pd.Series([11.0] * n)
    low = pd.Series([9.0] * n)
    close = pd.Series([10.0] * n)
    assert ind.last(ind.atr(high, low, close)) == pytest.approx(2.0)


def test_split_is_detected_from_exchange_prev_close():
    def bar(day, close, prev):
        return PriceBar(session=date(2026, 1, day), open=close, high=close, low=close,
                        close=close, prev_close=prev, volume=1000)

    bars = [bar(5, 1000, None), bar(6, 1010, 1000), bar(7, 510, 505), bar(8, 520, 510)]
    adjusted, events = split_bonus_adjust(bars)
    assert len(events) == 1 and events[0].session == date(2026, 1, 7)
    assert events[0].factor == pytest.approx(0.5)
    assert adjusted[0].close == pytest.approx(500) and adjusted[0].volume == 2000
    assert adjusted[0].adjustment == "split_bonus_adjusted"
    assert adjusted[2].close == 510 and adjusted[2].adjustment == "unadjusted"


def test_fundamental_metrics_cite_their_inputs():
    facts = make_facts()
    metrics = {m.name: m for m in fundamental_metrics(facts, 300.0, date(2026, 9, 30))}
    assert metrics["revenue_yoy"].value == pytest.approx(20.0)  # 1200 vs 1000
    assert metrics["revenue_qoq"].value == pytest.approx(1.69, abs=0.01)
    assert metrics["pe_ttm"].value == pytest.approx(300 / (5.9 + 6.25 + 6.8 + 7.5), abs=0.01)
    fact_ids = {f.evidence_id for f in facts}
    assert set(metrics["revenue_yoy"].inputs) <= fact_ids
    assert "M:close" in metrics["pe_ttm"].inputs  # resolved to a real ID by the builder
    # PBT margin 200/1200 now vs 150/1000 a year ago: 16.67% - 15% = +1.67 pp
    assert metrics["pbt_margin_change_yoy"].value == pytest.approx(1.67, abs=0.01)
    assert metrics["pbt_margin_change_yoy"].unit == "pp"


def test_pack_metric_placeholders_resolve_to_ids():
    pack = make_pack()
    pe = next(m for m in pack.metrics if m.name == "pe_ttm")
    close = next(m for m in pack.metrics if m.name == "close")
    assert close.evidence_id in pe.inputs and "M:close" not in pe.inputs


def test_vetoes_block_and_cap():
    empty = make_pack(bars=[], facts=[])
    assert [(v.code, v.severity) for v in compute_vetoes(empty)] == [
        ("no_core_evidence", "block")]
    short = make_pack(bars=make_bars(sessions=40))
    assert ("short_price_history", "cap") in {(v.code, v.severity)
                                               for v in compute_vetoes(short)}


def test_healthy_pack_has_no_capping_vetoes():
    vetoes = compute_vetoes(make_pack())
    assert not [v for v in vetoes if v.severity != "note"], vetoes


def test_price_levels_are_per_share_and_52w_needs_a_year():
    short = {m.name: m for m in technical_metrics(make_bars(sessions=60))}
    assert short["close"].unit == "INR/share" and short["sma20"].unit == "INR/share"
    assert "high_52w" not in short and "from_52w_high" not in short
    full = {m.name: m for m in technical_metrics(make_bars(sessions=260))}
    assert "high_52w" in full
    assert "volatility_1y" not in short and full["volatility_1y"].label.endswith("(250 sessions)")
