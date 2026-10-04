"""NSE equity master (`EQUITY_L.csv`): symbol, company name, series and ISIN."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from atrader.contracts import Listing
from atrader.data.http import PoliteClient

EQUITY_LIST_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
_REFRESH_S = 7 * 24 * 3600


def parse_equity_list(text: str) -> list[Listing]:
    reader = csv.DictReader(io.StringIO(text))
    listings: list[Listing] = []
    for raw in reader:
        row = {(k or "").strip(): (v or "").strip() for k, v in raw.items()}
        try:
            listed_on = datetime.strptime(row["DATE OF LISTING"], "%d-%b-%Y").date()
        except (KeyError, ValueError):
            listed_on = None
        try:
            listings.append(Listing(
                symbol=row["SYMBOL"],
                isin=row["ISIN NUMBER"],
                name=row["NAME OF COMPANY"],
                series=row.get("SERIES") or "EQ",
                listed_on=listed_on,
                face_value=float(row["FACE VALUE"]) if row.get("FACE VALUE") else None,
            ))
        except (KeyError, ValueError):
            continue  # malformed or non-Indian ISIN rows are skipped, not guessed
    return listings


class InstrumentMaster:
    def __init__(self, listings: list[Listing]) -> None:
        self._by_symbol = {item.symbol: item for item in listings}
        self._by_isin = {item.isin: item for item in listings}

    @classmethod
    def load(cls, client: PoliteClient) -> InstrumentMaster:
        fetched = client.get(EQUITY_LIST_URL, max_age_s=_REFRESH_S)
        return cls(parse_equity_list(fetched.content.decode("utf-8", errors="replace")))

    def __len__(self) -> int:
        return len(self._by_symbol)

    def resolve(self, query: str) -> Listing:
        """Exact symbol or ISIN. Ambiguity is an error, never a guess."""
        key = query.strip().upper().removesuffix(".NS")
        if key in self._by_symbol:
            return self._by_symbol[key]
        if key in self._by_isin:
            return self._by_isin[key]
        matches = self.search(query, limit=5)
        hint = ", ".join(f"{m.symbol} ({m.name})" for m in matches) or "no close matches"
        raise LookupError(f"{query!r} is not an NSE symbol or ISIN; candidates: {hint}")

    def search(self, query: str, limit: int = 10) -> list[Listing]:
        needle = query.strip().lower()
        hits = [
            item for item in self._by_symbol.values()
            if needle in item.symbol.lower() or needle in item.name.lower()
        ]
        hits.sort(key=lambda item: (item.symbol.lower() != needle, len(item.name)))
        return hits[:limit]
