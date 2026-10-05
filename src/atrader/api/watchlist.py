"""The user's watchlist: the companies they follow, kept in the application database."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from atrader.contracts import Listing

_SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    symbol   TEXT PRIMARY KEY,
    isin     TEXT NOT NULL,
    name     TEXT NOT NULL,
    added_at TEXT NOT NULL
);
"""


class Watchlist:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        with sqlite3.connect(path) as conn:
            conn.executescript(_SCHEMA)

    def items(self) -> list[tuple[str, str, str]]:
        """(symbol, isin, name), newest first."""
        with sqlite3.connect(self._path) as conn:
            return conn.execute(
                "SELECT symbol, isin, name FROM watchlist ORDER BY added_at DESC, symbol"
            ).fetchall()

    def add(self, listing: Listing) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute("INSERT OR IGNORE INTO watchlist VALUES (?, ?, ?, ?)",
                         (listing.symbol, listing.isin, listing.name,
                          datetime.now(UTC).isoformat()))

    def remove(self, symbol: str) -> bool:
        with sqlite3.connect(self._path) as conn:
            return conn.execute("DELETE FROM watchlist WHERE symbol = ?",
                                (symbol.upper(),)).rowcount > 0
