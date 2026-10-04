"""Deterministic risk and evidence vetoes (docs/04, debate rule 8).

Vetoes are computed from the frozen evidence pack only, so the same pack always
yields the same constraints. They are shown to the synthesizer as context and then
enforced on its assessment in code.
"""

from __future__ import annotations

from atrader.contracts import Assessment, Coverage, EvidencePack, Veto

STALE_PRICE_DAYS = 7
STALE_RESULTS_DAYS = 200
MIN_SESSIONS_FOR_TECHNICALS = 60
MIN_MEDIAN_TURNOVER_INR = 5e7  # ₹5 crore per day


def compute_vetoes(pack: EvidencePack) -> list[Veto]:
    vetoes: list[Veto] = []
    if not pack.has_core_evidence:
        vetoes.append(Veto(code="no_core_evidence", severity="block",
                           message="Neither price history nor reported financials are available."))
        return vetoes

    if pack.bars:
        age = (pack.cutoff - pack.bars[-1].session).days
        if age > STALE_PRICE_DAYS:
            vetoes.append(Veto(code="stale_prices", severity="cap",
                               message=f"Last price bar is {age} days before the cutoff."))
        if len(pack.bars) < MIN_SESSIONS_FOR_TECHNICALS:
            vetoes.append(Veto(code="short_price_history", severity="cap",
                               message=f"Only {len(pack.bars)} sessions of price history."))
        if any(b.adjustment == "split_bonus_adjusted" for b in pack.bars):
            vetoes.append(Veto(code="inferred_price_adjustment", severity="note",
                               message="Earlier prices were adjusted using factors inferred from "
                                       "the exchange's published previous close."))
    else:
        vetoes.append(Veto(code="no_price_data", severity="cap",
                           message="No price history; technical and valuation views are absent."))

    if pack.facts:
        latest_period = max(f.period_end for f in pack.facts)
        age = (pack.cutoff - latest_period).days
        if age > STALE_RESULTS_DAYS:
            vetoes.append(Veto(code="stale_results", severity="cap",
                               message=f"Latest reported period ended {age} days before the "
                                       "cutoff."))
        latest = [f for f in pack.facts if f.period_end == latest_period]
        if latest and all(f.audited is False for f in latest):
            vetoes.append(Veto(code="unaudited_latest", severity="note",
                               message="Latest results are unaudited (limited review)."))
    else:
        vetoes.append(Veto(code="no_reported_financials", severity="cap",
                           message="No reported financial results in the evidence pack."))

    turnover = next((m for m in pack.metrics if m.name == "median_turnover20"), None)
    if turnover and turnover.value is not None and turnover.value < MIN_MEDIAN_TURNOVER_INR:
        vetoes.append(Veto(code="low_liquidity", severity="cap",
                           message=f"Median daily traded value is ₹{turnover.value / 1e7:.2f} "
                                   "crore, below the ₹5 crore liquidity floor."))

    blocked = [c.category for c in pack.coverage if c.status == Coverage.ACCESS_BLOCKED]
    if blocked:
        vetoes.append(Veto(code="sources_blocked", severity="note",
                           message="Sources unavailable this run: " + ", ".join(blocked)))
    return vetoes


def enforce(assessment: Assessment, vetoes: list[Veto]) -> Assessment:
    """Apply vetoes to an assessment. Blocks win over caps; caps only lower `supportive`."""
    if any(v.severity == "block" for v in vetoes):
        return Assessment.INSUFFICIENT_EVIDENCE
    if assessment == Assessment.SUPPORTIVE and any(v.severity == "cap" for v in vetoes):
        return Assessment.MIXED
    return assessment
