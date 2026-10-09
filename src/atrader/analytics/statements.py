"""Comparable annual statement analytics. Missing inputs never become zero.

Industrial ratios are excluded for bank/NBFC taxonomies. Scenario parameters are
explicit analytical assumptions, not forecasts or empirically calibrated weights.
"""

from collections.abc import Sequence
from datetime import timedelta
from itertools import pairwise
from statistics import median

from atrader.contracts import DerivedMetric, FinancialFact

OCF = "CashFlowsFromUsedInOperatingActivities"
PPE = "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"
INTANGIBLES = "PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities"


def statement_metrics(facts: Sequence[FinancialFact]) -> list[DerivedMetric]:  # noqa: PLR0912, PLR0915
    entity = [
        f
        for f in facts
        if not f.dimensions
        and f.value is not None
        and f.value.is_finite()
        and f.unit in {"INR", "pure"}
    ]
    if len({(f.isin, f.basis) for f in entity}) != 1:
        return []
    annual = [
        f
        for f in entity
        if f.duration == "annual"
        and f.period_start
        and 355 <= (f.period_end - f.period_start).days <= 375
    ]
    years = sorted({f.period_end for f in annual}, reverse=True)[:6]
    if not years:
        return []
    bank = any(f.metric == "InterestExpended" for f in entity)
    lender = bank or any(f.metric == "Loans" for f in entity)
    out: list[DerivedMetric] = []

    def emit(
        name: str,
        label: str,
        value: float,
        unit: str,
        inputs: list[FinancialFact],
        formula: str,
        category: str = "capital",
        flags: tuple[str, ...] = (),
    ) -> None:
        out.append(
            DerivedMetric(
                name=name,
                label=label,
                value=round(value, 4),
                unit=unit,
                as_of=max(f.period_end for f in inputs),
                formula=formula,
                inputs=tuple(dict.fromkeys(f.evidence_id for f in inputs)),
                category=category,
                quality_flags=flags,
            )
        )

    cash_years: list[tuple[FinancialFact, FinancialFact]] = []
    returns: list[tuple[float, float, list[FinancialFact]]] = []
    margins: list[tuple[float, list[FinancialFact]]] = []
    for end in years:
        period = [f for f in annual if f.period_end == end]
        starts = {f.period_start for f in period}
        if len(starts) != 1:
            continue
        start = period[0].period_start
        assert start is not None
        instant = [f for f in entity if f.duration == "instant" and f.period_end == end]
        opening = [
            f
            for f in entity
            if f.duration == "instant" and f.period_end == start - timedelta(days=1)
        ]

        def get(name: str, pool: list[FinancialFact] = period) -> FinancialFact | None:
            expected = (
                "pure"
                if name
                in {"PercentageOfGrossNpa", "PercentageOfNpa", "CET1Ratio", "AdditionalTier1Ratio"}
                else "INR"
            )
            matches = [f for f in pool if f.metric == name and f.unit == expected]
            return matches[0] if len(matches) == 1 else None

        def val(f: FinancialFact) -> float:
            assert f.value is not None
            return float(f.value)

        def ratio(
            name: str,
            label: str,
            num: FinancialFact | None,
            den: FinancialFact | None,
            *,
            percent: bool = False,
        ) -> None:
            if num is not None and den is not None and val(den) > 0:
                emit(
                    f"{name}_{num.period_end}",
                    f"{label}, FY ended {num.period_end}",
                    val(num) / val(den) * (100 if percent else 1),
                    "%" if percent else "x",
                    [num, den],
                    f"{num.metric} / {den.metric}" + (" * 100" if percent else ""),
                )

        pat = get("ProfitLossForPeriod") or get("ProfitLossForThePeriod")
        for tag, label in (
            ("DividendsPaidClassifiedAsFinancingActivities", "Cash dividends paid"),
            ("PaymentsToAcquireOrRedeemEntitysShares", "Cash buybacks / share redemptions"),
            ("ProceedsFromIssuingSharesClassifiedAsFinancingActivities", "Cash equity issuance"),
            (
                "CashFlowsUsedInObtainingControlOfSubsidiariesOrOtherBusinessesClassifiedAsInvestingActivities",
                "Cash spent acquiring businesses",
            ),
            ("ExceptionalItemsBeforeTax", "Reported exceptional items before tax"),
        ):
            item = get(tag)
            if item:
                emit(
                    f"allocation_{tag}_{end}",
                    f"{label}, FY ended {end}",
                    val(item),
                    "INR",
                    [item],
                    "reported annual cash flow / statement item",
                    flags=("classification follows filing; absence is unknown, not zero",),
                )
        assets, prior_assets = get("Assets", instant), get("Assets", opening)
        if pat and assets and prior_assets and val(assets) + val(prior_assets) > 0:
            emit(
                f"roa_{end}",
                f"Return on average assets, FY ended {end}",
                200 * val(pat) / (val(assets) + val(prior_assets)),
                "%",
                [pat, assets, prior_assets],
                "annual profit / average opening and closing assets * 100",
            )
        if lender:
            loans = get("Advances", instant) or get("Loans", instant)
            ratio("loan_deposit", "Loans / deposits", loans, get("Deposits", instant))
            ratio(
                "credit_provision_proxy",
                "Provisions / closing loans (not pure credit cost)",
                get("ProvisionsOtherThanTaxAndContingencies")
                or get("ImpairmentOnFinancialInstruments"),
                loans,
                percent=True,
            )
            for name in (
                "PercentageOfGrossNpa",
                "PercentageOfNpa",
                "CET1Ratio",
                "AdditionalTier1Ratio",
            ):
                f = get(name)
                if f and 0 < val(f) <= 1:
                    emit(
                        f"bank_{name}_{end}",
                        f"{f.label}, FY ended {end}",
                        val(f) * 100,
                        "%",
                        [f],
                        "reported fractional ratio * 100",
                        "resilience",
                        ("zero/absent filer ratios are not interpreted as financial strength",),
                    )
            continue

        revenue, ocf = get("RevenueFromOperations"), get(OCF)
        ratio("cash_conversion", "Operating cash flow / net profit", ocf, pat)
        ratio(
            "receivables_sales",
            "Closing current receivables / annual sales",
            get("TradeReceivablesCurrent", instant),
            revenue,
            percent=True,
        )
        ratio(
            "inventory_sales",
            "Closing inventory / annual sales",
            get("Inventories", instant),
            revenue,
            percent=True,
        )
        ratio(
            "current_ratio",
            "Current assets / current liabilities",
            get("CurrentAssets", instant),
            get("CurrentLiabilities", instant),
        )
        if ocf and pat:
            cash_years.append((ocf, pat))
        capex, intangible = get(PPE), get(INTANGIBLES)
        if ocf and capex and intangible and val(capex) >= 0 and val(intangible) >= 0:
            emit(
                f"fcf_after_total_capex_{end}",
                f"Cash flow after total capex, FY ended {end}",
                val(ocf) - val(capex) - val(intangible),
                "INR",
                [ocf, capex, intangible],
                "operating cash flow - PPE purchases - intangible purchases",
                flags=(
                    "total capex is not maintenance capex; interest classification varies",
                ),
            )
        pbt, finance, tax = get("ProfitBeforeTax"), get("FinanceCosts"), get("TaxExpense")
        debt_current, debt_long = (
            get("BorrowingsCurrent", instant),
            get("BorrowingsNoncurrent", instant),
        )
        cash, equity = get("CashAndCashEquivalents", instant), get("Equity", instant)
        if pbt and finance and val(finance) > 0:
            emit(
                f"interest_coverage_{end}",
                f"EBIT / finance costs, FY ended {end}",
                (val(pbt) + val(finance)) / val(finance),
                "x",
                [pbt, finance],
                "(profit before tax + finance costs) / finance costs",
                "resilience",
            )
        if debt_current and debt_long and cash:
            debt = val(debt_current) + val(debt_long)
            emit(
                f"net_borrowings_{end}",
                f"Borrowings less cash, {end}",
                debt - val(cash),
                "INR",
                [debt_current, debt_long, cash],
                "current borrowings + noncurrent borrowings - cash equivalents",
                "resilience",
                ("excludes leases, guarantees and restricted-cash adjustments",),
            )
            if pbt and finance and revenue and val(revenue) > 0:
                ebit = val(pbt) + val(finance)
                stressed = val(revenue) * 0.85 * (ebit / val(revenue) - 0.03)
                cost = val(finance) + debt * 0.03
                if cost > 0:
                    emit(
                        f"joint_stress_coverage_{end}",
                        f"Joint stress interest coverage, {end}",
                        stressed / cost,
                        "x",
                        [revenue, pbt, finance, debt_current, debt_long],
                        "revenue * 0.85 * (EBIT margin - 0.03) / "
                        "(finance costs + borrowings * 0.03)",
                        "resilience",
                        (
                            "scenario: demand -15%, margin -3pp, all borrowings reprice +3pp",
                            "not a default probability; maturities and floating share unknown",
                        ),
                    )
        if pbt and finance and revenue and val(revenue) > 0:
            margins.append(
                ((val(pbt) + val(finance)) / val(revenue) * 100, [pbt, finance, revenue])
            )
        opening_parts = [
            get(n, opening)
            for n in (
                "Equity",
                "BorrowingsCurrent",
                "BorrowingsNoncurrent",
                "CashAndCashEquivalents",
            )
        ]
        closing_parts = [equity, debt_current, debt_long, cash]
        if (
            pbt
            and finance
            and tax
            and val(pbt) > 0
            and 0 <= val(tax) / val(pbt) <= 0.5
            and all(f is not None for f in opening_parts + closing_parts)
        ):
            parts = [f for f in opening_parts + closing_parts if f is not None]
            ic_open = sum(val(f) for f in parts[:3]) - val(parts[3])
            ic_close = sum(val(f) for f in parts[4:7]) - val(parts[7])
            nopat = (val(pbt) + val(finance)) * (1 - val(tax) / val(pbt))
            if ic_open > 0 and ic_close > 0:
                inputs = [pbt, finance, tax, *parts]
                emit(
                    f"roic_proxy_{end}",
                    f"Return on invested-capital proxy, FY ended {end}",
                    200 * nopat / (ic_open + ic_close),
                    "%",
                    inputs,
                    "EBIT * (1 - effective tax rate) / average(equity + borrowings - cash) * 100",
                    flags=("proxy excludes leases and accounting adjustments; not economic ROIC",),
                )
                returns.append((nopat, ic_close, inputs))

    contiguous = all(
        new[0].period_start == old[0].period_end + timedelta(days=1)
        for new, old in pairwise(cash_years[:3])
    )
    if len(cash_years) >= 3 and contiguous:
        selected = cash_years[:3]
        profit = sum(float(p.value or 0) for _, p in selected)
        if profit > 0:
            emit(
                "cash_conversion_3y",
                "Three-year operating cash flow / profit",
                sum(float(c.value or 0) for c, _ in selected) / profit,
                "x",
                [f for pair in selected for f in pair],
                "sum(annual OCF, 3 years) / sum(annual profit, 3 years)",
            )
    if len(returns) >= 4 and returns[0][1] > returns[3][1]:
        latest, old = returns[0], returns[3]
        emit(
            "incremental_return_proxy",
            "Incremental return on capital over reported endpoints",
            100 * (latest[0] - old[0]) / (latest[1] - old[1]),
            "%",
            latest[2] + old[2],
            "change in annual NOPAT / change in closing invested-capital proxy * 100",
            flags=("acquisitions and accounting changes can distort incremental returns",),
        )
    if len(margins) >= 3:
        inputs = [f for _, group in margins for f in group]
        for name, value in (
            ("low", min(v for v, _ in margins)),
            ("median", median(v for v, _ in margins)),
            ("high", max(v for v, _ in margins)),
        ):
            emit(
                f"historical_ebit_margin_{name}",
                f"Historical annual EBIT margin: {name}",
                value,
                "%",
                inputs,
                f"{name}(annual EBIT / revenue) * 100",
                "valuation",
                (f"{len(margins)} reported years; not proof of a complete business cycle",),
            )
    return out
