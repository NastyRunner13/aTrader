"""Versioned, rule-defined chart signals (F16 simple set).

A signal is dated at the session whose close confirms it. More subjective geometries
(double tops, flags) need explicit tolerances and prospective validation first.
"""

from __future__ import annotations

from atrader.analytics import indicators as ind
from atrader.analytics.prices import bars_frame
from atrader.contracts import DerivedMetric, PriceBar

_BREAKOUT_LOOKBACK = 55
_BREAKOUT_VOLUME = 1.5
_UNUSUAL_VOLUME = 2.5


def detect_patterns(bars: list[PriceBar]) -> list[DerivedMetric]:
    frame = bars_frame(bars)
    if len(frame) < 60:
        return []
    close, high, low, volume = frame["close"], frame["high"], frame["low"], frame["volume"]
    as_of = frame.index[-1]
    out: list[DerivedMetric] = []

    sma50, sma200 = ind.last(ind.sma(close, 50)), ind.last(ind.sma(close, 200))
    last_close = float(close.iloc[-1])
    if sma50 is not None and sma200 is not None:
        if last_close > sma50 > sma200:
            state, detail = 1.0, "uptrend: close > SMA50 > SMA200"
        elif last_close < sma50 < sma200:
            state, detail = -1.0, "downtrend: close < SMA50 < SMA200"
        else:
            state, detail = 0.0, "mixed: averages not aligned"
        out.append(DerivedMetric(
            name="ma_trend", label="Moving-average trend state", value=state, unit="signal",
            as_of=as_of, formula="sign of close/SMA50/SMA200 ordering",
            formula_version="ma_trend/1",
            detail=detail, category="pattern",
        ))

    prior_high = high.iloc[-1 - _BREAKOUT_LOOKBACK:-1].max()
    prior_low = low.iloc[-1 - _BREAKOUT_LOOKBACK:-1].min()
    avg_volume = volume.iloc[-21:-1].mean()
    volume_ratio = float(volume.iloc[-1] / avg_volume) if avg_volume else 0.0
    breakout = 0.0
    detail = f"no close beyond the prior {_BREAKOUT_LOOKBACK}-session range"
    if last_close > prior_high and volume_ratio >= _BREAKOUT_VOLUME:
        breakout = 1.0
        detail = (f"close {last_close:.2f} above prior {_BREAKOUT_LOOKBACK}-session high "
                  f"{prior_high:.2f} on {volume_ratio:.1f}x volume; invalidated by a close back "
                  f"below {prior_high:.2f}")
    elif last_close < prior_low and volume_ratio >= _BREAKOUT_VOLUME:
        breakout = -1.0
        detail = (f"close {last_close:.2f} below prior {_BREAKOUT_LOOKBACK}-session low "
                  f"{prior_low:.2f} on {volume_ratio:.1f}x volume; invalidated by a close back "
                  f"above {prior_low:.2f}")
    out.append(DerivedMetric(
        name="range_breakout", label="Confirmed range breakout", value=breakout, unit="signal",
        as_of=as_of, formula=f"close beyond prior {_BREAKOUT_LOOKBACK}-session high/low with "
        f"volume >= {_BREAKOUT_VOLUME}x 20-session average", formula_version="range_breakout/1",
        detail=detail, category="pattern",
    ))

    out.append(DerivedMetric(
        name="unusual_volume", label="Unusual volume", value=1.0 if volume_ratio >=
        _UNUSUAL_VOLUME else 0.0, unit="signal", as_of=as_of,
        formula=f"volume >= {_UNUSUAL_VOLUME}x prior 20-session average",
        formula_version="unusual_volume/1", detail=f"{volume_ratio:.2f}x average",
        category="pattern",
    ))
    return out
