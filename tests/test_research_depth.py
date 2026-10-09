"""Accounting and source-boundary regression set; no network or model calls."""

import io
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest
from openpyxl import Workbook

from atrader.analytics.institutional import institutional_metrics
from atrader.analytics.metrics import number, pack_metrics
from atrader.analytics.ownership import ownership_metrics
from atrader.analytics.portfolio import PortfolioPosition, portfolio_exposures
from atrader.analytics.statements import statement_metrics
from atrader.analytics.valuation import ValuationAssumptions, equity_value, reverse_valuation
from atrader.contracts import (
    CorporateAction,
    DocumentPassage,
    FinancialFact,
    OwnershipPosition,
    SourceRef,
)
from atrader.contracts.agents import EvidenceQuote, Investigation, ManagementDelivery
from atrader.data.documents import extract_pdf, select_passages
from atrader.data.providers.corporate_actions import parse_actions
from atrader.data.providers.fund_portfolios import parse_fund_workbook
from atrader.data.providers.nsdl import parse_confirmed, parse_sector_report
from atrader.data.providers.ownership import parse_ownership
from atrader.data.store import MarketStore
from atrader.data.xbrl import parse_results_xbrl
from atrader.verification.research import verify_research
from tests.conftest import CUTOFF, LISTING, make_pack

FIXTURES = Path(__file__).parent / "fixtures"
OBSERVED = datetime(2026, 10, 9, 10, tzinfo=UTC)
SOURCE = SourceRef(provider="test", url="https://example.invalid/filing", retrieved_at=OBSERVED)


def statement(name="lt"):
    parsed = parse_results_xbrl((FIXTURES / f"{name}_statement_excerpt.xml").read_bytes())
    return number(
        [
            FinancialFact(
                isin=LISTING.isin,
                metric=f.metric,
                label=f.label,
                value=f.value,
                unit=f.unit,
                period_start=f.period_start,
                period_end=f.period_end,
                duration=f.duration,
                dimensions=f.dimensions,
                basis=parsed.basis,
                filed_at=OBSERVED,
                source=SOURCE,
            )
            for f in parsed.facts
        ],
        "F",
    )


def test_real_industrial_cash_conversion_and_segment_identity():
    facts = statement()
    metrics = {m.name: m for m in pack_metrics([], facts)}
    assert metrics["cash_conversion_2026-03-31"].value == pytest.approx(
        219279500000 / 62871300000, abs=0.0001
    )
    segment = next(m for m in metrics.values()
                   if m.label.startswith("Infrastructure Projects:") and "annual" in m.label)
    assert segment.value == pytest.approx(56857300000 / 1074426200000 * 100, abs=0.0001)
    assert set(segment.inputs) <= {f.evidence_id for f in facts if f.dimensions}
    assert "fcf_after_total_capex_2026-03-31" in metrics
    assert "maintenance capex" in metrics["fcf_after_total_capex_2026-03-31"].quality_flags[0]


def test_opening_capital_roic_joint_stress_and_reverse_dcf_have_resolvable_inputs():
    facts = statement()
    opening = [f.model_copy(update={"period_end": date(2025, 3, 31),
                                   "value": f.value * Decimal("0.8")})
               for f in facts if f.duration == "instant" and not f.dimensions]
    facts = number([*facts, *opening], "F")
    pack = make_pack().model_copy(update={"facts": tuple(facts)})
    metrics = pack_metrics(pack.bars, facts)
    by_name = {m.name: m for m in metrics}
    current = {f.metric: float(f.value) for f in facts if not f.dimensions
               and f.period_end == date(2026, 3, 31) and f.duration != "quarter"}
    ic = (current["Equity"] + current["BorrowingsCurrent"] + current["BorrowingsNoncurrent"]
          - current["CashAndCashEquivalents"])
    nopat = (current["ProfitBeforeTax"] + current["FinanceCosts"]) * (
        1-current["TaxExpense"]/current["ProfitBeforeTax"])
    assert by_name["roic_proxy_2026-03-31"].value == pytest.approx(100*nopat/(ic*.9),abs=.0001)
    debt = current["BorrowingsCurrent"] + current["BorrowingsNoncurrent"]
    stressed = current["RevenueFromOperations"] * .85 * (
        (current["ProfitBeforeTax"]+current["FinanceCosts"])/current["RevenueFromOperations"]-.03)
    assert by_name["joint_stress_coverage_2026-03-31"].value == pytest.approx(
        stressed/(current["FinanceCosts"]+debt*.03),abs=.0001)
    assert len([m for m in metrics if m.name.startswith("dcf_sensitivity_")]) == 9
    known = {f.evidence_id for f in facts} | {m.evidence_id for m in metrics}
    assert all(i in known for m in metrics if m.name.startswith(("reverse_dcf", "dcf_"))
               for i in m.inputs)


