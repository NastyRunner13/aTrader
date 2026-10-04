"""Command line: `atrader research LT`, `atrader resume <run>`, `atrader models`, ..."""

from __future__ import annotations

import json
import logging
from datetime import date

import typer

from atrader.config import get_settings
from atrader.contracts import Horizon, Mode
from atrader.data.http import PoliteClient
from atrader.data.providers.nse_bhavcopy import ingest_sessions
from atrader.data.providers.nse_instruments import InstrumentMaster
from atrader.data.store import MarketStore
from atrader.graph.research_graph import ResearchGraph, RunPaused
from atrader.graph.run_registry import RunRegistry
from atrader.llm import GatewayError
from atrader.llm.openrouter import OpenRouterClient
from atrader.llm.policy import FreeModelPolicy, ineligibility_reason
from atrader.llm.usage import UsageLedger
from atrader.timeutil import today_ist

app = typer.Typer(no_args_is_help=True, add_completion=False,
                  help="Evidence-linked research agents for Indian listed equities.")


@app.callback()
def _main(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")


@app.command()
def research(
    symbol: str = typer.Argument(..., help="NSE symbol or ISIN, e.g. LT or INE018A01030"),
    mode: Mode = typer.Option(Mode.COMPACT, help="data_only (0 calls), compact (6), full (13)"),
    horizon: Horizon = typer.Option(Horizon.SWING),
    cutoff: str = typer.Option(None, help="Knowledge cutoff YYYY-MM-DD (default: today, IST)"),
    dry_run: bool = typer.Option(False, help="Use placeholder model output; no API calls."),
) -> None:
    """Research one company and write a Markdown + JSON report."""
    graph = ResearchGraph(dry_run=dry_run,
                          on_progress=lambda step: typer.echo(f"  collecting {step}..."))
    typer.echo(f"Researching {symbol} ({mode.value}, {horizon.value})"
               + (" [dry run]" if dry_run else ""))
    try:
        report = graph.run(symbol, mode=mode, horizon=horizon,
                           cutoff=date.fromisoformat(cutoff) if cutoff else None)
    except RunPaused as exc:
        typer.secho(f"{exc}\nResume later with: atrader resume {exc.run_id}", fg="yellow")
        raise typer.Exit(2) from exc
    except (GatewayError, LookupError) as exc:
        typer.secho(str(exc), fg="red")
        raise typer.Exit(1) from exc
    _print_summary(report)


@app.command()
def resume(run_id: str) -> None:
    """Continue a paused run from its last checkpoint."""
    try:
        report = ResearchGraph().resume(run_id)
    except RunPaused as exc:
        typer.secho(str(exc), fg="yellow")
        raise typer.Exit(2) from exc
    _print_summary(report)


@app.command()
def ingest(sessions: int = typer.Option(320, help="Weekdays of history to download")) -> None:
    """Download NSE bhavcopy and index files (first run takes a few minutes)."""
    settings = get_settings()
    settings.ensure_dirs()
    with PoliteClient(settings.cache_dir, settings.http_min_interval_s) as client:
        result = ingest_sessions(client, MarketStore(settings.db_path), today_ist(), sessions)
    typer.echo(f"downloaded {result.downloaded}, holidays {result.holidays}, "
               f"already present {result.already_present}")
    for failure in result.failed or []:
        typer.secho(f"  failed {failure}", fg="yellow")


@app.command()
def search(query: str) -> None:
    """Find NSE listings by symbol or company name."""
    settings = get_settings()
    settings.ensure_dirs()
    with PoliteClient(settings.cache_dir) as client:
        master = InstrumentMaster.load(client)
    for listing in master.search(query):
        typer.echo(f"{listing.symbol:<14} {listing.isin}  {listing.name}")


@app.command()
def models() -> None:
    """List OpenRouter models the free-only policy allows."""
    settings = get_settings()
    client = OpenRouterClient(None, settings.openrouter_base_url, settings.request_timeout_s)
    catalog = client.list_models()
    allowlist = frozenset(settings.model_allowlist)
    for model in FreeModelPolicy(catalog, allowlist).eligible():
        schema = "json_schema" if model.supports_json_schema else (
            "json_mode" if model.supports_json_mode else "prompt-only")
        typer.echo(f"{model.id:<55} ctx {model.context_length or '?':>8}  {schema}")
    for name, configured in (("quick", settings.quick_model), ("deep", settings.deep_model)):
        info = next((m for m in catalog if m.id == configured), None)
        reason = "not in catalog" if info is None else ineligibility_reason(info, allowlist)
        status = "ok" if reason is None else f"BLOCKED: {reason}"
        typer.echo(f"configured {name} model: {configured} — {status}")


@app.command()
def usage() -> None:
    """Show today's model-request usage against the configured allowance."""
    settings = get_settings()
    ledger = UsageLedger(settings.db_path, settings.usable_daily_requests)
    typer.echo(f"used today (UTC): {ledger.used_today()} of {settings.usable_daily_requests} "
               f"usable ({settings.daily_request_limit} limit, {settings.daily_request_reserve} "
               "held in reserve)")


@app.command()
def runs(limit: int = 15) -> None:
    """List recent runs."""
    for run_id, request_json, status, report_path, created in RunRegistry(
            get_settings().db_path).recent(limit):
        request = json.loads(request_json)
        typer.echo(f"{created[:16]}  {run_id[:12]}  {request['symbol']:<12} {request['mode']:<9} "
                   f"{status:<12} {report_path or ''}")


def _print_summary(report) -> None:  # type: ignore[no-untyped-def]
    assessment = report.assessment.value if report.assessment else "none (data only)"
    typer.secho(f"\nAssessment: {assessment}   status: {report.status.value}", bold=True)
    for veto in report.vetoes:
        typer.echo(f"  {veto.severity:<5} {veto.code}: {veto.message}")
    calls = [c for c in report.model_calls if c.status != "blocked"]
    typer.echo(f"Model calls: {len(calls)}")
    typer.echo(f"Report: {get_settings().reports_dir / (report.report_id + '.md')}")


if __name__ == "__main__":
    app()
