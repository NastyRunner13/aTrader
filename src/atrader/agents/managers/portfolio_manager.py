from atrader.agents import context
from atrader.agents.utils import ask
from atrader.contracts import AgentStatus, Synthesis, SynthesisOutput
from atrader.verification import verify_reasons


def create_portfolio_manager(llm):
    def portfolio_manager_node(state):
        pack = state["pack"]

        role = """\
You are the portfolio manager. Code has already turned the analysts' work into a draft
scorecard: a 0-100 score for each area, weighted into a 1-month, 6-month and 2-year
score and signal. Explain it for a reader who wants the answer, not the whole analysis.
- summary: two or three plain sentences a non-expert understands.
- pros and cons: up to five each, one sentence with evidence IDs, most decision-relevant
  first.
- horizons: one note each for 1m, 6m and 2y: up to three drivers, and observable events
  that would move the signal up (up_if) or down (down_if).
- adjustment: you may move a horizon's score by up to 5 points when the debate or risk
  reviews show the draft misses something material; give adjustment_reason. Usually 0.
- unresolved: disagreements the evidence could not settle and missing data that matters.
- Keep disagreement visible; do not average contradictions into false certainty.
- Code applies the listed constraints after you answer."""

        evidence = context.join(
            context.all_evidence(pack),
            context.analyst_reports(state),
            context.debate(state),
            context.risk_reviews(state),
            context.draft_scorecard(state),
            context.vetoes(state),
            "Write the final synthesis.",
        )
        output, call_ids, error = ask(llm, "portfolio_manager", role, evidence, SynthesisOutput)
        if output is None:
            return {"final_synthesis": Synthesis(
                summary=f"Portfolio manager unavailable: {error}", status=AgentStatus.FAILED,
                model_call_ids=call_ids)}

        pros, dropped = verify_reasons(output.pros, pack)
        cons, dropped_cons = verify_reasons(output.cons, pack)
        synthesis = Synthesis(
            **output.model_dump(exclude={"pros", "cons"}),
            pros=pros, cons=cons, dropped_reasons=dropped + dropped_cons,
            model_call_ids=call_ids,
        )
        return {"final_synthesis": synthesis}

    return portfolio_manager_node
