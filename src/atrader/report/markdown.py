"""Render a ResearchReport as Markdown (structure from docs/01, "Report structure")."""

from __future__ import annotations

from atrader.contracts import (
    AgentStatus,
    ClaimStatus,
    EvidencePack,
    Mode,
    Reason,
    ResearchReport,
)
from atrader.formatting import format_value

_ASSESSMENT_LABEL = {
    "supportive": "Supportive",
    "mixed": "Mixed",
    "adverse": "Adverse",
    "insufficient_evidence": "Insufficient evidence",
}


def render_markdown(report: ResearchReport) -> str:
    pack = report.pack
    parts = [_header(report), _assessment(report)]
    if pack is not None:
        parts += [_coverage(report), _financials(pack), _metrics(pack), _catalysts(pack)]
    if report.request.mode != Mode.DATA_ONLY:
        parts += [_analysts(report), _debate(report), _full_mode(report), _conditions(report)]
    parts += [_appendix(report)]
    return "\n\n".join(p for p in parts if p).strip() + "\n"


def _header(report: ResearchReport) -> str:
    pack, request = report.pack, report.request
    name = f"{pack.listing.name} ({pack.listing.exchange}: {pack.listing.symbol})" if pack \
        else request.symbol
    lines = [
        f"# {name}",
        "",
        "| | |",
        "|---|---|",
        f"| ISIN | {pack.listing.isin if pack else 'unresolved'} |",
        f"| Horizon | {request.horizon.description} |",
        f"| Knowledge cutoff | {pack.cutoff if pack else request.cutoff or 'latest'} (IST) |",
        f"| Mode | {request.mode.value} |",
        f"| Status | {report.status.value} |",
        f"| Generated | {report.generated_at:%Y-%m-%d %H:%M} UTC |",
        f"| Evidence pack | `{pack.pack_id if pack else 'none'}` |",
        f"| Run | `{report.run_id}` |",
    ]
    return "\n".join(lines)


def _assessment(report: ResearchReport) -> str:
    if report.request.mode == Mode.DATA_ONLY:
        return "## Assessment\n\nData-only run: no model was called and no assessment is made."
    label = _ASSESSMENT_LABEL[report.assessment.value] if report.assessment else "None"
    lines = [f"## Assessment: {label}"]
    before = report.assessment_before_vetoes
    if before and report.assessment and before != report.assessment:
        lines.append(f"\nThe portfolio manager wrote **{_ASSESSMENT_LABEL[before.value]}**; "
                     "code-enforced constraints changed it.")
    synthesis = report.final_synthesis
    if synthesis and synthesis.summary:
        lines.append(f"\n{synthesis.summary}")
    if synthesis and synthesis.top_reasons:
        lines += ["", "**Top reasons**", *_reasons(synthesis.top_reasons)]
    if synthesis and synthesis.key_risks:
        lines += ["", "**Key risks**", *_reasons(synthesis.key_risks)]
    if report.vetoes:
        lines += ["", "**Code-enforced constraints**"]
        lines += [f"- `{v.severity}` {v.code}: {v.message}" for v in report.vetoes]
    return "\n".join(lines)


def _reasons(reasons: list[Reason]) -> list[str]:
    return [f"- {r.statement} {_cite(r.evidence_ids, r.statement)}".rstrip() for r in reasons]


def _coverage(report: ResearchReport) -> str:
    lines = ["## Coverage", "", "| Source | Status | Detail |", "|---|---|---|"]
    lines += [f"| {c.category} | {c.status.value} | {c.detail} |" for c in report.coverage]
    return "\n".join(lines)


def _financials(pack: EvidencePack) -> str:
    quarter = [f for f in pack.facts if f.duration == "quarter"]
    if not quarter:
        return ""
    periods = sorted({f.period_end for f in quarter}, reverse=True)[:5]
    metrics = list(dict.fromkeys(f.metric for f in quarter))
    labels = {f.metric: f.label for f in quarter}
    lookup = {(f.metric, f.period_end): f for f in quarter}
    basis = quarter[0].basis.value
    lines = [f"## Reported quarterly results ({basis}, ₹ crore)", "",
             "| Line item | " + " | ".join(str(p) for p in periods) + " |",
             "|---|" + "---|" * len(periods)]
    for metric in metrics:
        cells = []
        for period in periods:
            fact = lookup.get((metric, period))
            cells.append(f"{format_value(fact.value, fact.unit)} [{fact.evidence_id}]" if fact
                         else "—")
        lines.append(f"| {labels[metric]} | " + " | ".join(cells) + " |")
    restated = [f for f in pack.facts if f.revision_note]
    if restated:
        lines += ["", *[f"- {f.evidence_id}: {f.revision_note}" for f in restated]]
    return "\n".join(lines)


def _metrics(pack: EvidencePack) -> str:
    if not pack.metrics:
        return ""
    lines = ["## Computed metrics", "", "| ID | Metric | Value | As of | Formula |",
             "|---|---|---|---|---|"]
    for m in pack.metrics:
        value = format_value(m.value, m.unit) + (f" ({m.detail})" if m.detail else "")
        lines.append(f"| {m.evidence_id} | {m.label} | {value} | {m.as_of} | {m.formula} |")
    return "\n".join(lines)


