"""GDELT DOC 2.0 headline discovery.

GDELT supplies headline metadata and links, not article rights. Its timestamp is the
time GDELT first saw the article, which is recorded as such. The service asks for at
most one request every five seconds; the HTTP client enforces that.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from atrader.contracts import NewsItem, SourceRef
from atrader.data.http import PoliteClient

_API = "https://api.gdeltproject.org/api/v2/doc/doc"
_TTL_S = 3 * 3600
_SUFFIXES = re.compile(r"\b(limited|ltd\.?|private|pvt\.?)\s*$", re.IGNORECASE)


def company_query(name: str) -> str:
    core = _SUFFIXES.sub("", name).strip().rstrip(",")
    return f'"{core}" sourcelang:english'


def news_url(name: str, cutoff: date, lookback_days: int, max_records: int = 25) -> str:
    end = datetime(cutoff.year, cutoff.month, cutoff.day, 23, 59, 59)
    start = end - timedelta(days=lookback_days)
    params = {
        "query": company_query(name),
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(max_records),
        "sort": "datedesc",
        "startdatetime": start.strftime("%Y%m%d%H%M%S"),
        "enddatetime": end.strftime("%Y%m%d%H%M%S"),
    }
    return f"{_API}?{urlencode(params)}"


def parse_articles(payload: Any, retrieved_at: datetime, url: str) -> list[NewsItem]:
    articles = payload.get("articles", []) if isinstance(payload, dict) else []
    items = []
    for row in articles:
        seen = _seen_date(row.get("seendate"))
        if seen is None or not row.get("url") or not row.get("title"):
            continue
        items.append(NewsItem(
            title=" ".join(str(row["title"]).split())[:300],
            url=row["url"],
            domain=row.get("domain") or "",
            published_at=seen,
            language=row.get("language"),
            source=SourceRef(provider="gdelt.doc (first-seen time)", url=url,
                             published_at=seen, retrieved_at=retrieved_at),
        ))
    return _deduplicate(items)


def company_aliases(name: str, symbol: str) -> list[str]:
    """Names a relevant headline is likely to use: 'Larsen & Toubro Limited' gives
    'larsen & toubro', 'larsen' and 'l&t'; a symbol of 3+ letters is added too."""
    core = _SUFFIXES.sub("", name).strip().rstrip(",").lower()
    words = [w for w in re.split(r"\s+", core) if w]
    aliases = {_tight(core)}
    if words and len(words[0]) >= 4:
        aliases.add(words[0])
    if "&" in words:
        i = words.index("&")
        if 0 < i < len(words) - 1:
            aliases.add(f"{words[i - 1][0]}&{words[i + 1][0]}")
    if len(symbol) >= 3:
        aliases.add(symbol.lower())
    return sorted(aliases)


def mentions_company(title: str, aliases: list[str]) -> bool:
    text = _tight(title.lower())
    return any(re.search(rf"(?<![a-z0-9]){re.escape(_tight(a))}(?![a-z0-9])", text)
               for a in aliases)


def _tight(text: str) -> str:
    """'L & T' and 'L&T' compare equal."""
    return re.sub(r"\s*&\s*", "&", text)


def fetch_company_news(client: PoliteClient, name: str, cutoff: date,
                       lookback_days: int) -> list[NewsItem]:
    url = news_url(name, cutoff, lookback_days, max_records=75)
    fetched = client.get(url, max_age_s=_TTL_S)
    text = fetched.content.decode("utf-8", errors="replace").strip()
    if not text.startswith("{"):
        # GDELT answers rate limits and bad queries with plain text.
        raise ValueError(f"GDELT returned a non-JSON answer: {text[:120]}")
    return parse_articles(json.loads(text), fetched.retrieved_at, url)


def _seen_date(text: Any) -> datetime | None:
    try:
        return datetime.strptime(str(text), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _deduplicate(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    unique = []
    for item in items:
        key = re.sub(r"[^a-z0-9]", "", item.title.lower())[:80]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique
