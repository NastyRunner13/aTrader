"""Fundamental and valuation metrics computed from reported facts.

Every metric names the evidence IDs it was computed from. Comparisons only use the
same statement basis and the same period length. A metric that cannot be computed
is omitted rather than estimated.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from atrader.contracts import DerivedMetric, FinancialFact, StatementBasis

REVENUE = "RevenueFromOperations"
PBT = "ProfitBeforeTax"
OTHER_INCOME = "OtherIncome"
PAT = "ProfitLossForPeriod"
PAT_OWNERS = "ProfitOrLossAttributableToOwnersOfParent"
EPS = "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"
PAID_UP = "PaidUpValueOfEquityShareCapital"
FACE_VALUE = "FaceValueOfEquityShareCapital"


class _Quarters:
    """Quarter facts indexed by (metric, period_end)."""

    def __init__(self, facts: list[FinancialFact]) -> None:
        self._facts = {(f.metric, f.period_end): f for f in facts
                       if f.duration == "quarter" and f.value is not None}
        self.periods = sorted({f.period_end for f in facts if f.duration == "quarter"},
                              reverse=True)

    def get(self, metric: str, period_end: date) -> FinancialFact | None:
        return self._facts.get((metric, period_end))

    def year_ago(self, period_end: date) -> date | None:
        return next((p for p in self.periods
                     if p.month == period_end.month and p.year == period_end.year - 1), None)


def fundamental_metrics(facts: list[FinancialFact], last_close: float | None,
                        close_as_of: date | None) -> list[DerivedMetric]:
    quarter_facts = [f for f in facts if f.duration == "quarter"]
    if not quarter_facts:
        return []
    quarters = _Quarters(quarter_facts)
    latest = quarters.periods[0]
    basis = quarter_facts[0].basis
    pat_metric = PAT_OWNERS if basis == StatementBasis.CONSOLIDATED and quarters.get(
        PAT_OWNERS, latest) else PAT
    out: list[DerivedMetric] = []
    suffix = f"{basis.value}, quarter ended {latest.isoformat()}"

    def ratio(name: str, label: str, num: FinancialFact | None, den: FinancialFact | None,
              formula: str, *, growth: bool = False) -> None:
        if num is None or den is None or num.value is None or not den.value:
            return
        value = (num.value / den.value - 1) if growth else num.value / den.value
        if growth and den.value < 0:
            return  # growth from a negative base is not meaningful
        out.append(DerivedMetric(
            name=name, label=f"{label} ({suffix})", value=round(float(value * 100), 2),
            unit="%", as_of=latest, formula=formula,
            inputs=(num.evidence_id, den.evidence_id),
        ))

    year_ago = quarters.year_ago(latest)
    previous = quarters.periods[1] if len(quarters.periods) > 1 else None
    if year_ago:
        ratio("revenue_yoy", "Revenue growth YoY", quarters.get(REVENUE, latest),
              quarters.get(REVENUE, year_ago), "revenue_q / revenue_q_year_ago - 1", growth=True)
        ratio("profit_yoy", "Net profit growth YoY", quarters.get(pat_metric, latest),
              quarters.get(pat_metric, year_ago), "profit_q / profit_q_year_ago - 1", growth=True)
    if previous:
        ratio("revenue_qoq", "Revenue growth QoQ", quarters.get(REVENUE, latest),
              quarters.get(REVENUE, previous), "revenue_q / revenue_prev_q - 1", growth=True)
    ratio("pbt_margin", "Profit-before-tax margin", quarters.get(PBT, latest),
          quarters.get(REVENUE, latest), "pbt / revenue")
    ratio("net_margin", "Net profit margin", quarters.get(pat_metric, latest),
          quarters.get(REVENUE, latest), "profit / revenue")
    ratio("other_income_share", "Other income as share of PBT", quarters.get(OTHER_INCOME, latest),
          quarters.get(PBT, latest), "other_income / pbt")
    if year_ago:
        out.extend(_margin_change(quarters, latest, year_ago, suffix))

    out.extend(_valuation(quarters, latest, facts, last_close, close_as_of))
    return out


def _margin_change(quarters: _Quarters, latest: date, year_ago: date,
                   suffix: str) -> list[DerivedMetric]:
    """Pre-tax margin now minus the same quarter a year earlier, in percentage points."""
    pbt, revenue = quarters.get(PBT, latest), quarters.get(REVENUE, latest)
    pbt_before, revenue_before = quarters.get(PBT, year_ago), quarters.get(REVENUE, year_ago)
    if not (pbt and revenue and pbt_before and revenue_before):
        return []
    if pbt.value is None or pbt_before.value is None or not revenue.value \
            or not revenue_before.value:
        return []
    change = (pbt.value / revenue.value - pbt_before.value / revenue_before.value) * 100
    return [DerivedMetric(
        name="pbt_margin_change_yoy", label=f"Change in PBT margin YoY ({suffix})",
        value=round(float(change), 2), unit="pp", as_of=latest,
        formula="pbt / revenue - pbt_year_ago / revenue_year_ago",
        inputs=(pbt.evidence_id, revenue.evidence_id, pbt_before.evidence_id,
                revenue_before.evidence_id),
    )]


def _valuation(quarters: _Quarters, latest: date, facts: list[FinancialFact],
               last_close: float | None, close_as_of: date | None) -> list[DerivedMetric]:
    if last_close is None or close_as_of is None:
        return []
    out: list[DerivedMetric] = []
    last_four = quarters.periods[:4]
    eps = [quarters.get(EPS, p) for p in last_four]
    consecutive = len(last_four) == 4 and (last_four[0] - last_four[3]).days < 300
    if consecutive and all(e is not None and e.value is not None for e in eps):
        ttm_eps = sum((e.value for e in eps if e and e.value is not None), Decimal(0))
        ids = tuple(e.evidence_id for e in eps if e)
        out.append(DerivedMetric(
            name="eps_ttm", label="Basic EPS, trailing four quarters", value=float(ttm_eps),
            unit="INR/share", as_of=latest, formula="sum(basic EPS, last 4 quarters)", inputs=ids,
            category="valuation",
        ))
        if ttm_eps > 0:
            out.append(DerivedMetric(
                name="pe_ttm", label="Price / trailing EPS",
                value=round(last_close / float(ttm_eps), 2),
                unit="x", as_of=close_as_of, formula="last close / eps_ttm",
                inputs=(*ids, "M:close"), category="valuation",
                quality_flags=("price and EPS dates differ",) if close_as_of > latest else (),
            ))

    paid_up = _latest(facts, PAID_UP)
    face = _latest(facts, FACE_VALUE)
    if paid_up and face and paid_up.value and face.value:
        shares = float(paid_up.value / face.value)
        out.append(DerivedMetric(
            name="market_cap", label="Market capitalisation (approx.)", value=shares * last_close,
            unit="INR", as_of=close_as_of, formula="(paid-up capital / face value) * last close",
            inputs=(paid_up.evidence_id, face.evidence_id, "M:close"), category="valuation",
            quality_flags=("share count derived from paid-up capital at period end; treasury "
                           "shares and later allotments not reflected",),
        ))
    return out


def _latest(facts: list[FinancialFact], metric: str) -> FinancialFact | None:
    candidates = [f for f in facts if f.metric == metric and f.value is not None]
    return max(candidates, key=lambda f: f.period_end, default=None)
