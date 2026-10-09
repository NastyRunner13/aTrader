"""Explicit revenue/margin/reinvestment DCF sensitivities, not valuation recommendations."""

from collections.abc import Sequence
from datetime import date
from itertools import pairwise
from math import isfinite
from typing import Any

from pydantic import BaseModel, Field, model_validator

from atrader.contracts import DerivedMetric, FinancialFact


class ValuationAssumptions(BaseModel):
    revenue: float = Field(gt=0)
    operating_margin: float = Field(gt=0, lt=1)
    tax_rate: float = Field(ge=0, lt=1)
    return_on_new_capital: float = Field(gt=0, le=1)
    discount_rate: float = Field(gt=0, lt=1)
    terminal_growth: float = Field(ge=0, lt=1)
    years: int = Field(default=5, ge=1, le=15)
    net_debt: float
    equity_value: float = Field(gt=0)
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _valid_terminal(self) -> "ValuationAssumptions":
        if self.terminal_growth >= min(self.discount_rate, self.return_on_new_capital):
            raise ValueError("terminal growth must be below discount rate and incremental return")
        if not all(isfinite(v) for v in self.model_dump().values() if isinstance(v, float)):
            raise ValueError("valuation inputs must be finite")
        return self


def equity_value(a: ValuationAssumptions, growth: float) -> float:
    if not isfinite(growth) or not 0 <= growth < a.return_on_new_capital:
        raise ValueError("growth must be nonnegative and below return on new capital")
    revenue, value = a.revenue, 0.0
    for year in range(1, a.years + 1):
        revenue *= 1 + growth
        nopat = revenue * a.operating_margin * (1 - a.tax_rate)
        cash = nopat * (1 - growth / a.return_on_new_capital)
        value += cash / (1 + a.discount_rate) ** year
    terminal_nopat = revenue * (1 + a.terminal_growth) * a.operating_margin * (1 - a.tax_rate)
    terminal_cash = terminal_nopat * (1 - a.terminal_growth / a.return_on_new_capital)
    return (
        value
        + terminal_cash / (a.discount_rate - a.terminal_growth) / (1 + a.discount_rate) ** a.years
        - a.net_debt
    )


def reverse_valuation(a: ValuationAssumptions) -> dict[str, Any]:
    """Find all bracketed roots: reinvestment can make value non-monotonic in growth."""
    ceiling = min(0.5, a.return_on_new_capital - 1e-6)
    grid = [ceiling * i / 200 for i in range(201)]
    roots = []
    for bounds in pairwise(grid):
        lo, hi = bounds
        left, right = equity_value(a, lo) - a.equity_value, equity_value(a, hi) - a.equity_value
        if left == 0:
            roots.append(lo)
        if left * right >= 0:
            continue
        for _ in range(50):
            mid = (lo + hi) / 2
            value = equity_value(a, mid) - a.equity_value
            if left * value <= 0:
                hi = mid
            else:
                lo, left = mid, value
        roots.append((lo + hi) / 2)
    if equity_value(a, ceiling) == a.equity_value:
        roots.append(ceiling)
    return {
        "assumptions": a.model_dump(),
        "required_growth_rates": roots,
        "search_interval": [0, ceiling],
        "status": "solutions" if roots else "no solution in search interval",
        "scenarios": [
            {
                "growth": g,
                "margin": margin,
                "equity_value": equity_value(a.model_copy(update={"operating_margin": margin}), g),
            }
            for g in (0.0, min(0.05, ceiling), min(0.10, ceiling))
            for margin in (
                max(0.001, a.operating_margin - 0.03),
                a.operating_margin,
                min(0.999, a.operating_margin + 0.03),
            )
        ],
        "limitations": [
            "constant margins and incremental capital returns are assumptions",
            "no probability assigned; no automatic score adjustment",
            "industrial enterprise model is not suitable for banks/NBFCs",
            "compare assumptions to disclosed history; this is not intrinsic-value proof",
        ],
    }


