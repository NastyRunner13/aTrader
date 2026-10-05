"""Company search, price history for charts, and last-close quotes, all from local data."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import date
from typing import Any

import pandas as pd

from atrader.analytics.indicators import sma
from atrader.analytics.prices import bars_frame, split_bonus_adjust
from atrader.config import Settings
from atrader.contracts import Listing
from atrader.data.http import PoliteClient
from atrader.data.providers.nse_instruments import InstrumentMaster
from atrader.data.store import MarketStore

AVERAGES = (20, 50, 200)
MAX_SESSIONS = 1300  # about five years


class Market:
    def __init__(self, settings: Settings,
                 load_master: Callable[[], InstrumentMaster] | None = None) -> None:
        self._settings = settings
        self._store = MarketStore(settings.db_path)
        self._load_master = load_master or self._download_master
        self._master: InstrumentMaster | None = None
        self._lock = threading.Lock()

    @property
    def latest_session(self) -> date | None:
        return self._store.latest_session()

    def master(self) -> InstrumentMaster:
        """The NSE equity list, fetched on first use (and cached on disk for a week)."""
        with self._lock:
            if self._master is None:
                self._master = self._load_master()
            return self._master

    def search(self, query: str, limit: int = 10) -> list[Listing]:
        return self.master().search(query, limit) if query.strip() else []

    def resolve(self, symbol: str) -> Listing:
        return self.master().resolve(symbol)

    def bars(self, symbol: str, sessions: int, until: date | None) -> dict[str, Any]:
        """Split-adjusted daily bars with moving averages computed over earlier history,
        so the 200-session average is already drawn on the first visible bar."""
        listing = self.resolve(symbol)
        sessions = min(max(sessions, 20), MAX_SESSIONS)
        raw = self._store.bars_for(listing.isin, until or date.max, sessions + max(AVERAGES))
        bars, events = split_bonus_adjust(raw)
        frame = bars_frame(bars)
        averages = {f"sma{window}": sma(frame["close"], window) for window in AVERAGES} \
            if not frame.empty else {}
        visible = frame.tail(sessions)
        return {
            "symbol": listing.symbol, "name": listing.name, "isin": listing.isin,
            "adjusted": bool(events),
            "adjustments": [{"session": e.session.isoformat(), "factor": e.factor}
                            for e in events],
            "bars": [
                {"session": str(session), "open": round(row.open, 2),
                 "high": round(row.high, 2), "low": round(row.low, 2),
                 "close": round(row.close, 2), "volume": int(row.volume),
                 "delivery_pct": _number(row.delivery_pct)}
                for session, row in visible.iterrows()],
            "averages": {name: [_number(series.get(session)) for session in visible.index]
                         for name, series in averages.items()},
        }

    def quote(self, isin: str) -> dict[str, Any] | None:
        """Last close and the change from the session before, or None without prices.
        Reads local data only, so a watchlist loads without the NSE list."""
        bars, _ = split_bonus_adjust(self._store.bars_for(isin, date.max, 2))
        if not bars:
            return None
        last = bars[-1]
        previous = bars[-2].close if len(bars) > 1 else last.prev_close
        change = (last.close / previous - 1) * 100 if previous else None
        return {"close": round(last.close, 2), "session": last.session.isoformat(),
                "change_pct": round(change, 2) if change is not None else None}

    def _download_master(self) -> InstrumentMaster:
        with PoliteClient(self._settings.cache_dir, self._settings.http_min_interval_s) as client:
            return InstrumentMaster.load(client)


def _number(value: object) -> float | None:
    if value is None or pd.isna(value):  # type: ignore[call-overload]
        return None
    return round(float(value), 2)  # type: ignore[arg-type]
