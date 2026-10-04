"""The step the three risk debators share: review the trader's plan once each, in turn,
seeing the reviews before them."""

from atrader.agents import context
from atrader.agents.utils import ask
from atrader.contracts import AgentStatus, RiskOutput, RiskReview
from atrader.verification import known_ids


def review_plan(llm, state, perspective, role):
    pack = state["pack"]
    evidence = context.join(
        context.company(pack),
        context.metrics(pack, "fundamental", "valuation", title="Fundamentals and valuation"),
        context.metrics(pack, "technical", "pattern", "liquidity",
                        title="Technicals and liquidity"),
        context.coverage(pack),
        context.research_decision(state),
        context.trader_plan(state),
        context.risk_reviews(state),
        context.vetoes(state),
        f"Give the {perspective} risk review of this plan.",
    )
    output, call_ids, error = ask(llm, f"{perspective}_debator", role, evidence, RiskOutput)
    if output is None:
        review = RiskReview(perspective=perspective, verdict="caution",
                            rationale=f"Reviewer unavailable: {error}",
                            status=AgentStatus.FAILED, model_call_ids=call_ids)
    else:
        review = RiskReview(perspective=perspective,
                            **output.model_dump(exclude={"evidence_ids"}),
                            evidence_ids=known_ids(output.evidence_ids, pack),
                            model_call_ids=call_ids)
    return {"risk_reviews": [review]}
