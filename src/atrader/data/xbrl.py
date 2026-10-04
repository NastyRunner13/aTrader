"""Parser for Indian exchange financial-results XBRL (SEBI Reg. 33 / Integrated Filing).

Values in these filings are already in base units (rupees); `decimals` only records
the precision the filer rounded to (e.g. -7 for crores). Period identity comes from
each fact's context dates, never from context names like `OneD`.

P0 keeps entity-level (non-dimensional) facts. Segment facts carry an explicit XBRL
dimension and are left for the segment-exposure work (F07).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal
from xml.etree.ElementTree import Element  # typing only; parsing uses defusedxml

from defusedxml import ElementTree

from atrader.contracts import StatementBasis

_XBRLI = "{http://www.xbrl.org/2003/instance}"

Duration = Literal["quarter", "half_year", "nine_months", "annual", "instant", "other"]

# Curated labels for the line items analysts read first. Anything else keeps its
# element name split into words.
KEY_LABELS: dict[str, str] = {
    "RevenueFromOperations": "Revenue from operations",
    "OtherIncome": "Other income",
    "Income": "Total income",
    "Expenses": "Total expenses",
    "CostOfMaterialsConsumed": "Cost of materials consumed",
    "EmployeeBenefitExpense": "Employee benefit expense",
    "FinanceCosts": "Finance costs",
    "DepreciationDepletionAndAmortisationExpense": "Depreciation and amortisation",
    "ProfitBeforeExceptionalItemsAndTax": "Profit before exceptional items and tax",
    "ExceptionalItemsBeforeTax": "Exceptional items",
    "ProfitBeforeTax": "Profit before tax",
    "TaxExpense": "Tax expense",
    "ProfitLossForPeriod": "Net profit for the period",
    "ProfitOrLossAttributableToOwnersOfParent": "Net profit attributable to owners",
    "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations": "Basic EPS",
    "DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations": "Diluted EPS",
    "PaidUpValueOfEquityShareCapital": "Paid-up equity share capital",
    "FaceValueOfEquityShareCapital": "Face value per share",
}
# Filer-computed ratios (DebtEquityRatio, DebtServiceCoverageRatio, ...) are left out:
# definitions vary by filer and sampled values were implausible. Leverage will be
# computed from balance-sheet facts instead.

_UNIT_NAMES = {"INR": "INR", "INRPerShare": "INR/share", "pure": "pure", "shares": "shares"}
_META = {
    "NatureOfReportStandaloneConsolidated",
    "WhetherResultsAreAuditedOrUnaudited",
    "LevelOfRoundingUsedInFinancialStatements",
    "DescriptionOfPresentationCurrency",
    "Symbol",
    "NameOfTheCompany",
    "DateOfStartOfReportingPeriod",
    "DateOfEndOfReportingPeriod",
}


class XbrlParseError(ValueError):
    pass


@dataclass(frozen=True)
class XbrlFact:
    metric: str
    label: str
    value: Decimal
    unit: str
    period_start: date | None
    period_end: date
    duration: Duration


@dataclass
class ParsedResults:
    symbol: str | None
    company: str | None
    basis: StatementBasis | None
    audited: bool | None
    rounding: str | None
    currency: str | None
    reporting_period: tuple[date, date] | None
    facts: list[XbrlFact] = field(default_factory=list)


@dataclass(frozen=True)
class _Context:
    start: date | None
    end: date
    instant: bool
    dimensional: bool


def parse_results_xbrl(content: bytes) -> ParsedResults:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise XbrlParseError(f"invalid XML: {exc}") from exc

    contexts = _contexts(root)
    meta: dict[str, str] = {}
    facts: list[XbrlFact] = []
    for element in root:
        tag = element.tag
        if not isinstance(tag, str) or tag.startswith(_XBRLI) or "}" not in tag:
            continue
        name = tag.split("}", 1)[1]
        context = contexts.get(element.get("contextRef", ""))
        text = (element.text or "").strip()
        if context is None or not text:
            continue
        unit_ref = element.get("unitRef")
        if unit_ref is None:
            if name in _META and not context.dimensional:
                meta.setdefault(name, text)
            continue
        if context.dimensional:
            continue
        try:
            value = Decimal(text)
        except InvalidOperation:
            continue
        facts.append(XbrlFact(
            metric=name,
            label=KEY_LABELS.get(name, _words(name)),
            value=value,
            unit=_UNIT_NAMES.get(unit_ref, unit_ref),
            period_start=None if context.instant else context.start,
            period_end=context.end,
            duration="instant" if context.instant else _duration(context.start, context.end),
        ))

    return ParsedResults(
        symbol=meta.get("Symbol"),
        company=meta.get("NameOfTheCompany"),
        basis=_basis(meta.get("NatureOfReportStandaloneConsolidated")),
        audited=_audited(meta.get("WhetherResultsAreAuditedOrUnaudited")),
        rounding=meta.get("LevelOfRoundingUsedInFinancialStatements"),
        currency=meta.get("DescriptionOfPresentationCurrency"),
        reporting_period=_period(meta),
        facts=_deduplicate(facts),
    )


def _contexts(root: Element) -> dict[str, _Context]:
    contexts: dict[str, _Context] = {}
    for ctx in root.iter(f"{_XBRLI}context"):
        period = ctx.find(f"{_XBRLI}period")
        if period is None:
            continue
        instant = period.findtext(f"{_XBRLI}instant")
        start = period.findtext(f"{_XBRLI}startDate")
        end = period.findtext(f"{_XBRLI}endDate")
        dimensional = (ctx.find(f"{_XBRLI}scenario") is not None
                       or ctx.find(f".//{_XBRLI}segment") is not None)
        try:
            if instant:
                contexts[ctx.get("id", "")] = _Context(None, date.fromisoformat(instant.strip()),
                                                       True, dimensional)
            elif start and end:
                contexts[ctx.get("id", "")] = _Context(date.fromisoformat(start.strip()),
                                                       date.fromisoformat(end.strip()),
                                                       False, dimensional)
        except ValueError:
            continue
    return contexts


def _duration(start: date | None, end: date) -> Duration:
    if start is None:
        return "other"
    days = (end - start).days + 1
    if 80 <= days <= 100:
        return "quarter"
    if 170 <= days <= 190:
        return "half_year"
    if 260 <= days <= 285:
        return "nine_months"
    if 355 <= days <= 375:
        return "annual"
    return "other"


def _deduplicate(facts: list[XbrlFact]) -> list[XbrlFact]:
    seen: dict[tuple[str, date | None, date, str], XbrlFact] = {}
    for fact in facts:
        seen.setdefault((fact.metric, fact.period_start, fact.period_end, fact.unit), fact)
    return list(seen.values())


def _basis(text: str | None) -> StatementBasis | None:
    if not text:
        return None
    lowered = text.lower()
    if "consolidated" in lowered:
        return StatementBasis.CONSOLIDATED
    if "standalone" in lowered:
        return StatementBasis.STANDALONE
    return None


def _audited(text: str | None) -> bool | None:
    if not text:
        return None
    lowered = text.lower()
    if lowered.startswith("unaudited") or lowered.startswith("un-audited"):
        return False
    if lowered.startswith("audited"):
        return True
    return None


def _period(meta: dict[str, str]) -> tuple[date, date] | None:
    try:
        return (date.fromisoformat(meta["DateOfStartOfReportingPeriod"]),
                date.fromisoformat(meta["DateOfEndOfReportingPeriod"]))
    except (KeyError, ValueError):
        return None


def _words(name: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name).capitalize()
