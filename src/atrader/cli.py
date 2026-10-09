"""Command line: `atrader research LT`, `atrader resume <run>`, `atrader models`, ..."""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

import typer
import uvicorn

from atrader.analytics.portfolio import PortfolioPosition, portfolio_exposures
from atrader.analytics.valuation import ValuationAssumptions, reverse_valuation
from atrader.api.app import create_app
from atrader.config import Settings, get_settings
from atrader.contracts import (
    Coverage,
    CoverageEntry,
    EvidencePack,
    Mode,
    ResearchRequest,
    SourceRef,
)
from atrader.data.documents import extract_pdf
from atrader.data.http import PoliteClient
from atrader.data.providers import nsdl, nse_institutional
from atrader.data.providers.fund_portfolios import (
    DIRECTORY,
    disclosure_directory,
    parse_fund_workbook,
)
from atrader.data.providers.nse_bhavcopy import ingest_sessions
from atrader.data.providers.nse_institutional import collect_activity
from atrader.data.providers.nse_instruments import InstrumentMaster
from atrader.data.store import MarketStore
from atrader.evaluation import audit_summary, evaluate_reports
from atrader.graph.research_graph import ResearchGraph, RunPaused
from atrader.graph.run_registry import RunRegistry
from atrader.llm import GatewayError
from atrader.llm.openrouter import OpenRouterClient
from atrader.llm.policy import FreeModelPolicy, ineligibility_reason
from atrader.llm.usage import UsageLedger
from atrader.report.card import render_card_text
from atrader.timeutil import now_utc, today_ist

app = typer.Typer(no_args_is_help=True, add_completion=False,
                  help="Evidence-linked research agents for Indian listed equities.")