def _catalysts(pack: EvidencePack) -> str:
    lines: list[str] = []
    if pack.announcements:
        lines += ["## Disclosures and catalysts", ""]
        lines += [f"- **{a.published_at:%Y-%m-%d}** {a.category}: {a.summary} "
                  f"[{a.evidence_id}]" + (f" ([attachment]({a.attachment_url}))"
                                         if a.attachment_url else "")
                  for a in pack.announcements]
    if pack.shareholding:
        lines += ["", "**Shareholding**", ""]
        lines += [f"- {s.period_end}: promoter group {s.promoter_pct}%, public "
                  f"{s.public_pct}% [{s.evidence_id}]" for s in pack.shareholding]
    if pack.news:
        lines += ["", "**News headlines** (discovery only)", ""]
        lines += [f"- {n.published_at:%Y-%m-%d} [{n.title}]({n.url}) — {n.domain} "
                  f"[{n.evidence_id}]" for n in pack.news]
    return "\n".join(lines)


def _analysts(report: ResearchReport) -> str:
    if not report.analyst_reports:
        return ""
    lines = ["## Analyst reports"]
    for a in report.analyst_reports:
        stance = f", stance **{a.stance.value}**" if a.stance else ""
        lines += ["", f"### {a.agent.replace('_', ' ').title()} ({a.status.value}{stance})"]
        if a.status in (AgentStatus.SKIPPED, AgentStatus.FAILED):
            lines.append(f"_{a.error}_")
            continue
        lines.append(a.summary)
        for c in a.claims:
            flag = {ClaimStatus.SUPPORTED: "", ClaimStatus.NEEDS_REVIEW: " _(needs review)_",
                    ClaimStatus.UNSUPPORTED: " ~~unsupported~~"}[c.status]
            lines.append(f"- `{c.claim_id}` {c.statement} {_cite(c.evidence_ids, c.statement)}"
                         f"{flag}".replace("  ", " "))
        if a.gaps:
            lines.append("- Gaps: " + "; ".join(a.gaps))
    return "\n".join(lines)


def _debate(report: ResearchReport) -> str:
    if not report.debate:
        return ""
    lines = ["## Bull and bear debate"]
    for t in report.debate:
        lines += ["", f"### {t.side.title()} {t.phase} (turn {t.turn_index})"]
        if t.status == AgentStatus.FAILED:
            lines.append(f"_{t.error}_")
            continue
        lines.append(t.thesis)
        lines += [f"- `{c.claim_id}` {c.statement} {_cite(c.evidence_ids, c.statement)}".rstrip()
                  for c in t.claims if c.status != ClaimStatus.UNSUPPORTED]
        lines += [f"- Challenges `{ch.target_claim_id}` ({ch.dispute}): {ch.argument}"
                  for ch in t.challenges]
        if t.falsifiers:
            lines.append("- Falsifiers: " + "; ".join(t.falsifiers))
    return "\n".join(lines)


def _full_mode(report: ResearchReport) -> str:
    lines: list[str] = []
    decision = report.research_decision
    if decision:
        lines += ["## Research manager", f"Stronger side: **{decision.stronger_side}**, "
                  f"assessment {decision.assessment.value}.", "", decision.rationale]
        if decision.unresolved:
            lines += ["", "Unresolved: " + "; ".join(decision.unresolved)]
    plan = report.trader_plan
    if plan:
        lines += ["", "## Trader (hypothetical plan, no orders)", f"Stance: **{plan.stance}**"]
        lines += [f"- Condition: {c}" for c in plan.conditions_to_consider]
        lines += [f"- Invalidation: {c}" for c in plan.invalidation]
        lines += [f"- Scenario _{s.name}_: {s.description}" for s in plan.scenarios]
    if report.risk_reviews:
        lines += ["", "## Risk team"]
        for r in report.risk_reviews:
            lines += [f"- **{r.perspective}** ({r.verdict}): {r.rationale}"]
            lines += [f"  - {o}" for o in r.objections]
    return "\n".join(lines)


def _conditions(report: ResearchReport) -> str:
    s = report.final_synthesis
    if not s:
        return ""
    lines = ["## What would change the conclusion"]
    for title, items in (("Strengthen if", s.strengthen_if), ("Weaken if", s.weaken_if),
                         ("Invalidate if", s.invalidate_if), ("Unresolved", s.unresolved)):
        if items:
            lines += ["", f"**{title}**", *[f"- {i}" for i in items]]
    return "\n".join(lines)


def _appendix(report: ResearchReport) -> str:
    lines = ["## Appendix"]
    if report.notes:
        lines += ["", "**Run notes**", *[f"- {n}" for n in report.notes]]
    if report.model_calls:
        lines += ["", "**Model calls**", "", "| Node | Model served | Status | Tokens in/out | "
                  "Cost |", "|---|---|---|---|---|"]
        lines += [f"| {c.node} | {c.served_model or c.requested_model} | {c.status} | "
                  f"{c.prompt_tokens or '-'}/{c.completion_tokens or '-'} | {c.cost or 0} |"
                  for c in report.model_calls]
    pack = report.pack
    if pack and pack.facts:
        sources = sorted({(f.source.url, f.filed_at) for f in pack.facts if f.source.url},
                         key=lambda s: s[1], reverse=True)
        lines += ["", "**Filings used**", *[f"- {d:%Y-%m-%d}: {u}" for u, d in sources]]
    lines += ["", "**Limitations**", *[f"- {item}" for item in report.limitations]]
    return "\n".join(lines)


def _cite(ids: list[str], text: str = "") -> str:
    """Citation suffix, omitted when the text already cites every ID inline."""
    if ids and all(f"[{i}]" in text for i in ids):
        return ""
    return f"[{', '.join(ids)}]" if ids else "[no citation]"
