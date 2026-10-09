"""Offline report audits and forward-return measurements with explicit denominators."""

import json
from collections import defaultdict
from math import sqrt
from pathlib import Path
from typing import Any

from atrader.analytics.prices import split_bonus_adjust
from atrader.contracts import Claim, ResearchReport
from atrader.data.store import MarketStore
from atrader.timeutil import end_of_day_ist, today_ist


def audit_summary(audit: list[dict[str, Any]]) -> dict[str, Any]:
    """Wilson interval over explicitly human-labelled support, never machine citation status."""
    reviewed = [row for row in audit if isinstance(row.get("human_support"), bool)]
    n = len(reviewed)
    supported = sum(row["human_support"] for row in reviewed)
    interval = None
    if n:
        p, z = supported / n, 1.96
        center = (p + z*z/(2*n)) / (1+z*z/n)
        half = z * sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1+z*z/n)
        interval = [max(0, center-half), min(1, center+half)]
    return {"sampled": len(audit), "reviewed": n, "unreviewed": len(audit)-n,
            "supported": supported, "support_rate": supported/n if n else None,
            "support_rate_95pct_wilson": interval,
            "threshold_95pct_met": supported/n >= .95 if n else None,
            "limitations": ["human labels supplied by reviewer; sampling design matters",
                            "meeting a support threshold does not establish predictive accuracy"]}


def evaluate_reports(paths: list[Path], store: MarketStore) -> dict[str, Any]:
    rows, audit = [], []
    modes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or "report_id" not in payload:
            continue
        report = ResearchReport.model_validate(payload)
        pack = report.pack
        if pack is None:
            continue
        claims = [c for a in report.analyst_reports for c in a.claims]
        claims += [c for turn in report.debate for c in turn.claims]
        for analyst in report.analyst_reports:
            claims += [Claim(claim_id=f"{analyst.agent}-{item.topic}", agent=analyst.agent,
                             statement=item.finding, kind="interpretation", status="needs_review",
                             evidence_ids=item.evidence_ids)
                       for item in analyst.investigations if item.status != "unknown"]
            claims += [Claim(claim_id=f"{analyst.agent}-term-{i}", agent=analyst.agent,
                             statement=f"{term.name}: {term.value}",
                             kind="fact", status="needs_review",
                             evidence_ids=[term.support.evidence_id])
                       for i, term in enumerate(analyst.disclosure_terms)]
        if report.final_synthesis:
            claims += [Claim(claim_id=f"synthesis-{i}", agent="portfolio_manager",
                             statement=reason.statement, kind="interpretation",
                             status="needs_review",
                             evidence_ids=reason.evidence_ids)
                       for i, reason in enumerate(report.final_synthesis.pros
                                                  + report.final_synthesis.cons)]
        ids = pack.evidence_ids()
        unknown = sum(any(i not in ids for i in c.evidence_ids) for c in claims)
        unsupported = sum(c.status == "unsupported" for c in claims)
        future = [f.evidence_id for f in pack.facts if f.filed_at > end_of_day_ist(pack.cutoff)]
        result: dict[str, Any] = {
            "report": report.report_id,
            "mode": report.request.mode.value,
            "cutoff": str(pack.cutoff),
            "pack_id": pack.pack_id,
            "isin": pack.listing.isin,
            "claims": len(claims),
            "dry_run": any(c.requested_model.startswith("fake/") for c in report.model_calls),
            "unsupported_claims": unsupported,
            "unknown_citation_claims": unknown,
            "future_filing_ids": future,
            "model_calls": len(report.model_calls),
            "model_latency_ms": sum(c.latency_ms or 0 for c in report.model_calls),
            "cost": sum(c.cost or 0 for c in report.model_calls),
            "returns": {},
        }
        prices, _ = split_bonus_adjust(store.bars_for(pack.listing.isin, today_ist(), 3000))
        start = next((i for i, b in enumerate(prices) if b.session > pack.cutoff), None)
        if start is not None:
            for horizon, sessions in (("1m", 21), ("6m", 126), ("2y", 504)):
                if start + sessions < len(prices):
                    forward = prices[start + sessions].close / prices[start].open - 1
                    score = (
                        next(
                            (
                                h.score
                                for h in report.scorecard.horizons
                                if h.horizon.value == horizon
                            ),
                            None,
                        )
                        if report.scorecard
                        else None
                    )
                    result["returns"][horizon] = {
                        "sessions": sessions,
                        "entry_session": str(prices[start].session),
                        "price_return": forward,
                        "score": score,
                    }
        for claim in claims:
            audit.append(
                {
                    "report": report.report_id,
                    "claim_id": claim.claim_id,
                    "statement": claim.statement,
                    "evidence_ids": claim.evidence_ids,
                    "machine_status": claim.status.value,
                    "sources": [
                        pack.items_by_id()[i].model_dump(mode="json")
                        for i in claim.evidence_ids
                        if i in ids
                    ],
                    "human_support": None,
                    "human_notes": "",
                }
            )
        rows.append(result)
        modes[report.request.mode.value].append(result)
    return {
        "reports": rows,
        "human_audit": audit,
        "by_mode": {
            mode: {
                "reports": len(group),
                "claims": sum(r["claims"] for r in group),
                "unsupported": sum(r["unsupported_claims"] for r in group),
                "calls": sum(r["model_calls"] for r in group),
            }
            for mode, group in modes.items()
        },
        "limitations": [
            "human semantic support has not been judged by this command",
            "entry uses next stored session open; returns exclude dividends and costs",
            "horizons count stored sessions; sparse archives are not a trading calendar",
            "historical LLM reports may contain training-data hindsight",
            "selection bias and missing outcomes prevent performance claims",
            "no weights are fitted or changed automatically",
        ],
    }
