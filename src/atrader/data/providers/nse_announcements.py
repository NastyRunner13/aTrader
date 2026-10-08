"""NSE corporate announcements: official company disclosures with publication time.

Order wins are filed under the category "Bagging/Receiving of orders/contracts". The
announcement text only says an intimation was made; amounts and status live in the
attached PDF, which backlog extraction (F08) will read later.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote

from atrader.contracts import Announcement, SourceRef
from atrader.data.http import PoliteClient
from atrader.timeutil import parse_nse_datetime

_API = "https://www.nseindia.com/api/corporate-announcements"
_TTL_S = 3 * 3600

ORDER_CATEGORIES = frozenset({"Bagging/Receiving of orders/contracts"})
# Routine filings that rarely move a thesis; kept out of the prompt, not deleted.
LOW_SIGNAL_CATEGORIES = frozenset({
    "Copy of Newspaper Publication",
    "Trading Window",
    "Certificate under SEBI (Depositories and Participants) Regulations, 2018",
    "Shareholders meeting",
})


def announcements_url(symbol: str, start: date, end: date) -> str:
    return (f"{_API}?index=equities&symbol={quote(symbol)}"
            f"&from_date={start:%d-%m-%Y}&to_date={end:%d-%m-%Y}")


def parse_announcements(payload: Any, retrieved_at: datetime, url: str) -> list[Announcement]:
    rows = payload if isinstance(payload, list) else (payload or {}).get("data", [])
    items: list[Announcement] = []
    for row in rows:
        published = parse_nse_datetime(row.get("an_dt") or row.get("sort_date"))
        if published is None or not row.get("symbol"):
            continue
        items.append(Announcement(
            isin=row.get("sm_isin"),
            symbol=row["symbol"],
            category=(row.get("desc") or "Uncategorised").strip(),
            summary=_clean(row.get("attchmntText") or ""),
            published_at=published,
            attachment_url=row.get("attchmntFile") or None,
            source=SourceRef(provider="nse.announcements", url=url, published_at=published,
                             retrieved_at=retrieved_at),
        ))
    return items


def fetch_announcements(client: PoliteClient, symbol: str, cutoff: date,
                        lookback_days: int) -> list[Announcement]:
    url = announcements_url(symbol, cutoff - timedelta(days=lookback_days), cutoff)
    fetched = client.get(url, max_age_s=_TTL_S)
    items = parse_announcements(json.loads(fetched.content), fetched.retrieved_at, url)
    return _deduplicate(items)


def _deduplicate(items: list[Announcement]) -> list[Announcement]:
    seen: set[tuple[str, str, str]] = set()
    unique = []
    for item in sorted(items, key=lambda a: a.published_at, reverse=True):
        key = (item.category, item.summary[:160], item.published_at.date().isoformat())
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _clean(text: str) -> str:
    return " ".join(text.split())[:600]
