"""Turn adjusted bars into technical, liquidity and market-context metrics."""

from __future__ import annotations

from datetime import date
from typing import Literal

import pandas as pd

from atrader.analytics import indicators as ind
from atrader.analytics.prices import bars_frame
from atrader.contracts import DerivedMetric, PriceBar

_PROVIDER = "nse.bhavcopy"
PRICE = "INR/share"  # price levels are per share, never crore
Category = Literal["fundamental", "valuation", "technical", "liquidity", "pattern", "market"]


def technical_metrics(
    bars: list[PriceBar],
    benchmark: list[tuple[date, float]] | None = None,
    benchmark_name: str = "Nifty 50",
) -> list[DerivedMetric]:
    frame = bars_frame(bars)
    if frame.empty:
        return []
    close, as_of = frame["close"], frame.index[-1]
    basis = bars[-1].adjustment
    out: list[DerivedMetric] = []

    def add(name: str, label: str, value: float | None, unit: str, formula: str,
            category: Category = "technical", detail: str | None = None) -> None:
        out.append(DerivedMetric(
            name=name, label=label, value=None if value is None else round(value, 4),
            unit=unit, as_of=as_of, formula=formula, inputs=(f"{_PROVIDER} ({basis})",),
            category=category, detail=detail,
        ))

    add("close", "Last close", ind.last(close), PRICE, "close of last session")
    for window in (20, 50, 200):
        value = ind.last(ind.sma(close, window))
        add(f"sma{window}", f"{window}-session simple moving average", value, PRICE,
            f"mean(close, {window})")
        if value:
            add(f"close_vs_sma{window}", f"Close vs {window}-session average",
                (close.iloc[-1] / value - 1) * 100, "%", f"close / sma{window} - 1")
    add("rsi14", "RSI (14, Wilder)", ind.last(ind.rsi(close)), "index", "Wilder RSI, 14")
    *_, hist = ind.macd(close)
    add("macd_hist", "MACD histogram (12,26,9)", ind.last(hist), PRICE,
        "ema12 - ema26 - signal9")
    atr_value = ind.last(ind.atr(frame["high"], frame["low"], close))
    add("atr14", "Average true range (14)", atr_value, PRICE, "Wilder ATR, 14")
    if atr_value:
        add("atr14_pct", "ATR as % of close", atr_value / close.iloc[-1] * 100, "%",
            "atr14 / close")
    vol = ind.annualised_volatility(close)
    add("volatility20", "Annualised volatility (20 sessions)",
        None if vol is None else vol * 100, "%", "stdev(log returns, 20) * sqrt(252)")
    for sessions, label in ((21, "1M"), (63, "3M"), (126, "6M"), (252, "12M")):
        value = ind.period_return(close, sessions)
        add(f"return_{label.lower()}", f"Price return {label} ({sessions} sessions)",
            None if value is None else value * 100, "%", f"close / close[-{sessions}] - 1")

    if len(close) >= 240:  # a "52-week" figure needs roughly a year of sessions
        last_year = close.iloc[-252:]
        add("high_52w", "52-week high (closing basis)", float(last_year.max()), PRICE,
            "max(close, 252)")
        add("low_52w", "52-week low (closing basis)", float(last_year.min()), PRICE,
            "min(close, 252)")
        add("from_52w_high", "Distance from 52-week high",
            (close.iloc[-1] / last_year.max() - 1) * 100, "%", "close / high_52w - 1")

    volume = frame["volume"]
    avg_volume = volume.iloc[-21:-1].mean() if len(volume) > 20 else None
    add("volume_ratio", "Last volume / prior 20-session average",
        None if not avg_volume else float(volume.iloc[-1] / avg_volume), "x",
        "volume / mean(volume[-21:-1])")
    turnover = frame["turnover"].dropna()
    median_turnover = float(turnover.iloc[-20:].median()) if len(turnover) >= 5 else None
    add("median_turnover20", "Median daily traded value (20 sessions)", median_turnover, "INR",
        "median(turnover, 20)", category="liquidity")
    add("sessions_available", "Sessions of price history", float(len(close)), "count",
        "count(bars)", category="liquidity")

    if benchmark:
        relative = _relative_strength(close, benchmark, 63)
        if relative is not None:
            add("rel_strength_3m", f"3M price return vs {benchmark_name}", relative, "pp",
                f"stock 63-session return - {benchmark_name} return (price, not total return)",
                category="market")
    return out


def _relative_strength(close: pd.Series, benchmark: list[tuple[date, float]],
                       sessions: int) -> float | None:
    index = pd.Series(dict(benchmark)).sort_index()
    joined = pd.concat([close.rename("stock"), index.rename("index")], axis=1, join="inner")
    if len(joined) <= sessions:
        return None
    window = joined.iloc[-1 - sessions:]
    stock = window["stock"].iloc[-1] / window["stock"].iloc[0] - 1
    bench = window["index"].iloc[-1] / window["index"].iloc[0] - 1
    return float((stock - bench) * 100)
