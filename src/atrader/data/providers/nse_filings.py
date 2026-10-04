"""NSE financial-results filings index and XBRL retrieval.

Two exchange endpoints cover different eras:

* `corporates-financial-results` — the legacy Reg. 33 results, up to Q3 FY25.
* `integrated-filing-results` (Integrated Filing - Financials) — from Q4 FY25.

These are unofficial website endpoints, used here for personal research with polite
pacing and caching. They are not a licensed feed; see docs/05.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import quote

from atrader.contracts import StatementBasis
from atrader.data.http import FetchError, PoliteClient
from atrader.timeutil import parse_nse_date, parse_nse_datetime

logger = logging.getLogger(__name__)

_API = "https://www.nseindia.com/api"
_INDEX_TTL_S = 6 * 3600


@dataclass(frozen=True)
class FilingRef:
    symbol: str
    period_end: date
    basis: StatementBasis
    audited: bool | None
    filed_at: datetime
    xbrl_url: str
    source_api: str
    revision: str | None = None


def legacy_results_url(symbol: str) -> str:
    return (f"{_API}/corporates-financial-results?index=equities&symbol={quote(symbol)}"
            "&period=Quarterly")


def integrated_results_url(symbol: str) -> str:
    return (f"{_API}/integrated-filing-results?index=equities&symbol={quote(symbol)}"
            f"&type={quote('Integrated Filing- Financials')}")


def parse_legacy_index(payload: Any, symbol: str) -> list[FilingRef]:
    rows = payload if isinstance(payload, list) else []
    refs = []
    for row in rows:
        basis = _basis(row.get("consolidated"))
        filed_at = parse_nse_datetime(row.get("broadCastDate") or row.get("filingDate"))
        period_end = parse_nse_date(row.get("toDate"))
        url = row.get("xbrl")
        if basis is None or filed_at is None or period_end is None or not _is_xbrl(url):
            continue
        refs.append(FilingRef(symbol, period_end, basis, _audited(row.get("audited")),
                              filed_at, url, "nse.legacy_results"))
    return refs


def parse_integrated_index(payload: Any, symbol: str) -> list[FilingRef]:
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    refs = []
    for row in rows:
        basis = _basis(row.get("consolidated"))
        filed_at = parse_nse_datetime(row.get("broadcast_Date") or row.get("creation_Date"))
        period_end = parse_nse_date(row.get("qe_Date"))
        url = row.get("xbrl")
        if basis is None or filed_at is None or period_end is None or not _is_xbrl(url):
            continue
        refs.append(FilingRef(symbol, period_end, basis, _audited(row.get("audited")),
                              filed_at, url, "nse.integrated_filing",
                              revision=row.get("type_Sub")))
    return refs


def list_result_filings(client: PoliteClient, symbol: str) -> tuple[list[FilingRef], list[str]]:
    """All result filings from both endpoints, newest period first, plus any errors."""
    refs: list[FilingRef] = []
    errors: list[str] = []
    for url, parser in ((integrated_results_url(symbol), parse_integrated_index),
                        (legacy_results_url(symbol), parse_legacy_index)):
        try:
            payload = json.loads(client.get(url, max_age_s=_INDEX_TTL_S).content)
            refs.extend(parser(payload, symbol))
        except (FetchError, json.JSONDecodeError) as exc:
            errors.append(f"{url.split('?')[0].rsplit('/', 1)[-1]}: {exc}")
    refs.sort(key=lambda r: (r.period_end, r.filed_at), reverse=True)
    return refs, errors


def select_filings(refs: list[FilingRef], cutoff: datetime, quarters: int) -> list[FilingRef]:
    """Latest filing per period, filed before the cutoff, preferring consolidated.

    One basis is chosen for the whole series (consolidated if the latest eligible
    period has it), so growth rates never mix standalone and consolidated figures.
    A revised filing for the same period and basis supersedes the original.
    """
    eligible = [r for r in refs if r.filed_at <= cutoff]
    if not eligible:
        return []
    latest_period = max(r.period_end for r in eligible)
    has_consolidated = any(r.period_end == latest_period and
                           r.basis == StatementBasis.CONSOLIDATED for r in eligible)
    basis = StatementBasis.CONSOLIDATED if has_consolidated else StatementBasis.STANDALONE

    by_period: dict[date, FilingRef] = {}
    for ref in sorted(eligible, key=lambda r: r.filed_at):
        if ref.basis == basis:
            by_period[ref.period_end] = ref  # later filing wins
    periods = sorted(by_period, reverse=True)[:quarters]
    return [by_period[p] for p in periods]


def _basis(text: str | None) -> StatementBasis | None:
    if not text:
        return None
    lowered = text.lower()
    if lowered.startswith("non-consolidated") or lowered.startswith("standalone"):
        return StatementBasis.STANDALONE
    if lowered.startswith("consolidated"):
        return StatementBasis.CONSOLIDATED
    return None


def _audited(text: str | None) -> bool | None:
    if not text:
        return None
    lowered = text.lower()
    if lowered.startswith("un"):
        return False
    return lowered.startswith("audited") or None


def _is_xbrl(url: Any) -> bool:
    return isinstance(url, str) and url.startswith("https://") and url.lower().endswith(".xml")
