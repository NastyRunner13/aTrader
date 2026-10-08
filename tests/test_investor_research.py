"""Regression cases for research safeguards and multi-period expectations."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest

from atrader.analytics.fundamentals import EPS, fundamental_metrics
from atrader.analytics.scoring import base_scores, build_scorecard
from atrader.contracts import Coverage, CoverageEntry, ResearchRequest, StatementBasis
from atrader.data.evidence_builder import MAX_ANNOUNCEMENTS, NseEvidenceBuilder
from atrader.data.providers import nse_announcements
from tests.conftest import CUTOFF, LISTING, make_index, make_pack, make_two_year_facts


def test_trailing_growth_uses_eight_non_overlapping_quarters():
    facts = make_two_year_facts()
    metrics = {m.name: m for m in fundamental_metrics(facts, 300, CUTOFF)}
    eps = sorted((f for f in facts if f.metric == EPS), key=lambda f: f.period_end)
    expected = (sum(f.value for f in eps[4:]) / sum(f.value for f in eps[:4]) - 1) * 100
    assert metrics["eps_ttm_yoy"].value == pytest.approx(float(expected), abs=0.005)
    assert set(metrics["eps_ttm_yoy"].inputs) == {f.evidence_id for f in eps}
    assert {"revenue_ttm_yoy", "profit_ttm_yoy"} <= metrics.keys()
    assert "not through-cycle" in metrics["eps_ttm_yoy"].quality_flags[0]
    # Reported growth is available even without market prices.
    assert "eps_ttm_yoy" in {m.name for m in fundamental_metrics(facts, None, None)}


@pytest.mark.parametrize("problem", ["missing", "overlap", "basis", "units", "negative", "zero"])
def test_trailing_growth_rejects_incomparable_or_unusable_history(problem):
    facts = make_two_year_facts()
    first = next(f for f in facts if f.metric == EPS and f.period_end == date(2024, 12, 31))
    if problem == "missing":
        facts.remove(first)
    else:
        change = {"overlap": {"period_start": first.period_start - timedelta(days=1)},
                  "basis": {"basis": StatementBasis.STANDALONE},
                  "units": {"unit": "INR"}, "negative": {"value": Decimal(-1000)},
                  "zero": {"value": Decimal(0)}}[problem]
        facts = [f.model_copy(update=change) if f is first else f for f in facts]
        if problem == "zero":
            facts = [f.model_copy(update={"value": Decimal(0)})
                     if f.metric == EPS and f.period_end <= date(2025, 6, 30) else f
                     for f in facts]
    assert "eps_ttm_yoy" not in {m.name for m in fundamental_metrics(facts, 300, CUTOFF)}


def test_ttm_eps_requires_consecutive_quarters():
    facts = [f for f in make_two_year_facts() if f.period_end != date(2026, 3, 31)]
    names = {m.name for m in fundamental_metrics(facts, 300, CUTOFF)}
    assert "eps_ttm" not in names and "pe_ttm" not in names


@pytest.mark.parametrize("percentage", [0, 30, 60, 100])
def test_promoter_percentage_changes_cannot_move_scores(percentage):
    pack = make_pack()
    snapshot = pack.shareholding[0]
    changed = pack.model_copy(update={"shareholding": (
        snapshot.model_copy(update={"evidence_id": "S2", "period_end": date(2026, 3, 31),
                                    "promoter_pct": percentage}), snapshot)})
    assert base_scores(changed)["growth_quality"] == base_scores(pack)["growth_quality"]


@pytest.mark.parametrize("quarterly_growth", [-90, 0, 5, 5000])
def test_quarterly_growth_does_not_change_valuation(quarterly_growth):
    pack = make_pack(indices=(make_index(),))
    changed = pack.model_copy(update={"metrics": tuple(
        m.model_copy(update={"value": quarterly_growth}) if m.name == "profit_yoy" else m
        for m in pack.metrics)})
    original = base_scores(pack)
    assert base_scores(changed)["valuation"] == original["valuation"]
    assert build_scorecard(pack, original, []).version == "scorecard/3"


def test_reverse_valuation_reproduces_assumed_return_and_cites_inputs():
    pack = make_pack(indices=(make_index(pe=20), make_index("Sector", "sector", pe=15)))
    metrics = {m.name: m for m in pack.metrics}
    implied = metrics["price_implied_eps_growth_2y"]
    terminal = metrics["eps_ttm"].value * (1 + implied.value / 100) ** 2 * 15
    assert terminal / pack.bars[-1].close == pytest.approx(1.1 ** 2, abs=0.002)
    assert implied.inputs == (metrics["pe_ttm"].evidence_id, metrics["sector_pe"].evidence_id)
    assert "Assumptions" in implied.detail and "dividends excluded" in implied.detail
    assert set(implied.inputs) <= pack.evidence_ids()


def test_reverse_valuation_falls_back_to_valid_market_multiple_or_stays_missing():
    pack = make_pack(indices=(make_index(pe=20), make_index("Sector", "sector", pe=-5)))
    metrics = {m.name: m for m in pack.metrics}
    assert metrics["benchmark_pe"].evidence_id in metrics["price_implied_eps_growth_2y"].inputs
    assert "price_implied_eps_growth_2y" not in {m.name for m in make_pack().metrics}


def test_updates_reach_agents_and_prompt_truncation_is_visible(settings, monkeypatch):
    template = make_pack().announcements[0]
    update = template.model_copy(update={"category": "Updates", "summary": "Plant shut down"})
    routine = template.model_copy(update={"category": "Trading Window"})
    future = update.model_copy(update={"published_at": update.published_at.replace(month=10)})
    monkeypatch.setattr(nse_announcements, "fetch_announcements", lambda *args: [
        routine, update, future])
    builder = NseEvidenceBuilder(Mock(), Mock(), settings)
    kept, coverage = builder._announcements(LISTING, CUTOFF)
    assert kept == [update]
    assert coverage.status == Coverage.AVAILABLE
    assert "1 routine" in coverage.detail and "0 additional" in coverage.detail

    many = [update.model_copy(update={"published_at": update.published_at - timedelta(days=i)})
            for i in range(MAX_ANNOUNCEMENTS + 1)]
    monkeypatch.setattr(nse_announcements, "fetch_announcements", lambda *args: many[::-1])
    kept, coverage = builder._announcements(LISTING, CUTOFF)
    assert kept == many[:MAX_ANNOUNCEMENTS]
    assert coverage.status == Coverage.PARTIAL and "1 additional" in coverage.detail


def test_missing_institutional_datasets_are_separate_coverage_gaps(settings, monkeypatch):
    builder = NseEvidenceBuilder(Mock(), Mock(), settings)
    monkeypatch.setattr(builder, "resolve", lambda symbol: LISTING)
    monkeypatch.setattr(builder, "_prices", lambda *args: ([], []))
    monkeypatch.setattr(builder, "_index_series", lambda *args: None)
    entry = CoverageEntry(category="sector", status=Coverage.MISSING)
    monkeypatch.setattr(builder, "_sector", lambda *args: (None, None, entry))
    for method in ("_financials", "_announcements", "_shareholding", "_news"):
        monkeypatch.setattr(builder, method, lambda *args: ([], entry))
    pack = builder.build(ResearchRequest(symbol=LISTING.symbol, cutoff=CUTOFF))
    for category in ("institutional_market_activity", "institutional_sector_activity",
                     "institutional_ownership", "business_economics", "financial_resilience"):
        coverage = pack.coverage_for(category)
        assert coverage is not None and coverage.status == Coverage.NOT_REQUESTED
    assert not pack.metrics  # missing data never becomes synthetic zero flows
