"""Assemble the published report from the graph's final state."""

from __future__ import annotations

from typing import Any

from atrader.contracts import (
    AgentStatus,
    Mode,
    ModelCall,
    ResearchReport,
    ResearchRequest,
    RunStatus,
)
from atrader.timeutil import now_utc

LIMITATIONS = [
    "Research output, not investment advice. No order is placed and no return is promised.",
    "Scores, weights and signals are experimental: rules and starting weights that have not "
    "yet been validated against historical returns. They are not calibrated probabilities.",
    "Price ranges describe past volatility or stated scenarios. They are not forecasts or "
    "price targets.",
    "Prices are NSE end-of-day bhavcopy data; intraday paths and market depth are not known.",
    "Filings, announcements and shareholding come from NSE website endpoints used for "
    "personal research; they are not a licensed data feed and may change without notice.",
    "Claim verification checks that every citation exists in this run's evidence; it does "
    "not prove that a model's reading of the evidence is correct.",
    "Language models may carry knowledge from after the cutoff in their training data; "
    "reports on past dates are not clean backtests.",
]


def build_report(run_id: str, request: ResearchRequest, state: dict[str, Any],
                 calls: list[ModelCall]) -> ResearchReport:
    pack = state.get("pack")
    synthesis = state.get("final_synthesis")
    analysts = list(state.get("analyst_reports", {}).values())
    debate = state.get("debate", [])
    reviews = state.get("risk_reviews", [])

    statuses = [a.status for a in analysts] + [t.status for t in debate] + [
        r.status for r in reviews]
    statuses += [synthesis.status] if synthesis else []
    status = RunStatus.PARTIAL if AgentStatus.FAILED in statuses else RunStatus.COMPLETED

    notes: list[str] = []
    if request.mode == Mode.COMPACT:
        notes.append("Compact mode: one debate round; the risk team did not run.")
    if request.mode == Mode.DATA_ONLY:
        notes.append("Data-only run: a code-only scorecard. No model adjusted it and news "
                     "was not scored.")
    if pack is not None and not pack.has_core_evidence:
        notes.append("Minimum evidence was missing, so no AI analysis ran.")
    notes += [f"{a.agent} skipped: {a.error}" for a in analysts if a.status == AgentStatus.SKIPPED]
    if synthesis and synthesis.dropped_reasons:
        notes += [f"Removed unsupported pro or con: {r}" for r in synthesis.dropped_reasons]

    cutoff = pack.cutoff if pack else request.cutoff
    return ResearchReport(
        report_id=f"{request.symbol}-{cutoff}-{request.mode.value}-{run_id[:8]}",
        run_id=run_id,
        generated_at=now_utc(),
        status=status,
        request=request,
        pack=pack,
        scorecard=state.get("scorecard"),
        vetoes=state.get("vetoes", []),
        coverage=list(pack.coverage) if pack else [],
        analyst_reports=analysts,
        debate=debate,
        risk_reviews=reviews,
        final_synthesis=synthesis,
        model_calls=calls,
        notes=notes,
        limitations=LIMITATIONS,
    )