@pytest.mark.parametrize("name", ["hdfcbank", "shriramfin"])
def test_lenders_never_get_industrial_cash_or_stress_metrics(name):
    names = {m.name for m in statement_metrics(statement(name))}
    assert not any(
        n.startswith(("cash_conversion", "fcf_", "roic_", "joint_stress")) for n in names
    )
    assert not any("CET1" in n for n in names)  # reported zeros are not capital adequacy proof
    assert any(n.startswith("credit_provision_proxy_") for n in names)
    assert not any(n.startswith("roa_") for n in names)  # opening assets are absent in excerpt


@pytest.mark.parametrize(
    "problem", ["missing", "currency", "basis", "period", "dimension", "duplicate"]
)
def test_incomparable_cash_input_cannot_create_conversion(problem):
    facts = statement()
    ocf = next(
        f
        for f in facts
        if f.metric == "CashFlowsFromUsedInOperatingActivities" and f.duration == "annual"
    )
    if problem == "missing":
        facts.remove(ocf)
    elif problem == "duplicate":
        facts.append(ocf)
    else:
        updates = {
            "currency": {"unit": "USD"},
            "basis": {"basis": "consolidated"},
            "period": {"period_start": date(2025, 5, 1)},
            "dimension": {"dimensions": (("segment", "Other"),)},
        }[problem]
        facts = [f.model_copy(update=updates) if f is ocf else f for f in facts]
    assert "cash_conversion_2026-03-31" not in {m.name for m in statement_metrics(facts)}


def test_ownership_real_fraction_and_named_holder_context_join():
    rows = parse_ownership(
        (FIXTURES / "ownership_excerpt.xml").read_bytes(), "INE018A01030", SOURCE
    )
    category = next(r for r in rows if r.level == "category")
    assert category.shares == 274024354 and category.ownership_pct == pytest.approx(20.1)
    holder = next(r for r in rows if r.holder == "HDFC MUTUAL FUND")
    assert holder.level == "holder" and holder.shares == 29165638
    assert holder.ownership_pct == pytest.approx(2.14)
    with pytest.raises(ValueError, match="different ISIN"):
        parse_ownership((FIXTURES / "ownership_excerpt.xml").read_bytes(), LISTING.isin, SOURCE)


def test_exchange_pledge_and_total_encumbrance_are_distinct_fields():
    rows = parse_ownership((FIXTURES / "pledge_excerpt.xml").read_bytes(), "INE423A01024", SOURCE)
    assert len(rows) == 1
    assert rows[0].pledged_shares == 7_700_000 and rows[0].encumbered_shares == 7_700_000


def position(shares, end, identifier):
    return OwnershipPosition(
        evidence_id=identifier,
        isin=LISTING.isin,
        period_end=end,
        holder="Fund",
        category="Mutual funds",
        level="fund",
        shares=shares,
        available_at=OBSERVED,
        source=SOURCE,
    )


