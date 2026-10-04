"""The signal card: the one-screen answer at the top of every report. Markdown for the
saved file, plain text for the terminal. The full analysis is in the details file."""

from __future__ import annotations

from atrader.analytics.scoring import (
    MAX_ANALYST_ADJUSTMENT,
    MAX_MANAGER_ADJUSTMENT,
    MIN_WEIGHT_COVERED,
    SIGNAL_BANDS,
)
from atrader.contracts import (
    AgentStatus,
    Factor,
    HorizonView,
    Pillar,
    PillarScore,
    PriceRange,
    Reason,
    ResearchReport,
    Scorecard,
)
from atrader.formatting import indian_grouping, rupees

EXPERIMENTAL = ("Experimental: the scoring rules and weights have not yet been validated "
                "against history. Research, not investment advice.")


def render_card(report: ResearchReport, details_name: str | None = None) -> str:
    card = report.scorecard
    lines = [f"# {_title(report)}", "", _subtitle(report, details_name), "",
             f"> {EXPERIMENTAL}"]
    if card is None:
        lines += ["", "No scorecard: the company's evidence could not be collected."]
        return "\n".join(lines) + "\n"

    lines += ["", *_horizon_table(card)]
    synthesis = report.final_synthesis
    if synthesis and synthesis.status == AgentStatus.COMPLETED and synthesis.summary:
        lines += ["", synthesis.summary]
    lines += ["", "## Scores by area", "", *_pillar_table(card)]

    pros, cons = _pros_cons(report)
    if pros:
        lines += ["", "## Pros", *[f"- {r.statement} {_cite(r)}".rstrip() for r in pros]]
    if cons:
        lines += ["", "## Cons", *[f"- {r.statement} {_cite(r)}".rstrip() for r in cons]]

    lines += ["", "## By horizon"]
    for view in card.horizons:
        lines += ["", *_horizon_section(view)]

    if report.vetoes:
        lines += ["", "## Constraints applied by code"]
        lines += [f"- `{v.severity}` {v.code}: {v.message}" for v in report.vetoes]
    lines += ["", "## How the score works", "", _method()]
    return "\n".join(lines) + "\n"


def render_card_text(report: ResearchReport) -> str:
    """The card for a terminal: aligned columns, no Markdown."""
    card = report.scorecard
    lines = [_title(report) + f"   as of {_cutoff(report)}"]
    if card is None:
        return "\n".join([*lines, "No scorecard: the evidence could not be collected."])
    width = 26
    rows = (
        ("", [h.horizon.label for h in card.horizons]),
        ("Signal", [h.signal.label for h in card.horizons]),
        ("Score", [f"{h.score} / 100" if h.score is not None else "-" for h in card.horizons]),
        ("Confidence", [h.confidence.value for h in card.horizons]),
        ("Price range", [_range_short(h.price_range) for h in card.horizons]),
        ("Driven by", [h.driven_by.label if h.driven_by else "-" for h in card.horizons]),
    )
    lines.append("")
    lines += [f"{label:<14}" + "".join(f"{cell:<{width}}" for cell in cells)
              for label, cells in rows]
    lines.append(f"{'':<14}Ranges: 1M and 6M are typical moves (±1 sd); 2Y is bear / base / bull."
                 " Not forecasts.")
    lines += ["", f"{'Area':<20}{'Score':>5}  {'Conf.':<8}Weight 1M / 6M / 2Y"]
    for p in card.pillars:
        scored = p.score is not None
        score, confidence = (str(p.score), p.confidence.value) if scored else ("-", "-")
        lines.append(f"{p.pillar.label:<20}{score:>5}  {confidence:<8}"
                     f"{_weights(card, p.pillar)}")
    pros, cons = _pros_cons(report)
    if pros:
        lines += ["", "Pros", *[f"  + {r.statement}" for r in pros]]
    if cons:
        lines += ["", "Cons", *[f"  - {r.statement}" for r in cons]]
    flips = [(h.horizon.label, h.up_if[:1], h.down_if[:1]) for h in card.horizons]
    if any(up or down for _, up, down in flips):
        lines += ["", "What would flip it"]
        for label, up, down in flips:
            lines += [f"  {label}: up if {item}" for item in up]
            lines += [f"  {label}: down if {item}" for item in down]
    lines += ["", EXPERIMENTAL]
    return "\n".join(lines)


# --- pieces ---------------------------------------------------------------------------------


def _title(report: ResearchReport) -> str:
    pack = report.pack
    if pack is None:
        return report.request.symbol
    return f"{pack.listing.symbol} · {pack.listing.name}"


def _cutoff(report: ResearchReport) -> str:
    pack = report.pack
    return str(pack.cutoff if pack else report.request.cutoff or "latest")


def _subtitle(report: ResearchReport, details_name: str | None) -> str:
    card = report.scorecard
    kind = ("code-only scorecard" if card and not card.model_adjusted
            else f"{report.request.mode.value} run")
    details = f" · [full analysis]({details_name})" if details_name else ""
    return f"As of {_cutoff(report)} (IST) · {kind} · status {report.status.value}{details}"


