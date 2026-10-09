"""Evaluation must distinguish workflow checks, human judgements and realised outcomes."""

import json
from unittest.mock import Mock

import pytest

from atrader.analytics.portfolio import PortfolioPosition, portfolio_exposures
from atrader.contracts import Mode
from atrader.evaluation import audit_summary, evaluate_reports
from atrader.graph.research_graph import ResearchGraph
from tests.conftest import StaticEvidence, make_pack


def test_ungraded_claims_are_not_counted_as_human_supported():
    result = audit_summary([{"machine_status": "supported", "human_support": None}])
    assert result["reviewed"] == 0
    assert result["support_rate"] is None and result["threshold_95pct_met"] is None


def test_human_support_denominator_and_uncertainty():
    result = audit_summary([{"human_support": True}] * 19 + [{"human_support": False},
                                                            {"human_support": None}])
    assert result["reviewed"] == 20 and result["sampled"] == 21
    assert result["support_rate"] == .95
    assert result["support_rate_95pct_wilson"][0] < .95 < result["support_rate_95pct_wilson"][1]


def test_report_audit_labels_placeholder_models_and_preserves_evidence_identity(settings, tmp_path):
    pack = make_pack()
    report = ResearchGraph(settings, dry_run=True, evidence_source=StaticEvidence(pack)).run(
        pack.listing.symbol, mode=Mode.BASELINE, cutoff=pack.cutoff)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([{"report": report.report_id}]), encoding="utf-8")
    store = Mock()
    store.bars_for.return_value = []
    result = evaluate_reports([*settings.reports_dir.glob("*.json"), manifest], store)
    assert len(result["reports"]) == 1
    row = result["reports"][0]
    assert row["dry_run"] and row["pack_id"] == pack.pack_id and row["model_calls"] == 1
    assert row["returns"] == {}
    assert result["by_mode"]["baseline"]["reports"] == 1


@pytest.mark.parametrize("currency", ["USD", "EUR"])
def test_portfolio_rejects_mixed_valuation_currencies(currency):
    with pytest.raises(ValueError, match="common valuation currency"):
        portfolio_exposures([PortfolioPosition(isin="A", market_value=100),
                             PortfolioPosition(isin="B", market_value=100, currency=currency)])