@pytest.mark.parametrize(
    "old,new,factor,expected",
    [(100, 500, 5, 0), (100, 550, 5, 50), (100, 0, 1, -100), (0, 100, 1, 100)],
)
def test_disclosed_quantity_changes_adjust_splits_and_require_explicit_zero(
    old, new, factor, expected
):
    rows = [position(old, date(2026, 3, 31), "H1"), position(new, date(2026, 6, 30), "H2")]
    action = CorporateAction(
        evidence_id="C1",
        symbol="TESTCO",
        ex_date=date(2026, 5, 1),
        description="split",
        share_factor=factor,
        available_at=OBSERVED,
        source=SOURCE,
    )
    metric = ownership_metrics(rows, [action], actions_since=date(2026, 1, 1))[0]
    assert metric.value == expected and metric.inputs == ("H1", "H2", "C1")
    assert ownership_metrics(rows[:1], [action], actions_since=date(2026, 1, 1)) == []
    assert ownership_metrics(rows, [action], actions_since=None)[0].value is None
    assert (
        ownership_metrics(
            rows, [action.model_copy(update={"share_factor": None})], actions_since=date(2026, 1, 1)
        )[0].value
        is None
    )


def test_corporate_action_parser_uses_split_description_not_current_face_value():
    rows = parse_actions(
        b'[{"symbol":"TESTCO","exDate":"10-Jan-2025","faceVal":"1",'
        b'"subject":"Face Value Split (Sub-Division) - From Rs 10/- Per Share '
        b'To Rs 2/- Per Share"}]',
        "TESTCO",
        SOURCE,
    )
    assert rows[0].share_factor == 5
    assert rows[0].available_at == OBSERVED  # never backdate to ex date


def test_fund_workbook_uses_share_quantity_not_nav_weight():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["ISIN", "Quantity", "% to NAV"])
    sheet.append([LISTING.isin, 1500, 3.8])
    content = io.BytesIO()
    workbook.save(content)
    rows = parse_fund_workbook(content.getvalue(), "Fund", CUTOFF, OBSERVED, SOURCE)
    assert rows[0].shares == 1500 and rows[0].ownership_pct is None
    sheet.append([LISTING.isin, 1500, 3.8])
    content = io.BytesIO()
    workbook.save(content)
    with pytest.raises(ValueError, match="duplicate"):
        parse_fund_workbook(content.getvalue(), "Fund", CUTOFF, OBSERVED, SOURCE)


def test_confirmed_routes_rowspans_and_reporting_dates_stay_separate():
    rows = parse_confirmed((FIXTURES / "nsdl_daily_layout.html").read_bytes(), SOURCE)
    assert len(rows) == 2
    assert {r.route for r in rows} == {"stock_exchange", "primary_other"}
    assert all(r.date_basis == "reporting" and r.basis == "confirmed" for r in rows)
    assert rows[0].net_inr == -785.78 * 10_000_000
    assert institutional_metrics(number(rows, "I"), [r.session for r in rows]) == []


def test_sector_net_flow_is_not_change_in_auc():
    rows = parse_sector_report((FIXTURES / "nsdl_sector_layout.html").read_bytes(), SOURCE)
    assert len(rows) == 2
    assert rows[0].net_equity_inr == 3e7 and rows[0].equity_auc_inr == 100e7
    assert rows[1].net_equity_inr == -2e7 and rows[1].equity_auc_inr == 150e7


@pytest.mark.parametrize("kind", [DocumentPassage, OwnershipPosition])
def test_archived_evidence_respects_availability_and_preserves_revisions(tmp_path, kind):
    store = MarketStore(tmp_path / "store.db")
    row = (
        DocumentPassage(title="Report", page=1, text="Original source passage", source=SOURCE)
        if kind is DocumentPassage
        else position(100, CUTOFF, "H1")
    )
    store.save_research_evidence(LISTING.isin, [row])
    assert store.research_evidence(kind, LISTING.isin, CUTOFF) == []
    assert len(store.research_evidence(kind, LISTING.isin, OBSERVED.date())) == 1


def test_pdf_pages_keep_exact_quotes_and_image_only_coverage(monkeypatch):
    pages = [
        Mock(extract_text=lambda: "Customer retention improved. " * 4),
        Mock(extract_text=lambda: ""),
    ]
    monkeypatch.setattr(
        "atrader.data.documents.PdfReader", lambda *a, **kw: Mock(pages=pages, is_encrypted=False)
    )
    rows, gaps = extract_pdf(b"fixture", "Annual report", SOURCE)
    assert rows[0].page == 1 and "competitive_advantage" in rows[0].topics
    assert "page 2" in gaps[0]


