"""NSE end-of-day files: the cash-market bhavcopy (UDiFF format, from July 2024) and the
daily index closing file. Both are official exchange archives; prices are unadjusted."""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime

from pydantic import ValidationError

from atrader.contracts import PriceBar
from atrader.data.http import FetchError, NotFoundError, PoliteClient
from atrader.data.store import MarketStore
from atrader.timeutil import now_utc, weekdays_back

logger = logging.getLogger(__name__)

UDIFF_START = date(2024, 7, 8)
_EQUITY_SERIES = frozenset({"EQ", "BE", "BZ"})
PROVIDER = "nse.bhavcopy"


def bhavcopy_url(session: date) -> str:
    return ("https://nsearchives.nseindia.com/content/cm/"
            f"BhavCopy_NSE_CM_0_0_0_{session:%Y%m%d}_F_0000.csv.zip")


def index_close_url(session: date) -> str:
    return f"https://nsearchives.nseindia.com/content/indices/ind_close_all_{session:%d%m%Y}.csv"


@dataclass(frozen=True)
class BhavRow:
    symbol: str
    series: str
    isin: str | None
    bar: PriceBar


def parse_bhavcopy(zip_bytes: bytes) -> Iterator[BhavRow]:
    """Yield equity rows from a UDiFF bhavcopy zip. Invalid rows are skipped and logged."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        name = archive.namelist()[0]
        text = archive.read(name).decode("utf-8", errors="replace")
    skipped = 0
    for row in csv.DictReader(io.StringIO(text)):
        if row.get("FinInstrmTp") != "STK" or row.get("SctySrs") not in _EQUITY_SERIES:
            continue
        try:
            bar = PriceBar(
                session=date.fromisoformat(row["TradDt"]),
                open=float(row["OpnPric"]),
                high=float(row["HghPric"]),
                low=float(row["LwPric"]),
                close=float(row["ClsPric"]),
                prev_close=_float_or_none(row.get("PrvsClsgPric")),
                volume=int(float(row["TtlTradgVol"] or 0)),
                turnover_inr=_float_or_none(row.get("TtlTrfVal")),
                trades=_int_or_none(row.get("TtlNbOfTxsExctd")),
                provider=PROVIDER,
            )
        except (KeyError, ValueError, ValidationError):
            skipped += 1
            continue
        yield BhavRow(row["TckrSymb"], row["SctySrs"], row.get("ISIN") or None, bar)
    if skipped:
        logger.debug("bhavcopy %s: skipped %d invalid rows", name, skipped)


def parse_index_close(text: str) -> list[tuple[str, date, float | None, float | None,
                                               float | None, float, float | None,
                                               float | None, float | None]]:
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            session = datetime.strptime(row["Index Date"].strip(), "%d-%m-%Y").date()
            close = float(row["Closing Index Value"])
        except (KeyError, ValueError):
            continue
        rows.append((
            row["Index Name"].strip(), session,
            _float_or_none(row.get("Open Index Value")),
            _float_or_none(row.get("High Index Value")),
            _float_or_none(row.get("Low Index Value")),
            close,
            _float_or_none(row.get("P/E")),
            _float_or_none(row.get("P/B")),
            _float_or_none(row.get("Div Yield")),
        ))
    return rows


@dataclass
class IngestResult:
    downloaded: int = 0
    holidays: int = 0
    already_present: int = 0
    failed: list[str] | None = None


def ingest_sessions(
    client: PoliteClient, store: MarketStore, until: date, weekdays: int,
    on_progress: Callable[[date, str], None] | None = None,
) -> IngestResult:
    """Download bhavcopy and index files for the last `weekdays` weekdays up to `until`.

    A 404 for a weekday is recorded as `no_file` (a trading holiday) so it is not
    re-requested. Days before the UDiFF format are not supported by this adapter.
    """
    result = IngestResult(failed=[])
    known = store.known_sessions("equity")
    known_index = store.known_sessions("index")
    for session in weekdays_back(until, weekdays):
        if session < UDIFF_START:
            continue
        if session in known and session in known_index:
            result.already_present += 1
            continue
        try:
            if session not in known:
                _ingest_equity(client, store, session, result)
            if session not in known_index:
                _ingest_index(client, store, session)
        except FetchError as exc:
            assert result.failed is not None
            result.failed.append(f"{session}: {exc.reason}")
            logger.warning("bhavcopy %s failed: %s", session, exc.reason)
        if on_progress:
            on_progress(session, "done")
    return result


def _ingest_equity(client: PoliteClient, store: MarketStore, session: date,
                   result: IngestResult) -> None:
    url = bhavcopy_url(session)
    try:
        fetched = client.get(url)
    except NotFoundError:
        store.record_session(session, "no_file", source_url=url, retrieved_at=now_utc())
        result.holidays += 1
        return
    rows = [(r.symbol, r.series, r.isin, r.bar) for r in parse_bhavcopy(fetched.content)]
    store.upsert_bars(rows)
    store.record_session(session, "ok", source_url=url, sha256=fetched.sha256,
                         retrieved_at=fetched.retrieved_at)
    result.downloaded += 1


def _ingest_index(client: PoliteClient, store: MarketStore, session: date) -> None:
    try:
        fetched = client.get(index_close_url(session))
    except NotFoundError:
        store.record_index_session(session, "no_file", now_utc())
        return
    store.upsert_index_bars(parse_index_close(fetched.content.decode("utf-8", errors="replace")))
    store.record_index_session(session, "ok", fetched.retrieved_at)


def _float_or_none(value: str | None) -> float | None:
    if value is None or value.strip() in ("", "-", "NA"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _int_or_none(value: str | None) -> int | None:
    number = _float_or_none(value)
    return int(number) if number is not None else None

