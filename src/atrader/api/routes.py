"""The HTTP endpoints, under /v1. Each one is a thin wrapper over a service: search and
prices (`Market`), the archive (`ReportLibrary`), runs (`RunManager`), the watchlist."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import FileResponse, StreamingResponse

from atrader import __version__
from atrader.api.market import Market
from atrader.api.reports import ReportLibrary
from atrader.api.runs import CannotStart, RunManager
from atrader.api.schemas import (
    BarsOut,
    EvidenceOut,
    InstrumentOut,
    ReportSummary,
    RunBody,
    RunOut,
    StatusOut,
    Usage,
    WatchlistItem,
)
from atrader.api.watchlist import Watchlist
from atrader.config import Settings
from atrader.contracts import ResearchReport, ResearchRequest
from atrader.data.http import FetchError
from atrader.graph.run_registry import RunRegistry
from atrader.timeutil import today_ist

KEEP_ALIVE_S = 15


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass
class Services:
    settings: Settings
    market: Market
    reports: ReportLibrary
    runs: RunManager
    watchlist: Watchlist
    registry: RunRegistry


def services(request: Request) -> Services:
    return request.app.state.services  # type: ignore[no-any-return]


Svc = Annotated[Services, Depends(services)]


def same_origin(request: Request, svc: Svc) -> None:
    """A page on another site can make the browser send a request to this server. State-
    changing requests that name an Origin must come from the web app (or this server)."""
    origin = request.headers.get("origin")
    settings = svc.settings
    allowed = {*settings.web_origins,
               *(f"http://{host}:{settings.api_port}" for host in settings.api_hosts)}
    if origin is not None and origin not in allowed:
        raise ApiError(403, "forbidden_origin", f"requests from {origin} are not allowed")


router = APIRouter(prefix="/v1")
changes = APIRouter(prefix="/v1", dependencies=[Depends(same_origin)])


# --- status -------------------------------------------------------------------------------


@router.get("/status", response_model=StatusOut)
def get_status(svc: Svc) -> dict[str, Any]:
    settings = svc.settings
    return {"version": __version__, "latest_session": svc.market.latest_session,
            "model": {"api_key_set": settings.openrouter_api_key is not None,
                      "quick": settings.quick_model, "deep": settings.deep_model},
            "active_runs": svc.runs.active_count(), "usage": svc.runs.usage()}


@router.get("/usage", response_model=Usage)
def get_usage(svc: Svc) -> dict[str, int]:
    return svc.runs.usage()


# --- companies and prices -----------------------------------------------------------------


@router.get("/instruments", response_model=list[InstrumentOut])
def search_instruments(svc: Svc, query: Annotated[str, Query(max_length=60)] = "",
                       limit: Annotated[int, Query(ge=1, le=25)] = 10) -> list[Any]:
    try:
        return svc.market.search(query, limit)
    except FetchError as exc:
        raise ApiError(503, "source_unavailable",
                       f"The NSE company list could not be loaded: {exc.reason}") from exc


@router.get("/instruments/{symbol}/bars", response_model=BarsOut)
def get_bars(symbol: str, svc: Svc, sessions: Annotated[int, Query(ge=20, le=1300)] = 250,
             until: date | None = None) -> dict[str, Any]:
    data = _resolved(lambda: svc.market.bars(symbol, sessions, until))
    if not data["bars"]:
        raise ApiError(404, "no_prices", f"No stored prices for {data['symbol']}. "
                       "Run `atrader ingest` to download price history.")
    return data


# --- watchlist ----------------------------------------------------------------------------


@router.get("/watchlist", response_model=list[WatchlistItem])
def get_watchlist(svc: Svc) -> list[dict[str, Any]]:
    flagged = svc.registry.dry_run_ids()
    return [_watch_item(svc, symbol, isin, name, flagged)
            for symbol, isin, name in svc.watchlist.items()]


@changes.put("/watchlist/{symbol}", response_model=WatchlistItem)
def add_to_watchlist(symbol: str, svc: Svc) -> dict[str, Any]:
    listing = _resolved(lambda: svc.market.resolve(symbol))
    svc.watchlist.add(listing)
    return _watch_item(svc, listing.symbol, listing.isin, listing.name,
                       svc.registry.dry_run_ids())


@changes.delete("/watchlist/{symbol}", status_code=204)
def remove_from_watchlist(symbol: str, svc: Svc) -> None:
    if not svc.watchlist.remove(symbol):
        raise ApiError(404, "not_found", f"{symbol.upper()} is not on the watchlist")


# --- reports ------------------------------------------------------------------------------


@router.get("/reports", response_model=list[ReportSummary])
def list_reports(svc: Svc, symbol: str | None = None,
                 limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[dict[str, Any]]:
    flagged = svc.registry.dry_run_ids()
    return [{**r, "dry_run": r["run_id"] in flagged} for r in svc.reports.summaries(symbol, limit)]


@router.get(
    "/reports/{report_id}", response_model=ResearchReport,
    # The price series is large; the chart reads it from /instruments/{symbol}/bars.
    response_model_exclude={"pack": {"bars": True, "indices": {"__all__": {"closes"}}}})
def get_report(report_id: str, svc: Svc) -> ResearchReport:
    return _found(lambda: svc.reports.get(report_id))


@router.get("/reports/{report_id}/evidence/{evidence_id}", response_model=EvidenceOut)
def get_evidence(report_id: str, evidence_id: str, svc: Svc) -> dict[str, Any]:
    return _found(lambda: svc.reports.evidence(report_id, evidence_id))


@router.get("/reports/{report_id}/export")
def export_report(report_id: str, svc: Svc,
                  format: Literal["card", "details", "json"] = "card") -> FileResponse:
    path, media_type = _found(lambda: svc.reports.export_path(report_id, format))
    return FileResponse(path, media_type=media_type, filename=path.name)


# --- runs ---------------------------------------------------------------------------------


@changes.post("/runs", status_code=202, response_model=RunOut)
def start_run(body: RunBody, svc: Svc) -> dict[str, Any]:
    if body.cutoff is not None and body.cutoff > today_ist():
        raise ApiError(422, "bad_cutoff", "The cutoff date cannot be in the future.")
    listing = _resolved(lambda: svc.market.resolve(body.symbol))
    request = ResearchRequest(symbol=listing.symbol, mode=body.mode, cutoff=body.cutoff)
    return _started(svc, lambda: svc.runs.submit(request, body.dry_run))


@router.get("/runs", response_model=list[RunOut])
def list_runs(svc: Svc, limit: Annotated[int, Query(ge=1, le=100)] = 30) -> list[dict[str, Any]]:
    return svc.runs.recent(limit)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, svc: Svc) -> dict[str, Any]:
    return _found(lambda: svc.runs.snapshot(run_id))


@changes.post("/runs/{run_id}/cancel", response_model=RunOut)
def cancel_run(run_id: str, svc: Svc) -> dict[str, Any]:
    _found(lambda: svc.runs.cancel(run_id))
    return svc.runs.snapshot(run_id)


@changes.post("/runs/{run_id}/resume", status_code=202, response_model=RunOut)
def resume_run(run_id: str, svc: Svc) -> dict[str, Any]:
    _found(lambda: svc.runs.snapshot(run_id))
    return _started(svc, lambda: svc.runs.resume(run_id))


@router.get("/runs/{run_id}/events")
def run_events(
    run_id: str, svc: Svc,
    last_event_id: Annotated[int, Header(alias="Last-Event-ID", ge=0)] = 0,
) -> StreamingResponse:
    """Server-sent events: `status`, `progress`, `node` and a final `end`. A client that
    reconnects with `Last-Event-ID` receives only what it missed."""
    snapshot = _found(lambda: svc.runs.snapshot(run_id))
    live = svc.runs.live(run_id)
    if live is None:  # finished before this server started: only the outcome is known
        end = {"id": 1, "type": "end", "status": snapshot["status"],
               "detail": snapshot["detail"], "report_id": snapshot["report_id"]}
        return StreamingResponse(iter([_sse(end)]), media_type="text/event-stream")

    def stream() -> Iterator[str]:
        cursor = last_event_id
        while True:
            events, active = live.wait_for(cursor, KEEP_ALIVE_S)
            for event in events:
                yield _sse(event)
                cursor = event["id"]
            if not active and not events:
                return
            if not events:
                yield ": keep-alive\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --- helpers ------------------------------------------------------------------------------


def _sse(event: dict[str, Any]) -> str:
    return f"id: {event['id']}\nevent: {event['type']}\ndata: {json.dumps(event)}\n\n"


def _found[T](fetch: Callable[[], T]) -> T:
    try:
        return fetch()
    except LookupError as exc:
        raise ApiError(404, "not_found", str(exc.args[0]) if exc.args else "not found") from exc


def _resolved[T](fetch: Callable[[], T]) -> T:
    """Like `_found`, for lookups by symbol: an unknown symbol is a bad request."""
    try:
        return fetch()
    except LookupError as exc:
        raise ApiError(404, "unknown_symbol", str(exc.args[0])) from exc
    except FetchError as exc:
        raise ApiError(503, "source_unavailable",
                       f"The NSE company list could not be loaded: {exc.reason}") from exc


def _started(svc: Services, start: Callable[[], str]) -> dict[str, Any]:
    try:
        run_id = start()
    except CannotStart as exc:
        raise ApiError(409, exc.code, exc.message) from exc
    return svc.runs.snapshot(run_id)


def _watch_item(svc: Services, symbol: str, isin: str, name: str,
                flagged: set[str]) -> dict[str, Any]:
    latest = svc.reports.latest(symbol)
    return {"symbol": symbol, "name": name, "quote": svc.market.quote(isin),
            "latest_report": {**latest, "dry_run": latest["run_id"] in flagged}
            if latest else None}
