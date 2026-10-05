"""NSE end-of-day files: the cash-market bhavcopy (UDiFF format, from July 2024), the
daily index closing file and the security-wise delivery position. All are official
exchange archives; prices are unadjusted."""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from pydantic import ValidationError

from atrader.contracts import PriceBar
from atrader.data.http import FetchError, NotFoundError, PoliteClient
from atrader.data.store import MarketStore
from atrader.timeutil import now_utc, today_ist, weekdays_back

logger = logging.getLogger(__name__)

UDIFF_START = date(2024, 7, 8)
_EQUITY_SERIES = frozenset({"EQ", "BE", "BZ"})
PROVIDER = "nse.bhavcopy"
# Delivery is read over the last 20 sessions against the 60 before, so about four
# months of files is enough; older sessions are not downloaded.
DELIVERY_WEEKDAYS = 100
# A 404 for a session this recent may mean the file is not published yet rather than a
# holiday, so it is not recorded and the next run asks again.
_UNSETTLED_DAYS = 1


def bhavcopy_url(session: date) -> str:
    return ("https://nsearchives.nseindia.com/content/cm/"
            f"BhavCopy_NSE_CM_0_0_0_{session:%Y%m%d}_F_0000.csv.zip")


def index_close_url(session: date) -> str:
    return f"https://nsearchives.nseindia.com/content/indices/ind_close_all_{session:%d%m%Y}.csv"


def delivery_url(session: date) -> str:
    return ("https://nsearchives.nseindia.com/products/content/"
            f"sec_bhavdata_full_{session:%d%m%Y}.csv")


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


@dataclass(frozen=True)
class DeliveryRow:
    symbol: str
    series: str
    session: date
    traded_qty: int
    delivered_qty: int | None
    delivery_pct: float | None


def parse_delivery(text: str) -> Iterator[DeliveryRow]:
    """Yield equity rows from a `sec_bhavdata_full` file. Its header and cells carry
    padding spaces, and the delivery columns read '-' where nothing was reported."""
    reader = csv.reader(io.StringIO(text))
    header = [name.strip() for name in next(reader, [])]
    for raw in reader:
        row = dict(zip(header, (cell.strip() for cell in raw), strict=False))
        if row.get("SERIES") not in _EQUITY_SERIES:
            continue
        try:
            session = datetime.strptime(row["DATE1"], "%d-%b-%Y").date()
            traded = int(float(row["TTL_TRD_QNTY"]))
        except (KeyError, ValueError):
            continue
        pct = _float_or_none(row.get("DELIV_PER"))
        yield DeliveryRow(row["SYMBOL"], row["SERIES"], session, traded,
                          _int_or_none(row.get("DELIV_QTY")),
                          pct if pct is not None and 0 <= pct <= 100 else None)


@dataclass
class IngestResult:
    downloaded: int = 0
    holidays: int = 0
    already_present: int = 0
    delivery_downloaded: int = 0
    failed: list[str] | None = None


def ingest_sessions(
    client: PoliteClient, store: MarketStore, until: date, weekdays: int,
    on_progress: Callable[[date, str], None] | None = None,
    delivery_weekdays: int = DELIVERY_WEEKDAYS,
) -> IngestResult:
    """Download bhavcopy and index files for the last `weekdays` weekdays up to `until`,
    and delivery files for the most recent `delivery_weekdays` of them.

    A 404 for a settled weekday is recorded as `no_file` (a trading holiday) so it is
    not re-requested. A 404 for today or yesterday is not recorded, because the file may
    not be published yet. Days before the UDiFF format are not supported.
    """
    result = IngestResult(failed=[])
    settled = today_ist() - timedelta(days=_UNSETTLED_DAYS)
    known = _settled_only(store.known_sessions("equity"), settled)
    known_index = _settled_only(store.known_sessions("index"), settled)
    known_delivery = _settled_only(store.known_sessions("delivery"), settled)
    sessions = weekdays_back(until, weekdays)
    with_delivery = set(sessions[-delivery_weekdays:]) if delivery_weekdays > 0 else set()
    for session in sessions:
        if session < UDIFF_START:
            continue
        wants_delivery = session in with_delivery and session not in known_delivery
        if session in known and session in known_index and not wants_delivery:
            result.already_present += 1
            continue
        try:
            if session not in known:
                known[session] = _ingest_equity(client, store, session, result, settled)
            if session not in known_index:
                _ingest_index(client, store, session, settled)
            if wants_delivery and known.get(session) == "ok":
                _ingest_delivery(client, store, session, result, settled)
        except FetchError as exc:
            assert result.failed is not None
            result.failed.append(f"{session}: {exc.reason}")
            logger.warning("bhavcopy %s failed: %s", session, exc.reason)
        if on_progress:
            on_progress(session, "done")
    return result


def _settled_only(known: dict[date, str], settled: date) -> dict[date, str]:
    """Known sessions, minus recent `no_file` records that may have been premature."""
    return {s: status for s, status in known.items() if status == "ok" or s < settled}


def _ingest_equity(client: PoliteClient, store: MarketStore, session: date,
                   result: IngestResult, settled: date) -> str:
    url = bhavcopy_url(session)
    try:
        fetched = client.get(url)
    except NotFoundError:
        if session < settled:
            store.record_session(session, "no_file", source_url=url, retrieved_at=now_utc())
            result.holidays += 1
        return "no_file"
    rows = [(r.symbol, r.series, r.isin, r.bar) for r in parse_bhavcopy(fetched.content)]
    store.upsert_bars(rows)
    store.record_session(session, "ok", source_url=url, sha256=fetched.sha256,
                         retrieved_at=fetched.retrieved_at)
    result.downloaded += 1
    return "ok"


def _ingest_index(client: PoliteClient, store: MarketStore, session: date,
                  settled: date) -> None:
    try:
        fetched = client.get(index_close_url(session))
    except NotFoundError:
        if session < settled:
            store.record_index_session(session, "no_file", now_utc())
        return
    store.upsert_index_bars(parse_index_close(fetched.content.decode("utf-8", errors="replace")))
    store.record_index_session(session, "ok", fetched.retrieved_at)


def _ingest_delivery(client: PoliteClient, store: MarketStore, session: date,
                     result: IngestResult, settled: date) -> None:
    try:
        fetched = client.get(delivery_url(session))
    except NotFoundError:
        if session < settled:
            store.record_delivery_session(session, "no_file", now_utc())
        return
    store.upsert_delivery(parse_delivery(fetched.content.decode("utf-8", errors="replace")))
    store.record_delivery_session(session, "ok", fetched.retrieved_at)
    result.delivery_downloaded += 1


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
