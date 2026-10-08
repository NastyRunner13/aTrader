"""NSE's latest provisional cash activity; NSE-only and combined scopes never merge.

These endpoints expose the latest session, not history. Observations accumulate in
the store. Publication timestamps are absent, so retrieval time is the conservative
knowledge boundary; later captures are never backdated to the trading session.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from atrader.contracts import InstitutionalActivity, SourceRef
from atrader.data.http import FetchError, PoliteClient
from atrader.data.store import MarketStore
from atrader.timeutil import IST, parse_nse_date

URLS: dict[Literal["nse", "combined"], str] = {
    "nse": "https://www.nseindia.com/api/fiidiiTradeNse",
    "combined": "https://www.nseindia.com/api/fiidiiTradeReact",
}


def parse_activity(payload: Any, scope: Literal["nse", "combined"], source: SourceRef
                   ) -> list[InstitutionalActivity]:
    if not isinstance(payload, list) or not payload:
        raise ValueError("expected non-empty NSE activity rows")
    if source.retrieved_at is None or source.retrieved_at.tzinfo is None:
        raise ValueError("activity requires a timezone-aware observation timestamp")
    result = []
    seen = set()
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError("invalid activity row")
        session = parse_nse_date(row.get("date"))
        participants: dict[str, Literal["FPI", "DII"]] = {"FII/FPI": "FPI", "DII": "DII"}
        participant = participants.get(str(row.get("category")))
        if session is None or participant is None:
            raise ValueError("unknown institutional session or participant")
        if session > source.retrieved_at.astimezone(IST).date():
            raise ValueError("activity session is later than observation")
        key = (session, participant)
        if key in seen:
            raise ValueError("duplicate institutional row")
        seen.add(key)
        amounts = []
        for field in ("buyValue", "sellValue", "netValue"):
            try:
                amount = Decimal(str(row.get(field, "")).replace(",", ""))
            except InvalidOperation as exc:
                raise ValueError(f"invalid {field}") from exc
            if not amount.is_finite():
                raise ValueError(f"non-finite {field}")
            amounts.append(float(amount * 10_000_000))
        result.append(InstitutionalActivity(
            session=session, participant=participant, scope=scope,
            purchases_inr=amounts[0], sales_inr=amounts[1], net_inr=amounts[2],
            available_at=source.retrieved_at, source=source))
    return result


def collect_activity(client: PoliteClient, store: MarketStore) -> tuple[int, list[str]]:
    written, errors = 0, []
    for scope, url in URLS.items():
        try:
            fetched = client.get(url, max_age_s=3600)
            rows = parse_activity(json.loads(fetched.content), scope, SourceRef(
                provider="nse.institutional", url=url, retrieved_at=fetched.retrieved_at,
                content_hash=fetched.sha256))
            written += store.save_institutional_activity(rows)
        except (FetchError, ValueError) as exc:
            errors.append(f"{scope}: {exc}")
    return written, errors
