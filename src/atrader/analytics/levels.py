"""Price levels: where the stock turned before and where its volume traded.

Support and resistance zones come from confirmed swing points. A swing high is the
highest high of the 10 sessions on either side, so a swing is only known 10 sessions
after it happens. Swing points closer than half an ATR merge into one zone; a zone
below the last close is support, one above is resistance. Anchored VWAPs are the
volume-weighted average price paid since an event, from NSE's daily traded value and
volume. The volume node is the price band where the most shares traded over six
months, placing each day's volume at that day's average price.

These describe the past. They are not forecasts, entries, stops or targets.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from math import floor
from typing import cast

import pandas as pd

from atrader.analytics import indicators as ind
from atrader.analytics.prices import bars_frame
from atrader.contracts import (
    DerivedMetric,
    EvidencePack,
    FinancialFact,
    Level,
    PriceBar,
    PriceLevels,
)
from atrader.formatting import rupees
from atrader.timeutil import IST

SWING = 10  # sessions on each side of a swing point
LOOKBACK = 250  # sessions searched for swing points
ZONE_ATR = 0.5  # swing points closer than this many ATRs form one zone
ZONES_PER_SIDE = 2
NODE_SESSIONS = 126
MIN_SESSIONS = 60
_MARKET_CLOSE = time(15, 30)
_PRICE = "INR/share"
_PROVIDER = "nse.bhavcopy"


@dataclass(frozen=True)
class Zone:
    low: float
    high: float
    mid: float
    touches: int
    last: date

    def describe(self) -> str:
        span = (rupees(self.low) if round(self.low) == round(self.high)
                else f"{rupees(self.low)}–{rupees(self.high)[1:]}")
        points = "1 swing point" if self.touches == 1 else f"{self.touches} swing points"
        return f"zone {span}; {points}, latest {self.last}"


def level_metrics(bars: Sequence[PriceBar], facts: Sequence[FinancialFact] = ()
                  ) -> list[DerivedMetric]:
    frame = bars_frame(list(bars))
    if len(frame) < MIN_SESSIONS:
        return []
    atr = ind.last(ind.atr(frame["high"], frame["low"], frame["close"]))
    if not atr:
        return []
    close, as_of = float(frame["close"].iloc[-1]), frame.index[-1]
    basis = f"{_PROVIDER} ({bars[-1].adjustment})"
    out: list[DerivedMetric] = []

    def add(name: str, label: str, value: float, formula: str, detail: str,
            inputs: tuple[str, ...] = ()) -> None:
        out.append(DerivedMetric(
            name=name, label=label, value=round(value, 2), unit=_PRICE, as_of=as_of,
            formula=formula, inputs=(basis, *inputs), category="level", detail=detail,
        ))

    zones = cluster(swing_points(frame.iloc[-LOOKBACK:]), ZONE_ATR * atr)
    zone_formula = (f"mean of swing highs/lows within {ZONE_ATR} ATR, last {LOOKBACK} "
                    f"sessions (swing = extreme of {SWING} sessions either side)")
    for side, label in (("support", "Support zone"), ("resistance", "Resistance zone")):
        for i, zone in enumerate(nearest_zones(zones, close, side), start=1):
            add(f"{side}_{i}", f"{label} {i} ({'nearest' if i == 1 else 'next'})", zone.mid,
                zone_formula, zone.describe(), ("M:atr14",))
            if side == "support" and i == 1:
                add("support_break", "Close that breaks the nearest support", zone.low - atr,
                    "nearest support zone low - atr14",
                    f"zone low {rupees(zone.low)} less one ATR ({rupees(atr)})",
                    ("M:support_1", "M:atr14"))

    for name, label, anchor, why in _anchors(frame, facts):
        value = anchored_vwap(frame, anchor)
        if value is not None:
            sessions = int((frame.index >= anchor).sum())
            add(name, label, value, "sum(traded value) / sum(volume) since the anchor session",
                f"since {anchor} ({why}), {sessions} sessions")

    node = volume_node(frame.iloc[-NODE_SESSIONS:], atr)
    if node is not None:
        low, high, share = node
        add("volume_node", f"Heaviest-traded price band ({NODE_SESSIONS} sessions)",
            (low + high) / 2, f"daily average price binned by ATR14; the band with the most "
            f"volume over {NODE_SESSIONS} sessions",
            f"{rupees(low)}–{rupees(high)[1:]}: {share:.0%} of the period's volume",
            ("M:atr14",))
    return out


# --- zones ----------------------------------------------------------------------------------


def swing_points(frame: pd.DataFrame, window: int = SWING) -> list[tuple[date, float]]:
    """Confirmed swing highs and lows as (session, price). A run of equal highs or lows
    counts once."""
    span = 2 * window + 1
    highs = frame["high"].rolling(span, center=True).max()
    lows = frame["low"].rolling(span, center=True).min()
    points: list[tuple[date, float]] = []
    sessions = _sessions(frame)
    for column, extreme in (("high", highs), ("low", lows)):
        last_position = -span
        for position, price in enumerate(frame[column].tolist()):
            if price == extreme.iloc[position] and position - last_position > window:
                points.append((sessions[position], float(price)))
                last_position = position
    return points


def cluster(points: Sequence[tuple[date, float]], tolerance: float) -> list[Zone]:
    """Merge points within `tolerance` of the zone's running mean, scanning by price."""
    zones: list[list[tuple[date, float]]] = []
    for point in sorted(points, key=lambda p: p[1]):
        if zones:
            members = zones[-1]
            mean = sum(p for _, p in members) / len(members)
            if point[1] - mean <= tolerance:
                members.append(point)
                continue
        zones.append([point])
    return [Zone(low=min(p for _, p in z), high=max(p for _, p in z),
                 mid=sum(p for _, p in z) / len(z), touches=len(z), last=max(d for d, _ in z))
            for z in zones]