@app.callback()
def _main(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    # The card prints ₹; a Windows pipe would otherwise use a code page without it.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


@app.command()
def research(
    symbol: str = typer.Argument(..., help="NSE symbol or ISIN, e.g. LT or INE018A01030"),
    mode: Mode = typer.Option(Mode.COMPACT,
                             help="data_only (0), baseline (1), compact (6), full (11)"),
    cutoff: str = typer.Option(None, help="Knowledge cutoff YYYY-MM-DD (default: today, IST)"),
    dry_run: bool = typer.Option(False, help="Use placeholder model output; no API calls."),
) -> None:
    """Research one company: a signal card for 1 month, 6 months and 2 years, plus the
    full analysis and JSON."""
    graph = ResearchGraph(dry_run=dry_run,
                          on_progress=lambda step: typer.echo(f"  collecting {step}..."))
    typer.echo(f"Researching {symbol} ({mode.value})" + (" [dry run]" if dry_run else ""))
    try:
        report = graph.run(symbol, mode=mode,
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
    """Download NSE bhavcopy, index and delivery files (first run takes a few minutes)."""
    settings = get_settings()
    settings.ensure_dirs()
    with PoliteClient(settings.cache_dir, settings.http_min_interval_s) as client:
        store = MarketStore(settings.db_path)
        result = ingest_sessions(client, store, today_ist(), sessions)
        activity_count, activity_errors = collect_activity(client, store)
    typer.echo(f"downloaded {result.downloaded}, delivery files {result.delivery_downloaded}, "
               f"holidays {result.holidays}, already present {result.already_present}")
    typer.echo(f"institutional cash observations saved: {activity_count}")
    for failure in [*(result.failed or []), *activity_errors]:
        typer.secho(f"  failed {failure}", fg="yellow")


@app.command("ingest-institutional")
def ingest_institutional() -> None:
    """Capture the latest FPI/DII cash observations without price ingestion."""
    settings = get_settings()
    settings.ensure_dirs()
    with PoliteClient(settings.cache_dir, settings.http_min_interval_s) as client:
        written, errors = collect_activity(client, MarketStore(settings.db_path))
    typer.echo(f"institutional cash observations saved: {written}")
    for error in errors:
        typer.secho(error, fg="yellow")
    if errors:
        raise typer.Exit(1)


@app.command("reverse-valuation")
def reverse_valuation_command(inputs: Path, output: Path) -> None:
    """Evaluate explicit revenue/margin/reinvestment assumptions from JSON."""
    assumptions = ValuationAssumptions.model_validate_json(inputs.read_text(encoding="utf-8"))
    output.write_text(json.dumps(reverse_valuation(assumptions), indent=2), encoding="utf-8")
    typer.echo(f"Sensitivity analysis written to {output}")


@app.command("portfolio-risk")
def portfolio_risk(inputs: Path, output: Path) -> None:
    """Measure concentration and shared exposures supplied in a JSON positions list."""
    positions = [PortfolioPosition.model_validate(p)
                 for p in json.loads(inputs.read_text(encoding="utf-8"))]
    output.write_text(json.dumps(portfolio_exposures(positions), indent=2), encoding="utf-8")
    typer.echo(f"Portfolio exposure analysis written to {output}")


@app.command("fund-disclosures")
def fund_disclosures() -> None:
    """List monthly disclosure sources from AMFI's official directory."""
    settings = get_settings()
    with PoliteClient(settings.cache_dir, settings.http_min_interval_s) as client:
        rows = disclosure_directory(client.get(DIRECTORY, max_age_s=86400).content)
    typer.echo(json.dumps(rows, indent=2))


@app.command("import-fund-portfolio")
def import_fund_portfolio(path: Path, fund: str, period_end: str, available_at: str,
                          source_url: str) -> None:
    """Import an official .xlsx disclosure; NAV percentages are not ownership percentages."""
    observed = datetime.fromisoformat(available_at)
    if observed.tzinfo is None or observed > now_utc():
        raise typer.BadParameter("available-at must include a timezone and not be future dated")
    period = date.fromisoformat(period_end)
    if observed.date() < period:
        raise typer.BadParameter("availability must not precede the reporting period")
    content = path.read_bytes()
    rows = parse_fund_workbook(content, fund, period, observed, SourceRef(
        provider="fund.portfolio", url=source_url, retrieved_at=observed,
        content_hash=hashlib.sha256(content).hexdigest()))
    store = MarketStore(get_settings().db_path)
    written = sum(store.save_research_evidence(isin, [r for r in rows if r.isin == isin])
                  for isin in {r.isin for r in rows})
    typer.echo(f"Saved {written} fund holdings")


@app.command("import-document")
def import_document(path: Path, isin: str, published_at: str, source_url: str) -> None:
    """Add a dated official annual report or presentation to the research archive."""
    published = datetime.fromisoformat(published_at)
    if published.tzinfo is None:
        raise typer.BadParameter("published-at must include a timezone")
    content = path.read_bytes()
    rows, gaps = extract_pdf(content, path.stem, SourceRef(
        provider="official.document.import", url=source_url, published_at=published,
        retrieved_at=now_utc(), content_hash=hashlib.sha256(content).hexdigest()), max_pages=800)
    written = MarketStore(get_settings().db_path).save_research_evidence(isin, rows)
    typer.echo(f"Saved {written} page passages")
    for gap in gaps:
        typer.echo(gap)


@app.command("import-institutional")
def import_institutional(path: Path, dataset: str, observed_at: str, source_url: str) -> None:
    """Backfill saved official captures using their actual, timezone-aware observation time."""
    observed = datetime.fromisoformat(observed_at)
    if observed.tzinfo is None or observed > now_utc():
        raise typer.BadParameter("observed-at must be timezone-aware and not in the future")
    content = path.read_bytes()
    source = SourceRef(provider="nse.institutional", url=source_url, retrieved_at=observed,
                       content_hash=hashlib.sha256(content).hexdigest())
    store = MarketStore(get_settings().db_path)
    if dataset == "nsdl-sectors":
        sectors = nsdl.parse_sector_report(content, source.model_copy(
            update={"provider": "nsdl.sectors"}))
        written = store.save_research_evidence("market", sectors)
    elif dataset == "nsdl-confirmed":
        written = store.save_institutional_activity(nsdl.parse_confirmed(content, source))
    elif dataset in {"nse", "combined"}:
        written = store.save_institutional_activity(nse_institutional.parse_activity(
            json.loads(content), "nse" if dataset == "nse" else "combined", source))
    else:
        raise typer.BadParameter("dataset: nse, combined, nsdl-confirmed, or nsdl-sectors")
    typer.echo(f"Saved {written} observations; knowledge dates were not inferred from report dates")


@app.command("benchmark")
def benchmark(pack_file: Path, output: Path, live: bool = False, ablations: bool = False) -> None:
    """Replay a frozen evidence pack across data-only, single-model, compact and full modes.

    Default is a workflow dry run. --live uses the existing free-only gateway and quota.
    --ablations also runs compact mode with documents, ownership or flow evidence removed.
    """
    pack = EvidencePack.model_validate_json(pack_file.read_text(encoding="utf-8"))
    settings = get_settings().model_copy(update={"reports_dir": output})

    class FrozenSource:
        def __init__(self, frozen: EvidencePack):
            self.pack = frozen

        def build(self, request: ResearchRequest) -> EvidencePack:
            return self.pack

    variants = [(mode.value, mode, pack) for mode in Mode]
    if ablations:
        for group in ("documents", "ownership", "institutional_activity", "sector_flows"):
            removed = {item.evidence_id for item in getattr(pack, group)}
            keep = list(pack.metrics)
            while True:
                affected = {m.evidence_id for m in keep if set(m.inputs) & removed}
                if not affected:
                    break
                removed |= affected
                keep = [m for m in keep if m.evidence_id not in removed]
            category = {"documents": "documents", "ownership": "institutional_ownership",
                        "institutional_activity": "institutional_market_activity",
                        "sector_flows": "institutional_sector_activity"}[group]
            coverage = [c for c in pack.coverage if c.category != category]
            coverage.append(CoverageEntry(category=category, status=Coverage.NOT_REQUESTED,
                                          detail="Intentionally omitted for this ablation"))
            changed = pack.model_copy(update={group: (), "metrics": tuple(keep),
                                              "coverage": tuple(coverage)})
            variants.append((f"without_{group}", Mode.COMPACT, changed))
    manifest = []
    for label, mode, frozen in variants:
        graph = ResearchGraph(settings, dry_run=not live, evidence_source=FrozenSource(frozen))
        report = graph.run(
            pack.listing.symbol, mode=mode, cutoff=pack.cutoff)
        manifest.append({"variant": label, "report": report.report_id,
                         "pack_id": frozen.pack_id, "dry_run": not live})
    (output / "benchmark-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    typer.echo("Benchmark saved; dry-run outputs do not measure model quality" if not live else
               "Benchmark saved; use evaluate and human source review before comparing quality")


@app.command("evaluate")
def evaluate(directory: Path, output: Path) -> None:
    """Audit saved reports, prepare human-review cases and measure available forward returns."""
    result = evaluate_reports(list(directory.glob("*.json")), MarketStore(get_settings().db_path))
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    typer.echo(f"Evaluated {len(result['reports'])} reports; human audit remains ungraded")


@app.command("audit-summary")
def audit_summary_command(audit_file: Path, output: Path) -> None:
    """Summarise manually labelled human_audit entries with denominator and uncertainty."""
    payload = json.loads(audit_file.read_text(encoding="utf-8"))
    result = audit_summary(payload["human_audit"])
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    typer.echo(f"Reviewed {result['reviewed']} of {result['sampled']} sampled claims")


@app.command()
def serve(
    host: str = typer.Option(None, help="Interface to listen on (default 127.0.0.1)"),
    port: int = typer.Option(None, help="Port (default 8000)"),
) -> None:
    """Start the web API that the aTrader web app talks to."""
    settings = get_settings()
    uvicorn.run(create_app(settings), host=host or settings.api_host,
                port=port or settings.api_port, log_level="info")


@app.command()
def openapi(out: Path = typer.Argument(Path("apps/web/openapi.json"))) -> None:
    """Write the web API's OpenAPI schema; the web app's TypeScript types come from it."""
    # A throwaway data directory, so exporting never touches real runs or reports.
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        app_ = create_app(Settings(_env_file=None, data_dir=root, reports_dir=root / "reports"))
        out.write_text(json.dumps(app_.openapi(), indent=2) + "\n", encoding="utf-8")
    typer.echo(f"wrote {out}")


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
    typer.echo("")
    typer.echo(render_card_text(report))
    calls = [c for c in report.model_calls if c.status != "blocked"]
    reports_dir = get_settings().reports_dir
    typer.echo(f"\nStatus: {report.status.value}   model calls: {len(calls)}")
    typer.echo(f"Card:      {reports_dir / (report.report_id + '.md')}")
    typer.echo(f"Analysis:  {reports_dir / (report.report_id + '-details.md')}")


if __name__ == "__main__":
    app()
