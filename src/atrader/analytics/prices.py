"""Price-series preparation: corporate-action adjustment and quality checks.

NSE bhavcopy prices are unadjusted. On the first session after a split or bonus,
the exchange publishes an adjusted previous close, so the ratio between that value
and the prior session's actual close reveals the adjustment factor. Earlier bars are
multiplied by that factor (volumes divided). Inferred factors are reported, never
silently applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import pairwise

import pandas as pd

from atrader.contracts import PriceBar

_ADJUSTMENT_TOLERANCE = 0.02  # ignore tick-level rounding in the published prev close


@dataclass(frozen=True)
class AdjustmentEvent:
    session: date
    factor: float  # multiply earlier prices by this


def split_bonus_adjust(bars: list[PriceBar]) -> tuple[list[PriceBar], list[AdjustmentEvent]]:
    if len(bars) < 2:
        return list(bars), []
    events: list[AdjustmentEvent] = []
    for previous, current in pairwise(bars):
        if current.prev_close is None or previous.close <= 0:
            continue
        ratio = current.prev_close / previous.close
        if abs(ratio - 1) > _ADJUSTMENT_TOLERANCE:
            events.append(AdjustmentEvent(current.session, ratio))
    if not events:
        return list(bars), []

    adjusted: list[PriceBar] = []
    for bar in bars:
        factor = 1.0
        for event in events:
            if bar.session < event.session:
                factor *= event.factor
        if factor == 1.0:
            adjusted.append(bar)
            continue
        adjusted.append(bar.model_copy(update={
            "open": bar.open * factor,
            "high": bar.high * factor,
            "low": bar.low * factor,
            "close": bar.close * factor,
            "prev_close": bar.prev_close * factor if bar.prev_close else None,
            "volume": round(bar.volume / factor),
            "adjustment": "split_bonus_adjusted",
        }))
    return adjusted, events


def bars_frame(bars: list[PriceBar]) -> pd.DataFrame:
    frame = pd.DataFrame(
        [{"session": b.session, "open": b.open, "high": b.high, "low": b.low,
          "close": b.close, "volume": b.volume, "turnover": b.turnover_inr} for b in bars]
    )
    if frame.empty:
        return frame
    return frame.set_index("session").sort_index()
