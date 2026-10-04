from atrader.agents import context
from atrader.agents.utils import ask
from atrader.contracts import AgentStatus, Assessment, Synthesis, SynthesisOutput
from atrader.verification import verify_reasons


def create_portfolio_manager(llm):
    def portfolio_manager_node(state):
        pack = state["pack"]

        role = """\
You are the portfolio manager. Write the final research conclusion for this company and
horizon from the analysts' verified claims, the debate, and any research-manager, trader
and risk reviews provided. If there are none, weigh the debate yourself and put the main
risk constraints in key_risks.
- assessment: supportive, mixed, adverse or insufficient_evidence. It describes what the
  evidence says for the horizon; it is not a trade instruction or a probability.
- top_reasons and key_risks: one sentence each, with evidence IDs.
- strengthen_if / weaken_if / invalidate_if: observable future events.
- unresolved: disagreements the evidence could not settle, and missing data.
- Keep disagreement visible; do not average contradictions into false certainty.
- Code applies the listed constraints after you answer. Write consistently with them."""

        evidence = context.join(
            context.all_evidence(pack),
            context.analyst_reports(state),
            context.debate(state),
            context.research_decision(state),
            context.trader_plan(state),
            context.risk_reviews(state),
            context.vetoes(state),
            "Write the final synthesis.",
        )
        output, call_ids, error = ask(llm, "portfolio_manager", role, evidence, SynthesisOutput)
        if output is None:
            return {"final_synthesis": Synthesis(
                assessment=Assessment.INSUFFICIENT_EVIDENCE,
                summary=f"Portfolio manager unavailable: {error}", status=AgentStatus.FAILED,
                model_call_ids=call_ids)}

        reasons, dropped = verify_reasons(output.top_reasons, pack)
        risks, dropped_risks = verify_reasons(output.key_risks, pack)
        synthesis = Synthesis(
            **output.model_dump(exclude={"top_reasons", "key_risks"}),
            top_reasons=reasons, key_risks=risks, dropped_reasons=dropped + dropped_risks,
            model_call_ids=call_ids,
        )
        return {"final_synthesis": synthesis}

    return portfolio_manager_node
