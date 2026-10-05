"""Local SQLite store for ingested market data.

Kept deliberately small: end-of-day bars and delivery positions (all NSE equities, so
the screener can reuse them later), index closes, and which sessions were ingested.
Filings, announcements and news are fetched per run through the HTTP cache.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from atrader.contracts import PriceBar

if TYPE_CHECKING:
    from atrader.data.providers.nse_bhavcopy import DeliveryRow

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingested_sessions (
    session     TEXT PRIMARY KEY,           -- ISO date
    dataset     TEXT NOT NULL,              -- 'equity' | 'index'
    status      TEXT NOT NULL,              -- 'ok' | 'no_file'
    source_url  TEXT,
    sha256      TEXT,
    retrieved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS index_sessions (
    session     TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    retrieved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS price_bars (
    symbol      TEXT NOT NULL,
    series      TEXT NOT NULL,
    isin        TEXT,
    session     TEXT NOT NULL,
    open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL,
    prev_close  REAL,
    volume      INTEGER NOT NULL,
    turnover    REAL,
    trades      INTEGER,
    provider    TEXT NOT NULL,
    PRIMARY KEY (symbol, series, session, provider)
);
CREATE INDEX IF NOT EXISTS ix_price_bars_isin ON price_bars (isin, session);
CREATE TABLE IF NOT EXISTS index_bars (
    index_name  TEXT NOT NULL,
    session     TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL NOT NULL,
    pe REAL, pb REAL, div_yield REAL,
    PRIMARY KEY (index_name, session)
);
CREATE TABLE IF NOT EXISTS delivery_sessions (
    session     TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    retrieved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS delivery (
    symbol      TEXT NOT NULL,
    series      TEXT NOT NULL,
    session     TEXT NOT NULL,
    traded_qty  INTEGER NOT NULL,
    delivered_qty INTEGER,
    delivery_pct REAL,
    PRIMARY KEY (symbol, series, session)
);
"""

_SESSION_TABLES = {"equity": "ingested_sessions", "index": "index_sessions",
                   "delivery": "delivery_sessions"}


class MarketStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path, timeout=30)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- sessions ------------------------------------------------------------------------

    def known_sessions(self, dataset: str = "equity") -> dict[date, str]:
        table = _SESSION_TABLES[dataset]
        with self._connect() as conn:
            rows = conn.execute(f"SELECT session, status FROM {table}").fetchall()
        return {date.fromisoformat(s): status for s, status in rows}

    def record_session(
        self, session: date, status: str, *, source_url: str | None = None,
        sha256: str | None = None, retrieved_at: datetime,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ingested_sessions VALUES (?, 'equity', ?, ?, ?, ?)",
                (session.isoformat(), status, source_url, sha256, retrieved_at.isoformat()),
            )

    def record_index_session(self, session: date, status: str, retrieved_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO index_sessions VALUES (?, ?, ?)",
                (session.isoformat(), status, retrieved_at.isoformat()),
            )

    def record_delivery_session(self, session: date, status: str,
                                retrieved_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO delivery_sessions VALUES (?, ?, ?)",
                (session.isoformat(), status, retrieved_at.isoformat()),
            )

    # --- bars ----------------------------------------------------------------------------

    def upsert_bars(self, rows: Iterable[tuple[str, str, str | None, PriceBar]]) -> int:
        """Insert (symbol, series, isin, bar) rows; returns the number written."""
        payload = [
            (sym, series, isin, b.session.isoformat(), b.open, b.high, b.low, b.close,
             b.prev_close, b.volume, b.turnover_inr, b.trades, b.provider)
            for sym, series, isin, b in rows
        ]
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO price_bars VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", payload
            )
        return len(payload)

    def bars_for(self, isin: str, until: date, limit: int) -> list[PriceBar]:
        """Bars across the equity series a security can move between (EQ, BE, BZ).
        A security trades in only one of them on a given session. The delivery file
        has no ISIN, so its rows join on symbol, series and session."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT p.session, p.open, p.high, p.low, p.close, p.prev_close, p.volume, "
                "p.turnover, p.trades, p.provider, d.delivery_pct FROM price_bars p "
                "LEFT JOIN delivery d ON d.symbol = p.symbol AND d.series = p.series "
                "AND d.session = p.session WHERE p.isin = ? AND p.series IN ('EQ', 'BE', 'BZ') "
                "AND p.session <= ? ORDER BY p.session DESC LIMIT ?",
                (isin, until.isoformat(), limit),
            ).fetchall()
        bars = [
            PriceBar(session=date.fromisoformat(r[0]), open=r[1], high=r[2], low=r[3], close=r[4],
                     prev_close=r[5], volume=r[6], turnover_inr=r[7], trades=r[8], provider=r[9],
                     delivery_pct=r[10])
            for r in rows
        ]
        return list(reversed(bars))

    def latest_session(self) -> date | None:
        """The newest session with stored equity prices, or None before the first ingest."""
        with self._connect() as conn:
            (latest,) = conn.execute("SELECT MAX(session) FROM price_bars").fetchone()
        return date.fromisoformat(latest) if latest else None

    def upsert_delivery(self, rows: Iterable[DeliveryRow]) -> int:
        payload = [(r.symbol, r.series, r.session.isoformat(), r.traded_qty, r.delivered_qty,
                    r.delivery_pct) for r in rows]
        with self._connect() as conn:
            conn.executemany("INSERT OR REPLACE INTO delivery VALUES (?,?,?,?,?,?)", payload)
        return len(payload)

    def upsert_index_bars(
        self, rows: Iterable[tuple[str, date, float | None, float | None, float | None, float,
                                   float | None, float | None, float | None]],
    ) -> None:
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO index_bars VALUES (?,?,?,?,?,?,?,?,?)",
                [(name, d.isoformat(), *rest) for name, d, *rest in rows],
            )

    def index_closes(self, index_name: str, until: date, limit: int) -> list[tuple[date, float]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session, close FROM index_bars WHERE index_name = ? AND session <= ? "
                "ORDER BY session DESC LIMIT ?",
                (index_name, until.isoformat(), limit),
            ).fetchall()
        return [(date.fromisoformat(s), c) for s, c in reversed(rows)]

    def latest_index_valuation(self, index_name: str, until: date) -> tuple[date, float | None]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT session, pe FROM index_bars WHERE index_name = ? AND session <= ? "
                "ORDER BY session DESC LIMIT 1",
                (index_name, until.isoformat()),
            ).fetchone()
        if row is None:
            raise LookupError(index_name)
        return date.fromisoformat(row[0]), row[1]
