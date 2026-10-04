"""Claim and reason verification against the frozen evidence pack."""

from __future__ import annotations

from atrader.contracts import ClaimDraft, ClaimKind, ClaimStatus, Reason
from atrader.verification import verify_claims, verify_reasons
from tests.conftest import make_pack


def _claim(statement, kind, ids):
    return ClaimDraft(statement=statement, kind=kind, evidence_ids=ids)


def test_claim_statuses():
    pack = make_pack()
    revenue = next(f.evidence_id for f in pack.facts)
    drafts = [
        _claim("Revenue grew 20% year on year.", ClaimKind.FACT, [revenue]),
        _claim("Revenue grew 20% year on year.", ClaimKind.FACT, ["F999"]),
        _claim("Revenue grew 20% year on year.", ClaimKind.FACT, ["A1"]),
        _claim("An order was disclosed.", ClaimKind.FACT, ["[A1]"]),
        _claim("Execution risk looks manageable.", ClaimKind.INTERPRETATION, []),
        _claim("Margins may compress.", ClaimKind.SCENARIO, ["X42"]),
    ]
    claims = verify_claims(drafts, pack, "fundamentals_analyst", "fundamentals")

    assert [c.status for c in claims] == [
        ClaimStatus.SUPPORTED,
        ClaimStatus.UNSUPPORTED,  # invented ID
        ClaimStatus.UNSUPPORTED,  # a number resting only on an announcement
        ClaimStatus.SUPPORTED,  # brackets are normalised
        ClaimStatus.NEEDS_REVIEW,  # opinion without evidence
        ClaimStatus.UNSUPPORTED,  # only unknown IDs
    ]
    assert claims[0].claim_id == "C-fundamentals-1"
    assert claims[1].evidence_ids == [] and "F999" in claims[1].issues[0]


def test_reasons_with_fake_ids_or_unbacked_numbers_are_dropped():
    pack = make_pack()
    metric = pack.metrics[0].evidence_id
    kept, dropped = verify_reasons([
        Reason(statement="Price is above its 50-day average by 4%.", evidence_ids=[metric]),
        Reason(statement="Margins expanded 300 bps.", evidence_ids=[]),
        Reason(statement="Order momentum is strong.", evidence_ids=["A77"]),
        Reason(statement="Disclosure flow is routine.", evidence_ids=[]),
    ], pack)
    assert [r.statement for r in kept] == ["Price is above its 50-day average by 4%.",
                                           "Disclosure flow is routine."]
    assert len(dropped) == 2


def test_shareholding_figures_can_back_numeric_claims():
    pack = make_pack()
    claims = verify_claims(
        [_claim("Promoter holding was 55.00% in the June quarter.", ClaimKind.FACT, ["S1"])],
        pack, "fundamentals_analyst", "fundamentals")
    assert claims[0].status == ClaimStatus.SUPPORTED
