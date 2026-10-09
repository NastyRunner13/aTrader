"""Research traceability: exact quotations and chronology, not semantic proof."""

from typing import get_args

from atrader.contracts import EvidencePack
from atrader.contracts.agents import (
    DisclosureTerm,
    EvidenceQuote,
    Investigation,
    ManagementDelivery,
    ResearchTopic,
)
from atrader.verification.claims import normalise_ids


def verify_research(
    investigations: list[Investigation],
    terms: list[DisclosureTerm],
    delivery: list[ManagementDelivery],
    pack: EvidencePack,
    require_topics: bool = False,
) -> tuple[list[Investigation], list[DisclosureTerm], list[ManagementDelivery], list[str]]:
    docs = {d.evidence_id: d for d in pack.documents}
    known = pack.evidence_ids()
    gaps = []

    def quote_ok(q: EvidenceQuote) -> bool:
        passage = docs.get(q.evidence_id)
        return passage is not None and " ".join(q.quote.split()) in " ".join(passage.text.split())

    reviewed: dict[str, Investigation] = {}
    for item in investigations:
        ids = list(dict.fromkeys(normalise_ids(item.evidence_ids)))
        quotes = [q for q in item.quotes if quote_ok(q)]
        valid = bool(ids and set(ids) <= known and len(quotes) == len(item.quotes)
                     and {q.evidence_id for q in quotes} <= set(ids))
        # Documentary assertions need a checked passage quote, not just a page ID.
        if {i for i in ids if i.startswith("D")} - {q.evidence_id for q in quotes}:
            valid = False
        reviewed[item.topic] = item.model_copy(
            update={
                "evidence_ids": ids if valid else [],
                "quotes": quotes if valid else [],
                "status": ("partial" if item.missing else "cited") if valid else "unknown",
                **(
                    {
                        "finding": "Insufficient traceable evidence for this investigation.",
                        "mechanism": None,
                        "threats": [],
                        "direction": "unknown",
                    }
                    if not valid
                    else {}
                ),
            }
        )
    if require_topics:
        for topic in get_args(ResearchTopic):
            reviewed.setdefault(
                topic,
                Investigation(
                    topic=topic,
                    finding="Not assessed by the model.",
                    missing=["A cited investigation is required."],
                ),
            )
    valid_terms = [t for t in terms if quote_ok(t.support)]
    if len(valid_terms) != len(terms):
        gaps.append("Disclosure terms without exact supporting source text were omitted.")
    valid_delivery = []
    for record in delivery:
        if not quote_ok(record.promise):
            gaps.append("A management record without a traceable promise was omitted.")
            continue
        promise_date = docs[record.promise.evidence_id].source.published_at
        outcome_date = (
            docs[record.outcome.evidence_id].source.published_at
            if record.outcome and quote_ok(record.outcome)
            else None
        )
        paired = bool(promise_date and outcome_date and outcome_date > promise_date)
        valid_delivery.append(
            record.model_copy(
                update={} if paired else {"outcome": None, "assessment": "unverified"}
            )
        )
    return list(reviewed.values()), valid_terms, valid_delivery, gaps
