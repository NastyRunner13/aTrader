"""Exchange action descriptions: only explicit split/bonus ratios adjust quantities."""

import json
import re
from datetime import date, datetime
from urllib.parse import urlencode

from atrader.contracts import SourceRef
from atrader.contracts.evidence import CorporateAction
from atrader.data.http import FetchError, PoliteClient
from atrader.timeutil import end_of_day_ist, parse_nse_datetime, today_ist


def parse_actions(content: bytes, symbol: str, source: SourceRef) -> list[CorporateAction]:
    payload = json.loads(content)
    if not isinstance(payload, list) or source.retrieved_at is None:
        raise ValueError("corporate actions require a list and observation time")
    rows = []
    for item in payload:
        if item.get("symbol") != symbol:
            continue
        description = str(item["subject"]).strip()
        if not re.search(
            r"split|sub.division|bonus|rights|merger|demerger|amalgamat", description, re.I
        ):
            continue
        factor = None
        split = re.search(r"From Rs\s*([\d.]+).*?To Rs\s*([\d.]+)", description, re.I)
        bonus = re.fullmatch(r"Bonus\s+(\d+)\s*:\s*(\d+)", description, re.I)
        if split and float(split[2]) > 0:
            factor = float(split[1]) / float(split[2])
        elif bonus and int(bonus[2]) > 0:
            factor = 1 + int(bonus[1]) / int(bonus[2])
        rows.append(
            CorporateAction(
                symbol=symbol,
                ex_date=datetime.strptime(item["exDate"], "%d-%b-%Y").date(),
                description=description,
                share_factor=factor,
                available_at=parse_nse_datetime(item.get("caBroadcastDate")) or source.retrieved_at,
                source=source,
            )
        )
    return rows


def collect_actions(
    client: PoliteClient, symbol: str, cutoff: date
) -> tuple[list[CorporateAction], list[str], date | None]:
    url = "https://www.nseindia.com/api/corporates-corporateActions?" + urlencode(
        {"index": "equities", "symbol": symbol}
    )
    try:
        fetched = client.get(url, max_age_s=86400)
        rows = parse_actions(
            fetched.content,
            symbol,
            SourceRef(
                provider="nse.corporate_actions",
                url=url,
                retrieved_at=fetched.retrieved_at,
                content_hash=fetched.sha256,
            ),
        )
        dates = [
            datetime.strptime(r["exDate"], "%d-%b-%Y").date()
            for r in json.loads(fetched.content)
            if r.get("symbol") == symbol
        ]
        since = min(dates) if dates and cutoff >= today_ist() else None
        return (
            [r for r in rows if r.ex_date <= cutoff and r.available_at <= end_of_day_ist(cutoff)],
            [],
            since,
        )
    except (FetchError, ValueError, KeyError) as exc:
        return [], [str(exc)], None