def _horizon_table(card: Scorecard) -> list[str]:
    views = card.horizons
    def row(title: str, cells: list[str]) -> str:
        return f"| **{title}** | " + " | ".join(cells) + " |"
    return [
        "| | " + " | ".join(h.horizon.label for h in views) + " |",
        "|---|" + "---|" * len(views),
        row("Signal", [f"**{h.signal.label}**" for h in views]),
        row("Score", [f"{h.score} / 100" if h.score is not None else "—" for h in views]),
        row("Confidence", [h.confidence.value for h in views]),
        row("Price range", [_range_long(h.price_range) for h in views]),
        row("Driven by", [h.driven_by.label if h.driven_by else "—" for h in views]),
    ]


def _pillar_table(card: Scorecard) -> list[str]:
    lines = ["| Area | Score | Confidence | Weight 1M / 6M / 2Y | Main reasons |",
             "|---|---|---|---|---|"]
    for p in card.pillars:
        if p.score is None:
            lines.append(f"| {p.pillar.label} | — | — | {_weights(card, p.pillar)} | "
                         f"not scored: {p.note} |")
            continue
        score = str(p.score)
        if p.adjustment:
            score += f" (code {p.base}, analyst {p.adjustment:+d})"
        lines.append(f"| {p.pillar.label} | {score} | {p.confidence.value} | "
                     f"{_weights(card, p.pillar)} | {_main_reasons(p)} |")
    return lines


def _main_reasons(p: PillarScore) -> str:
    top = [f for f in sorted(p.factors, key=lambda f: -abs(f.points)) if f.points][:2]
    reasons = [f"{f.label} ({f.points:+.0f})" for f in top]
    if p.adjustment and p.adjustment_reason:
        reasons.append(f"analyst: {p.adjustment_reason}")
    return "; ".join(reasons) or "no rule moved the score"


def _weights(card: Scorecard, pillar: Pillar) -> str:
    return " / ".join(str(h.weights[pillar.value]) for h in card.horizons)


def _horizon_section(view: HorizonView) -> list[str]:
    score = f" ({view.score} / 100)" if view.score is not None else ""
    lines = [f"### {view.horizon.label}: {view.signal.label}{score}"]
    if view.score is None:
        lines.append(f"No signal: {view.weight_covered}% of this horizon's weight had a score "
                     f"(at least {MIN_WEIGHT_COVERED}% is needed), or a constraint blocked it.")
    if view.drivers:
        lines.append("Drivers: " + "; ".join(view.drivers))
    if view.up_if:
        lines.append("Signal up if: " + "; ".join(view.up_if))
    if view.down_if:
        lines.append("Signal down if: " + "; ".join(view.down_if))
    if view.manager_adjustment:
        lines.append(f"Portfolio manager adjusted the score {view.manager_adjustment:+d}: "
                     f"{view.manager_reason or 'no reason given'}")
    if view.capped_by:
        lines.append(f"Held at Neutral by: {', '.join(view.capped_by)}")
    if view.price_range:
        lines.append(f"Price range: {_range_long(view.price_range)}. "
                     f"{view.price_range.detail}")
    return [lines[0], *[f"- {line}" for line in lines[1:]]]


def _range_short(value: PriceRange | None) -> str:
    if value is None:
        return "—"
    if value.method == "scenario" and value.base is not None:
        return (f"{rupees(value.low)} / {indian_grouping(round(value.base), 0)} / "
                f"{indian_grouping(round(value.high), 0)}")
    return f"{rupees(value.low)} – {indian_grouping(round(value.high), 0)}"


def _range_long(value: PriceRange | None) -> str:
    if value is not None and value.method == "scenario" and value.base is not None:
        return (f"bear {rupees(value.low)} · base {rupees(value.base)} · "
                f"bull {rupees(value.high)}")
    return _range_short(value)


def _pros_cons(report: ResearchReport) -> tuple[list[Reason], list[Reason]]:
    """The portfolio manager's pros and cons, or, without one, the rules that moved the
    scores most."""
    synthesis = report.final_synthesis
    if synthesis and synthesis.status == AgentStatus.COMPLETED and (synthesis.pros
                                                                     or synthesis.cons):
        return synthesis.pros, synthesis.cons
    card = report.scorecard
    factors: list[Factor] = [f for p in card.pillars for f in p.factors] if card else []
    ranked = sorted(factors, key=lambda f: -abs(f.points))
    def reasons(positive: bool) -> list[Reason]:
        return [Reason(statement=f.label, evidence_ids=f.evidence_ids) for f in ranked
                if (f.points > 0) == positive and f.points][:3]
    return reasons(True), reasons(False)


def _cite(reason: Reason) -> str:
    ids = reason.evidence_ids
    if not ids or all(f"[{i}]" in reason.statement for i in ids):
        return ""
    return f"[{', '.join(ids)}]"


def _method() -> str:
    bands = ", ".join(f"{signal.label} from {floor}" for floor, signal in SIGNAL_BANDS)
    return (
        "Each area starts at 50 (no lean either way). Code rules add or subtract points for "
        "what the metrics show, each citing its evidence. An analyst may move its own area "
        f"by up to ±{MAX_ANALYST_ADJUSTMENT} points with cited evidence; the news area comes "
        "from the news analyst's rated events. Each horizon weights the areas differently "
        "(the weight column above), the portfolio manager may move a horizon by up to "
        f"±{MAX_MANAGER_ADJUSTMENT}, and code constraints can hold a horizon at Neutral or "
        f"withhold the signal. Signal bands: {bands}. A missing area is left out and its "
        "weight shared among the rest; it never counts as 50."
    )
