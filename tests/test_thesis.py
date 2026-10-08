"""Thesis citation filtering and explicit unknown next events."""

import pytest
from pydantic import ValidationError

from atrader.agents.managers.portfolio_manager import create_portfolio_manager
from atrader.analytics.scoring import base_scores
from atrader.contracts import Synthesis, ThesisTest
from atrader.llm import LLM
from atrader.llm.fake import FakeGateway
from tests.conftest import make_pack


def synthesize(tests):
    pack = make_pack()
    llm = LLM(FakeGateway("thesis", lambda *args: {"summary": "Test", "thesis_tests": tests}),
              "deep")
    return create_portfolio_manager(llm)({
        "pack": pack, "base_scores": base_scores(pack), "vetoes": [],
    })["final_synthesis"]


def thesis(**changes):
    return {"assumption": "Margins remain sustainable", "evidence_ids": ["F1"],
            "invalidated_by": "Persistent margin contraction across comparable periods",
            "next_event": "Results meeting", "next_event_date": "2026-11-15",
            "next_event_evidence_ids": ["A1"], **changes}


def test_three_distinct_cited_assumptions_survive():
    result = synthesize([thesis(assumption=a) for a in (
        "Margins remain sustainable", "Collections remain healthy", "Expansion earns a return")])
    assert len(result.thesis_tests) == 3 and result.unresolved == []
    assert result.thesis_tests[0].next_event_date.isoformat() == "2026-11-15"


@pytest.mark.parametrize("ids", [[], ["F999"], ["F1", "F999"]])
def test_uncited_assumptions_are_not_padded_to_three(ids):
    result = synthesize([thesis(evidence_ids=ids)])
    assert result.thesis_tests == [] and any("Only 0" in gap for gap in result.unresolved)


@pytest.mark.parametrize("changes", [
    {"next_event_evidence_ids": []}, {"next_event_evidence_ids": ["F1"]},
    {"next_event_evidence_ids": ["A1", "A999"]}, {"next_event_date": "2026-09-01"},
    {"next_event": None},
])
def test_unsupported_or_past_next_event_becomes_unknown(changes):
    result = synthesize([thesis(**changes)])
    kept = result.thesis_tests[0]
    assert kept.next_event is None and kept.next_event_date is None
    assert kept.next_event_evidence_ids == []
    assert any("left unknown" in gap for gap in result.unresolved)


def test_duplicate_assumptions_do_not_fake_completeness():
    result = synthesize([thesis(), thesis(), thesis()])
    assert len(result.thesis_tests) == 1
    assert any("Only 1" in gap for gap in result.unresolved)


def test_empty_fields_are_invalid_and_old_reports_load():
    with pytest.raises(ValidationError):
        ThesisTest(assumption=" ", invalidated_by=" ")
    assert Synthesis(summary="Archived report").thesis_tests == []