@pytest.mark.parametrize("problem", ["none", "fabricated", "wrong_id", "uncited_quote"])
def test_research_quotes_are_exact_and_belong_to_cited_passages(problem):
    doc = DocumentPassage(
        evidence_id="D1",
        title="Report",
        page=2,
        text="Customer retention improved to the highest recorded level.",
        source=SOURCE,
    )
    pack = make_pack().model_copy(update={"documents": (doc,)})
    quote = EvidenceQuote(evidence_id="D1", quote=doc.text)
    ids = ["D1"]
    if problem == "fabricated":
        quote = quote.model_copy(update={"quote": "Fabricated source passage."})
    if problem == "wrong_id":
        quote = quote.model_copy(update={"evidence_id": "D2"})
    if problem == "uncited_quote":
        ids = ["F1"]
    findings, _, _, _ = verify_research(
        [
            Investigation(
                topic="competitive_advantage",
                finding="Retention improved",
                evidence_ids=ids,
                quotes=[quote],
            )
        ],
        [],
        [],
        pack,
        True,
    )
    assert len(findings) == 10
    assert findings[0].status == ("cited" if problem == "none" else "unknown")


def test_management_delivery_needs_later_publication_and_archive_keeps_old_support():
    promise = DocumentPassage(
        evidence_id="D1",
        title="Old",
        page=3,
        text="We plan to commission the new capacity next year.",
        topics=("governance",),
        source=SOURCE.model_copy(update={"published_at": datetime(2025, 1, 1, tzinfo=UTC)}),
    )
    outcome = promise.model_copy(
        update={
            "evidence_id": "D2",
            "title": "New",
            "text": "The new capacity has now been commissioned.",
            "source": SOURCE.model_copy(
                update={
                    "url": "https://example.invalid/new",
                    "published_at": datetime(2026, 1, 1, tzinfo=UTC),
                }
            ),
        }
    )
    record = ManagementDelivery(
        decision="New plant",
        assessment="delivered",
        promise=EvidenceQuote(evidence_id="D1", quote=promise.text),
        outcome=EvidenceQuote(evidence_id="D2", quote=outcome.text),
    )
    pack = make_pack().model_copy(update={"documents": (promise, outcome)})
    assert verify_research([], [], [record], pack)[2][0].assessment == "delivered"
    changed = outcome.model_copy(update={"source": promise.source})
    assert (
        verify_research(
            [], [], [record], pack.model_copy(update={"documents": (promise, changed)})
        )[2][0].assessment
        == "unverified"
    )
    assert promise in select_passages([outcome, promise])


def assumptions(**updates):
    return ValuationAssumptions.model_validate(
        dict(
            revenue=1000,
            operating_margin=0.20,
            tax_rate=0.25,
            return_on_new_capital=0.25,
            discount_rate=0.12,
            terminal_growth=0.04,
            net_debt=100,
            equity_value=1500,
            **updates,
        )
    )


def test_reverse_dcf_recovers_known_growth_and_scenario_monotonic_margin():
    a = assumptions()
    target = equity_value(a, 0.08)
    result = reverse_valuation(a.model_copy(update={"equity_value": target}))
    assert any(abs(r - 0.08) < 1e-8 for r in result["required_growth_rates"])
    assert len(result["scenarios"]) == 9
    assert result["scenarios"][0]["equity_value"] < result["scenarios"][2]["equity_value"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("discount_rate", 0.03),
        ("return_on_new_capital", 0.02),
        ("net_debt", float("nan")),
        ("years", 0),
    ],
)
def test_dcf_rejects_unusable_assumptions(field, value):
    with pytest.raises(ValueError):
        ValuationAssumptions.model_validate(assumptions().model_dump() | {field: value})


def test_portfolio_shared_exposures_are_not_treated_as_disjoint_sectors():
    rows = [
        PortfolioPosition(
            isin="A", market_value=60, sector="Bank", currency="INR", shared_exposures=["rates"]
        ),
        PortfolioPosition(
            isin="B",
            market_value=40,
            sector="Industry",
            currency="INR",
            shared_exposures=["rates", "exports"],
        ),
    ]
    result = portfolio_exposures(rows)
    assert result["shared_exposure_weights"]["rates"] == 1
