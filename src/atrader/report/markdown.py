"""Render the full analysis behind the signal card as Markdown (docs/01, "Report
structure"). The card itself is in `report.card`."""

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


def render_details(report: ResearchReport, card_name: str | None = None) -> str:
    pack = report.pack
    parts = [_header(report, card_name), _score_breakdown(report)]
    if pack is not None:
        parts += [_coverage(report), _financials(pack), _metrics(pack), _catalysts(pack),
                  _institutional(pack), _research_depth(report)]
    if report.request.mode != Mode.DATA_ONLY:
        parts += [_analysts(report), _debate(report), _risk_team(report), _synthesis(report)]
    parts += [_appendix(report)]
    return "\n\n".join(p for p in parts if p).strip() + "\n"


def _header(report: ResearchReport, card_name: str | None) -> str:
    pack, request = report.pack, report.request
    name = f"{pack.listing.name} ({pack.listing.exchange}: {pack.listing.symbol})" if pack \
        else request.symbol
    card = f"the [signal card]({card_name})" if card_name else "the signal card"
    lines = [
        f"# {name}: full analysis",
        "",
        f"The answer is on {card}; this file shows the work behind it.",
        "",
        "| | |",
        "|---|---|",
        f"| ISIN | {pack.listing.isin if pack else 'unresolved'} |",
        f"| NSE industry | {(pack.industry if pack else None) or 'not classified'} |",
        "| Outlook | 1 month · 6 months · 2 years |",
        f"| Knowledge cutoff | {pack.cutoff if pack else request.cutoff or 'latest'} (IST) |",
        f"| Mode | {request.mode.value} |",
        f"| Status | {report.status.value} |",
        f"| Generated | {report.generated_at:%Y-%m-%d %H:%M} UTC |",
        f"| Evidence pack | `{pack.pack_id if pack else 'none'}` |",
        f"| Run | `{report.run_id}` |",
    ]
    return "\n".join(lines)


def _score_breakdown(report: ResearchReport) -> str:
    card = report.scorecard
    if card is None:
        return ""
    lines = [f"## Score breakdown ({card.version})"]
    for p in card.pillars:
        lines += ["", f"### {p.pillar.label}: "
                  + (f"{p.score} / 100, confidence {p.confidence.value}" if p.score is not None
                     else "not scored")]
        if p.score is not None:
            lines.append("- Starts at 50")
        lines += [f"- {f.points:+.1f} {f'_{f.group}_ ' if f.group else ''}{f.label} "
                  f"{_cite(f.evidence_ids, f.label)}".rstrip() for f in p.factors]
        if p.adjustment:
            lines.append(f"- {p.adjustment:+d} analyst adjustment: {p.adjustment_reason} "
                         f"{_cite(p.adjustment_evidence)}".rstrip())
        if p.note:
            lines.append(f"- Note: {p.note}")
    lines += ["", "### Horizons", "", "| Horizon | Score | Signal | Weight covered | "
              "Manager adjustment | Held by |", "|---|---|---|---|---|---|"]
    lines += [f"| {h.horizon.label} | {h.score if h.score is not None else '—'} | "
              f"{h.signal.label} | {h.weight_covered}% | {h.manager_adjustment:+d} | "
              f"{', '.join(h.capped_by) or '—'} |" for h in card.horizons]
    if card.levels and card.levels.flips:
        lines += ["", "### Signal flips", "", "The next session's close at which each signal "
                  "would change, at average volume with every other input unchanged "
                  f"(searched to ±{card.levels.flips[0].searched_pct:.0f}%).", "",
                  "| Horizon | Direction | Close | Signal there |", "|---|---|---|---|"]
        lines += [f"| {f.horizon.label} | {f.direction} | "
                  f"{format_value(f.price, 'INR/share') if f.price else 'no change'} | "
                  f"{f.signal.label if f.signal else '—'} |" for f in card.levels.flips]
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


def _institutional(pack: EvidencePack) -> str:
    if not pack.institutional_activity:
        return ""
    lines = ["## Institutional cash activity", "",
             "Market-wide activity, not company buying/selling. NSE-only and combined scopes "
             "overlap; do not add them. Provisional and confirmed series remain separate. "
             "Observation times, rather than session dates, bound availability.", "",
             "| ID | Date | Participant | Scope, basis, route | Buys | Sales | Net | Observed |",
             "|---|---|---|---|---|---|---|---|"]
    for row in reversed(pack.institutional_activity):
        lines.append(f"| {row.evidence_id} | {row.session} | {row.participant} | "
                     f"{row.scope} / {row.basis} / {row.route} ({row.date_basis} date) | "
                     f"{format_value(row.purchases_inr, 'INR')} | "
                     f"{format_value(row.sales_inr, 'INR')} | {format_value(row.net_inr, 'INR')} "
                     f"| {row.available_at.isoformat()} |")
    sources = sorted({r.source.url for r in pack.institutional_activity if r.source.url})
    lines += ["", *[f"- [Source]({url})" for url in sources]]
    return "\n".join(lines)


