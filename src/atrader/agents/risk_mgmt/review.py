"""The step the three risk debators share: review the draft scorecard once each. They run
in parallel, so none sees the others' reviews; the portfolio manager reads all three."""

from atrader.agents import context
from atrader.agents.utils import ask
from atrader.contracts import AgentStatus, RiskOutput, RiskReview
from atrader.verification import known_ids


def review_scorecard(llm, state, perspective, role):
    pack = state["pack"]
    evidence = context.join(
        context.company(pack),
        context.metrics(pack, "fundamental", "valuation", title="Fundamentals and valuation"),
        context.metrics(pack, "technical", "pattern", "liquidity",
                        title="Technicals and liquidity"),
        context.coverage(pack),
        context.analyst_reports(state),
        context.debate(state),
        context.draft_scorecard(state),
        context.vetoes(state),
        f"Give the {perspective} risk review of the draft scorecard.",
    )
    output, call_ids, error = ask(llm, f"{perspective}_debator", role, evidence, RiskOutput)
    if output is None:
        review = RiskReview(perspective=perspective, verdict="fair",
                            rationale=f"Reviewer unavailable: {error}",
                            status=AgentStatus.FAILED, model_call_ids=call_ids)
    else:
        review = RiskReview(perspective=perspective,
                            **output.model_dump(exclude={"evidence_ids"}),
                            evidence_ids=known_ids(output.evidence_ids, pack),
                            model_call_ids=call_ids)
    return {"risk_reviews": [review]}
