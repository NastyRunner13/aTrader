"""The market store and session ingestion, with a fake client: no network."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from atrader.contracts import PriceBar
from atrader.data.http import Fetched, NotFoundError
from atrader.data.providers import nse_bhavcopy
from atrader.data.providers.nse_bhavcopy import DeliveryRow, ingest_sessions
from atrader.data.store import MarketStore
from atrader.timeutil import today_ist


def _bar(session: date, close: float = 100.0) -> PriceBar:
    return PriceBar(session=session, open=close, high=close, low=close, close=close,
                    volume=1000, turnover_inr=close * 1000)


def test_bars_carry_delivery_joined_on_symbol_series_and_session(tmp_path):
    store = MarketStore(tmp_path / "db.sqlite3")
    day1, day2 = date(2026, 9, 30), date(2026, 10, 1)
    store.upsert_bars([("TESTCO", "EQ", "INE000T01019", _bar(day1)),
                       ("TESTCO", "EQ", "INE000T01019", _bar(day2))])
    store.upsert_delivery([DeliveryRow("TESTCO", "EQ", day2, 1000, 600, 60.0),
                           DeliveryRow("TESTCO", "BE", day1, 1000, 1000, 100.0)])
    bars = store.bars_for("INE000T01019", day2, 10)
    assert [(b.session, b.delivery_pct) for b in bars] == [(day1, None), (day2, 60.0)]


class _NothingPublished:
    """A client for which every file 404s, as before the exchange publishes."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def get(self, url: str, *, max_age_s: float | None = None) -> Fetched:
        self.urls.append(url)
        raise NotFoundError(url, "HTTP 404", 404)


def test_recent_404s_are_not_recorded_as_holidays(tmp_path):
    store = MarketStore(tmp_path / "db.sqlite3")
    today = today_ist()
    old = today - timedelta(days=14)
    result = ingest_sessions(_NothingPublished(), store, today, 15)  # type: ignore[arg-type]
    known = store.known_sessions("equity")
    assert old.weekday() >= 5 or known.get(old) == "no_file"  # settled: a holiday
    assert today not in known  # may simply not be published yet: ask again next run
    assert result.holidays == len(known)

    # A premature `no_file` written before this fix is retried, not trusted.
    store.record_session(today, "no_file", retrieved_at=datetime.now(UTC))
    client = _NothingPublished()
    ingest_sessions(client, store, today, 1)  # type: ignore[arg-type]
    if today.weekday() < 5:
        assert nse_bhavcopy.bhavcopy_url(today) in client.urls


def test_delivery_is_fetched_only_for_recent_traded_sessions(tmp_path):
    store = MarketStore(tmp_path / "db.sqlite3")
    until = date(2026, 10, 1)

    class Client:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def get(self, url: str, *, max_age_s: float | None = None) -> Fetched:
            self.urls.append(url)
            raise NotFoundError(url, "HTTP 404", 404)

    client = Client()
    ingest_sessions(client, store, until, 10, delivery_weekdays=3)  # type: ignore[arg-type]
    # every session 404s on the bhavcopy, so no delivery file is asked for
    assert not [u for u in client.urls if "sec_bhavdata_full" in u]