def valuation_metrics(
    facts: Sequence[FinancialFact], metrics: Sequence[DerivedMetric], price: float, price_date: date
) -> list[DerivedMetric]:
    """Report sensitivities only when the industrial input bridge can be reproduced."""
    rows = [f for f in facts if not f.dimensions and f.value is not None and f.value.is_finite()]
    if len({(f.isin, f.basis) for f in rows}) != 1 or any(
        f.metric in {"Loans", "InterestExpended"} for f in rows
    ):
        return []
    revenues = sorted(
        (
            f
            for f in rows
            if f.metric == "RevenueFromOperations" and f.duration == "annual" and f.unit == "INR"
        ),
        key=lambda f: f.period_end,
        reverse=True,
    )
    if not revenues:
        return []
    revenue = revenues[0]
    selected = [revenue]
    for tag in ("ProfitBeforeTax", "FinanceCosts", "TaxExpense"):
        matches = [
            f
            for f in rows
            if f.metric == tag
            and f.unit == "INR"
            and f.period_start == revenue.period_start
            and f.period_end == revenue.period_end
        ]
        if len(matches) != 1:
            return []
        selected += matches
    for tag, unit in (
        ("PaidUpValueOfEquityShareCapital", "INR"),
        ("FaceValueOfEquityShareCapital", "INR/share"),
    ):
        matches = sorted(
            (f for f in rows if f.metric == tag and f.unit == unit),
            key=lambda f: f.period_end,
            reverse=True,
        )
        if not matches:
            return []
        selected.append(matches[0])
    rev, pbt, finance, tax, capital, face = [
        float(f.value) for f in selected if f.value is not None
    ]
    if min(rev, pbt, capital, face) <= 0 or selected[-2].period_end != selected[-1].period_end:
        return []
    by_name = {m.name: m for m in metrics}
    roic = by_name.get(f"roic_proxy_{revenue.period_end}")
    debt = by_name.get(f"net_borrowings_{revenue.period_end}")
    if not roic or roic.value is None or not debt or debt.value is None:
        return []
    inputs = (*(f.evidence_id for f in selected), f"M:{roic.name}", f"M:{debt.name}")
    try:
        a = ValuationAssumptions(
            revenue=rev,
            operating_margin=(pbt + finance) / rev,
            tax_rate=tax / pbt,
            return_on_new_capital=roic.value / 100,
            discount_rate=0.12,
            terminal_growth=0.04,
            net_debt=debt.value,
            equity_value=price * capital / face,
            evidence_ids=list(inputs),
        )
    except ValueError:
        return []
    detail = (
        f"Price {price:g} on {price_date}; shares proxy {capital / face:g} from "
        f"{selected[-1].period_end}; annual revenue {rev:g}, EBIT margin "
        f"{a.operating_margin:.2%}, tax {a.tax_rate:.2%}, reinvestment return "
        f"{a.return_on_new_capital:.2%}, net borrowings {a.net_debt:g}. "
        "Our assumptions: five years, terminal growth 4%; observed capital return "
        "is held constant as the incremental reinvestment return."
    )
    flags = (
        "industrial sensitivity, not a price target; minority/lease adjustments omitted",
        "capital / face value is a shares proxy; later dilution or actions may change shares",
        "reported history is not proof of sustainable margins or future capital returns",
    )
    out = []
    historical = by_name.get("historical_ebit_margin_median")
    if historical and historical.value is not None:
        earnings = (rev * historical.value / 100 - finance) * (1 - a.tax_rate)
        out.append(DerivedMetric(
            name="historical_margin_eps_scenario",
            label="EPS scenario at the historical median EBIT margin",
            value=round(earnings / (capital / face), 4), unit="INR/share", as_of=price_date,
            category="valuation", inputs=(*inputs, f"M:{historical.name}"),
            formula="(latest revenue * historical median EBIT margin - finance costs) "
                    "* (1 - tax rate) / shares proxy",
            detail="Historical margin scenario; reported history may not span a full cycle.",
            quality_flags=flags))
    for discount in (0.10, 0.12, 0.15):
        result = reverse_valuation(a.model_copy(update={"discount_rate": discount}))
        roots = result["required_growth_rates"]
        out.append(
            DerivedMetric(
                name=f"reverse_dcf_growth_{discount:g}",
                label=f"Price-implied annual revenue growth, {discount:.0%} discount rate",
                value=round(roots[0] * 100, 4) if len(roots) == 1 else None,
                unit="%",
                as_of=price_date,
                category="valuation",
                inputs=inputs,
                formula="solve discounted NOPAT * (1 - growth / incremental return) "
                "- net debt = equity value",
                detail=detail + f" Roots in search interval: {roots}; multiple/no roots withheld.",
                quality_flags=flags,
            )
        )
    for i, scenario in enumerate(reverse_valuation(a)["scenarios"]):
        out.append(
            DerivedMetric(
                name=f"dcf_sensitivity_{i}",
                label=f"Value vs price: growth {scenario['growth']:.0%}, "
                f"margin {scenario['margin']:.1%}",
                value=round((scenario["equity_value"] / a.equity_value - 1) * 100, 2),
                unit="%",
                as_of=price_date,
                category="valuation",
                inputs=inputs,
                formula="(scenario equity value / observed equity-value proxy - 1) * 100",
                detail=detail
                + " Discount rate 12%. Negative values mean the scenario is below price.",
                quality_flags=flags,
            )
        )
    return out