def _research_depth(report: ResearchReport) -> str:  # noqa: PLR0912
    pack = report.pack
    if pack is None:
        return ""
    lines = ["## Business and financial investigations"]
    for analyst in report.analyst_reports:
        for item in analyst.investigations:
            lines += [f"### {item.topic.replace('_', ' ').title()} ({item.status})",
                      f"{item.finding} {_cite(item.evidence_ids)}"]
            if item.mechanism:
                lines.append(f"Mechanism: {item.mechanism}")
            if item.threats:
                lines.append("Threats: " + "; ".join(item.threats))
            if item.missing:
                lines.append("Missing: " + "; ".join(item.missing))
            lines += [f"> {q.quote} [{q.evidence_id}]" for q in item.quotes]
        if analyst.disclosure_terms:
            lines += ["### Disclosed commercial and funding terms",
                      "Missing terms are unknown; new awards are not added to reported backlog."]
        for term in analyst.disclosure_terms:
            lines += [f"- {term.name}: {term.value} [{term.support.evidence_id}]",
                      f"  > {term.support.quote}"]
        if analyst.management_delivery:
            lines += ["### Management promises and outcomes",
                      "Chronology and quotes are checked; assessments remain model judgements."]
        for record in analyst.management_delivery:
            lines += [f"- {record.decision}: {record.assessment}",
                      f"  - Promise: {record.promise.quote} [{record.promise.evidence_id}]",
                      f"  - Outcome: {record.outcome.quote if record.outcome else 'unverified'}"
                      + (f" [{record.outcome.evidence_id}]" if record.outcome else "")]
    if pack.ownership:
        lines += ["## Detailed ownership",
                  "Category totals overlap named holders; do not add them."]
        for row in pack.ownership:
            lines.append(f"- [{row.evidence_id}] {row.period_end}: {row.holder} ({row.level}); "
                         f"shares {row.shares}; ownership {row.ownership_pct}%; "
                         f"pledged {row.pledged_shares}; encumbered {row.encumbered_shares}; "
                         f"source {row.source.url}")
    if pack.corporate_actions:
        lines += ["## Corporate actions used for comparability"]
        for action in pack.corporate_actions:
            lines.append(f"- [{action.evidence_id}] {action.ex_date}: {action.description}; "
                         f"share factor {action.share_factor}; source {action.source.url}")
    if pack.sector_flows:
        lines += ["## Sector FPI investment", "Assets under custody are not net investment."]
        for flow in pack.sector_flows:
            lines.append(f"- [{flow.evidence_id}] {flow.sector}, "
                         f"{flow.period_start}–{flow.period_end}: "
                         f"net equity {format_value(flow.net_equity_inr, 'INR')}; "
                         f"equity AUC {format_value(flow.equity_auc_inr, 'INR')}")
    if pack.documents:
        lines += ["## Document passages"]
        for doc in pack.documents:
            lines += [f"### [{doc.evidence_id}] {doc.title}, page {doc.page}",
                      f"Source: {doc.source.url} (published {doc.source.published_at})", doc.text]
    return "\n\n".join(lines)


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
        lines += [f"- Score adjustment `{x.pillar.value}` {x.points:+d}: {x.reason} "
                  f"{_cite(x.evidence_ids)}".rstrip() for x in a.score_adjustments]
        lines += [f"- Event ({e.materiality}, impact {e.impact:+d}): {e.event} "
                  f"{_cite(e.evidence_ids, e.event)}".rstrip() for e in a.events]
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


def _risk_team(report: ResearchReport) -> str:
    if not report.risk_reviews:
        return ""
    lines = ["## Risk team (reviews of the draft scorecard)"]
    for r in report.risk_reviews:
        lines += [f"- **{r.perspective}** (draft scores {r.verdict}): {r.rationale}"]
        lines += [f"  - {o}" for o in r.objections]
        lines += [f"  - constraint: {c}" for c in r.constraints]
    return "\n".join(lines)


def _synthesis(report: ResearchReport) -> str:
    s = report.final_synthesis
    if not s:
        return ""
    lines = ["## Portfolio manager"]
    if s.summary:
        lines += ["", s.summary]
    if s.pros:
        lines += ["", "**Pros**", *_reasons(s.pros)]
    if s.cons:
        lines += ["", "**Cons**", *_reasons(s.cons)]
    if s.thesis_tests:
        lines += ["", "### Thesis assumptions and failure conditions"]
        for test in s.thesis_tests:
            lines += [f"- Assumption: {test.assumption} {_cite(test.evidence_ids)}",
                      f"  - Invalidated by: {test.invalidated_by}",
                      f"  - Next event: {test.next_event or 'unknown'}"
                      + (f" ({test.next_event_date})" if test.next_event_date
                         else " (date unknown)")
                      + (f" {_cite(test.next_event_evidence_ids)}" if test.next_event else "")]
    for note in s.horizons:
        lines += ["", f"**{note.horizon.label}** (adjustment {note.adjustment:+d}"
                  + (f": {note.adjustment_reason}" if note.adjustment_reason else "") + ")"]
        lines += [f"- Driver: {d}" for d in note.drivers]
        lines += [f"- Up if: {u}" for u in note.up_if]
        lines += [f"- Down if: {d}" for d in note.down_if]
    if s.unresolved:
        lines += ["", "**Unresolved**", *[f"- {u}" for u in s.unresolved]]
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
