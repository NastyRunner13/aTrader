"""NSE shareholding-pattern summaries (promoter and public percentages per quarter)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.parse import quote

from atrader.contracts import ShareholdingSnapshot, SourceRef
from atrader.data.http import PoliteClient
from atrader.timeutil import parse_nse_date, parse_nse_datetime

_API = "https://www.nseindia.com/api/corporate-share-holdings-master"
_TTL_S = 12 * 3600


def shareholding_url(symbol: str) -> str:
    return f"{_API}?index=equities&symbol={quote(symbol)}"


def parse_shareholding(payload: Any, retrieved_at: datetime,
                       url: str) -> list[ShareholdingSnapshot]:
    rows = payload if isinstance(payload, list) else []
    snapshots = []
    for row in rows:
        period_end = parse_nse_date(row.get("date"))
        if period_end is None:
            continue
        published = parse_nse_datetime(row.get("broadcastDate"))
        snapshots.append(ShareholdingSnapshot(
            period_end=period_end,
            promoter_pct=_pct(row.get("pr_and_prgrp")),
            public_pct=_pct(row.get("public_val")),
            employee_trust_pct=_pct(row.get("employeeTrusts")),
            published_at=published,
            remarks=(" ".join((row.get("remarksWeb") or "").split())[:400] or None),
            source=SourceRef(provider="nse.shareholding", url=url, published_at=published,
                             retrieved_at=retrieved_at),
        ))
    snapshots.sort(key=lambda s: s.period_end, reverse=True)
    return snapshots


def fetch_shareholding(client: PoliteClient, symbol: str) -> list[ShareholdingSnapshot]:
    url = shareholding_url(symbol)
    fetched = client.get(url, max_age_s=_TTL_S)
    return parse_shareholding(json.loads(fetched.content), fetched.retrieved_at, url)


def _pct(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if 0 <= number <= 100 else None