def nearest_zones(zones: Sequence[Zone], close: float, side: str) -> list[Zone]:
    """The nearest zones on one side, preferring ones price turned at more than once."""
    candidates = sorted((z for z in zones if (z.mid < close if side == "support"
                                              else z.mid > close)),
                        key=lambda z: abs(z.mid - close))
    strong = [z for z in candidates if z.touches >= 2][:ZONES_PER_SIDE]
    weak = [z for z in candidates if z.touches < 2][:ZONES_PER_SIDE - len(strong)]
    return sorted(strong + weak, key=lambda z: abs(z.mid - close))


# --- volume-weighted levels -----------------------------------------------------------------


def anchored_vwap(frame: pd.DataFrame, anchor: date) -> float | None:
    rows = frame[frame.index >= anchor]
    rows = rows[rows["turnover"].notna() & (rows["volume"] > 0)]
    if rows.empty:
        return None
    return float(rows["turnover"].sum() / rows["volume"].sum())


def volume_node(frame: pd.DataFrame, width: float) -> tuple[float, float, float] | None:
    """(low, high, share of volume) of the ATR-wide price band with the most volume."""
    rows = frame[frame["turnover"].notna() & (frame["volume"] > 0)]
    if len(rows) < MIN_SESSIONS or width <= 0:
        return None
    price = rows["turnover"] / rows["volume"]
    bands = (price / width).map(floor)
    by_band = rows["volume"].groupby(bands).sum()
    band = int(by_band.index.tolist()[int(by_band.to_numpy().argmax())])
    return band * width, (band + 1) * width, float(by_band.max() / by_band.sum())


def _anchors(frame: pd.DataFrame, facts: Sequence[FinancialFact]
             ) -> list[tuple[str, str, date, str]]:
    anchors: list[tuple[str, str, date, str]] = []
    filed = max((f.filed_at for f in facts if f.duration == "quarter"), default=None)
    if filed is not None:
        session = _first_session_after(frame, filed)
        if session is not None:
            anchors.append(("avwap_results", "VWAP since the latest results", session,
                            f"results filed {filed.astimezone(IST):%Y-%m-%d %H:%M} IST"))
    if len(frame) >= 240:
        year = frame.iloc[-252:]
        closes, sessions = year["close"].to_numpy(), _sessions(year)
        anchors.append(("avwap_52w_high", "VWAP since the 52-week high",
                        sessions[int(closes.argmax())], "the highest close of the year"))
        anchors.append(("avwap_52w_low", "VWAP since the 52-week low",
                        sessions[int(closes.argmin())], "the lowest close of the year"))
    return anchors


def _sessions(frame: pd.DataFrame) -> list[date]:
    return [cast(date, session) for session in frame.index.tolist()]


def _first_session_after(frame: pd.DataFrame, filed: datetime) -> date | None:
    """The first session that could trade on a filing: the same day if it was filed
    before the close, otherwise the next session."""
    local = filed.astimezone(IST)
    day = local.date()
    sessions = frame.index[frame.index >= day] if local.time() < _MARKET_CLOSE \
        else frame.index[frame.index > day]
    return sessions[0] if len(sessions) else None


# --- the card's view ------------------------------------------------------------------------

# (metric, kind, card label). The card shows these when they exist; the details file
# lists every level metric.
CARD_LEVELS = (
    ("resistance_2", "resistance", "Resistance"),
    ("resistance_1", "resistance", "Resistance (nearest)"),
    ("support_1", "support", "Support (nearest)"),
    ("support_2", "support", "Support"),
    ("sma50", "average", "50-day average"),
    ("sma200", "average", "200-day average"),
    ("avwap_results", "vwap", "VWAP since results"),
    ("avwap_52w_high", "vwap", "VWAP since 52-week high"),
    ("volume_node", "volume", "Heaviest-traded band (6M)"),
    ("high_52w", "range", "52-week high"),
    ("low_52w", "range", "52-week low"),
)


def build_levels(pack: EvidencePack) -> PriceLevels | None:
    metrics = {m.name: m for m in pack.metrics if m.value is not None}
    close = metrics.get("close")
    if close is None or close.value is None:
        return None
    levels = [
        Level(kind=kind, label=label, price=m.value, detail=m.detail or "",
              evidence_id=m.evidence_id)
        for name, kind, label in CARD_LEVELS
        if (m := metrics.get(name)) is not None and m.value is not None
    ]
    levels.sort(key=lambda level: -level.price)
    brk = metrics.get("support_break")
    support_break = Level(kind="support", label="Support break", price=brk.value,
                          detail=brk.detail or "", evidence_id=brk.evidence_id) \
        if brk is not None and brk.value is not None else None
    return PriceLevels(close=close.value, as_of=close.as_of, levels=levels,
                       support_break=support_break)
