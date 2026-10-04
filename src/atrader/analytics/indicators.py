"""Deterministic technical indicators. Every function is pure and tested against
fixtures; agents explain these numbers, they never compute them."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window, min_periods=window).mean()


def ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False, min_periods=span).mean()


def _wilder_smooth(values: np.ndarray, period: int) -> np.ndarray:
    """Wilder smoothing seeded with the simple mean of the first `period` values."""
    out = np.full(len(values), np.nan)
    if len(values) < period:
        return out
    out[period - 1] = values[:period].mean()
    for i in range(period, len(values)):
        out[i] = (out[i - 1] * (period - 1) + values[i]) / period
    return out


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI. A series with no losses in the window reads 100."""
    delta = close.diff().to_numpy()[1:]
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)
    avg_gain = _wilder_smooth(gains, period)
    avg_loss = _wilder_smooth(losses, period)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        values = 100 - 100 / (1 + rs)
    values = np.where((avg_loss == 0) & ~np.isnan(avg_gain), 100.0, values)
    return pd.Series(np.concatenate([[np.nan], values]), index=close.index)


def macd(close: pd.Series, fast: int = 12, slow: int = 26,
         signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    line = ema(close, fast) - ema(close, slow)
    signal_line = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return line, signal_line, line - signal_line


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    true_range.iloc[0] = high.iloc[0] - low.iloc[0]
    return pd.Series(_wilder_smooth(true_range.to_numpy(), period), index=close.index)


def annualised_volatility(close: pd.Series, window: int = 20) -> float | None:
    ratio = (close / close.shift(1)).to_numpy(dtype=float)
    log_returns = pd.Series(np.log(ratio), index=close.index).dropna()
    if len(log_returns) < window:
        return None
    return float(log_returns.iloc[-window:].std(ddof=1) * math.sqrt(252))


def period_return(close: pd.Series, sessions: int) -> float | None:
    if len(close) <= sessions:
        return None
    return float(close.iloc[-1] / close.iloc[-1 - sessions] - 1)


def last(series: pd.Series) -> float | None:
    value = series.iloc[-1] if len(series) else float("nan")
    return None if pd.isna(value) else float(value)
