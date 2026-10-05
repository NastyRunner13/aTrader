"""Volume and delivery: how much conviction sits behind the price move.

NSE reports, for every stock and day, how much of the traded quantity was marked for
delivery rather than squared off the same day. Average delivered volume on rising days
against falling days is read as accumulation or distribution; traded volume gives the
same reading without delivery data. The volume EMAs show whether participation is growing,
and the average trade size hints at larger (often institutional) tickets. None of this
says who traded: per-stock FII buying and selling is not published daily.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Literal

import pandas as pd

from atrader.analytics import indicators as ind
from atrader.analytics.prices import bars_frame
from atrader.contracts import DerivedMetric, PriceBar

WINDOW = 20  # sessions read for the current state
BASELINE = 60  # sessions before that, for "is it changing"
MIN_SESSIONS = 15  # of the last 20 with data, or the reading is skipped
MIN_BASELINE = 40  # of the 60 before
MIN_DAYS_PER_SIDE = 3  # up days and down days needed to compare their volume
_PROVIDERS = ("nse.bhavcopy", "nse.delivery_position")


def flow_metrics(bars: Sequence[PriceBar]) -> list[DerivedMetric]:
    frame = bars_frame(list(bars))
    if len(frame) <= WINDOW:
        return []
    as_of = frame.index[-1]
    volume = frame["volume"].astype(float)
    change = frame["close"].diff().iloc[-WINDOW:]
    up, down = change > 0, change < 0
    out: list[DerivedMetric] = []

    ema20, ema50 = ind.last(ind.ema(volume, 20)), ind.last(ind.ema(volume, 50))
    if ema20 and ema50:
        out.append(_metric(
            "volume_ema_ratio", "Volume trend: 20-session EMA / 50-session EMA of volume",
            ema20 / ema50, "x", as_of, "ema(volume, 20) / ema(volume, 50)",
            f"EMA20 {ema20:,.0f} vs EMA50 {ema50:,.0f} shares a day"))

    traded = volume.iloc[-WINDOW:]
    if ratio := _ratio(traded[up], traded[down]):
        out.append(_metric(
            "updown_volume20", f"Average volume, up days / down days ({WINDOW} sessions)",
            ratio, "x", as_of, f"mean(volume, close up) / mean(volume, close down), last "
            f"{WINDOW} sessions", f"{int(up.sum())} up days, {int(down.sum())} down days"))

    out += _delivery(frame, volume, up, down, as_of)
    out += _trade_size(frame, as_of)
    return out


def _delivery(frame: pd.DataFrame, volume: pd.Series, up: pd.Series, down: pd.Series,
              as_of: date) -> list[DerivedMetric]:
    pct = frame["delivery_pct"]
    known = pct.iloc[-WINDOW:].notna()
    if known.sum() < MIN_SESSIONS:
        return []
    delivered = volume * pct / 100
    now_volume, now_delivered = volume.iloc[-WINDOW:], delivered.iloc[-WINDOW:]
    share = float(now_delivered[known].sum() / now_volume[known].sum() * 100)
    out = [_metric(
        "delivery_pct20", f"Delivery share of traded volume ({WINDOW} sessions)", share, "%",
        as_of, f"sum(delivered qty) / sum(traded qty), last {WINDOW} sessions",
        f"{int(known.sum())} of {WINDOW} sessions with delivery data")]

    before = slice(-WINDOW - BASELINE, -WINDOW)
    base_known = pct.iloc[before].notna()
    if base_known.sum() >= MIN_BASELINE:
        base_share = float(delivered.iloc[before][base_known].sum()
                           / volume.iloc[before][base_known].sum() * 100)
        out.append(_metric(
            "delivery_pct_change", f"Delivery share: last {WINDOW} sessions vs the {BASELINE} "
            "before", share - base_share, "pp", as_of,
            f"delivery_pct20 - delivery share of the prior {BASELINE} sessions",
            f"{share:.1f}% now vs {base_share:.1f}% before"))

    if ratio := _ratio(now_delivered[up & known], now_delivered[down & known]):
        out.append(_metric(
            "delivery_updown20", f"Average delivered volume, up days / down days ({WINDOW} "
            "sessions)", ratio, "x", as_of, "mean(delivered qty, close up) / mean(delivered "
            f"qty, close down), last {WINDOW} sessions", f"{int((up & known).sum())} up days, "
            f"{int((down & known).sum())} down days with delivery data"))
    return out


def _trade_size(frame: pd.DataFrame, as_of: date) -> list[DerivedMetric]:
    valid = frame["turnover"].notna() & (frame["trades"] > 0)
    now, before = slice(-WINDOW, None), slice(-WINDOW - BASELINE, -WINDOW)
    if valid.iloc[now].sum() < MIN_SESSIONS or valid.iloc[before].sum() < MIN_BASELINE:
        return []

    def size(window: slice) -> float:
        rows = frame.iloc[window][valid.iloc[window]]
        return float(rows["turnover"].sum() / rows["trades"].sum())

    size_now, size_before = size(now), size(before)
    return [_metric(
        "trade_size_change", f"Average trade size: last {WINDOW} sessions vs the {BASELINE} "
        "before", (size_now / size_before - 1) * 100, "%", as_of,
        "(traded value / number of trades) now vs before",
        f"₹{size_now:,.0f} vs ₹{size_before:,.0f} a trade", category="liquidity")]


def _metric(name: str, label: str, value: float, unit: str, as_of: date, formula: str,
            detail: str, category: Literal["flow", "liquidity"] = "flow") -> DerivedMetric:
    return DerivedMetric(name=name, label=label, value=round(value, 4), unit=unit, as_of=as_of,
                         formula=formula, inputs=_PROVIDERS, category=category, detail=detail)


def _ratio(up_days: pd.Series, down_days: pd.Series) -> float | None:
    """Average volume on up days over average volume on down days. Averages, not sums:
    a falling stock has more down days, and summing would count the fall a second time.
    None with fewer than three days on either side."""
    if len(up_days) < MIN_DAYS_PER_SIDE or len(down_days) < MIN_DAYS_PER_SIDE:
        return None
    up, down = float(up_days.mean()), float(down_days.mean())
    return up / down if up > 0 and down > 0 else None
