"""Time helpers. India has no daylight saving, so a fixed +05:30 offset is exact and
avoids depending on a tz database (absent by default on Windows)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def now_utc() -> datetime:
    return datetime.now(UTC)


def today_ist() -> date:
    return datetime.now(IST).date()


def parse_nse_datetime(text: str | None) -> datetime | None:
    """Parse NSE timestamps such as '16-Jan-2025 20:20:21' or '17-JUL-2026 19:50' (IST)."""
    if not text:
        return None
    cleaned = text.strip()
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%b-%Y"):
        try:
            return datetime.strptime(cleaned.title(), fmt).replace(tzinfo=IST)
        except ValueError:
            continue
    return None


def parse_nse_date(text: str | None) -> date | None:
    parsed = parse_nse_datetime(text)
    return parsed.date() if parsed else None


def end_of_day_ist(day: date) -> datetime:
    """The last instant of an IST calendar day: the knowledge boundary of a cutoff date."""
    return datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=IST)


def weekdays_back(until: date, count: int) -> list[date]:
    """`count` weekdays ending at `until`, oldest first (holidays are filtered later)."""
    days: list[date] = []
    cursor = until
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(days))
