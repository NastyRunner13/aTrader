from atrader.agents import context
from atrader.agents.utils import ask, debate_instruction, debate_turn
from atrader.contracts import DebateOutput


def create_bull_researcher(llm):
    def bull_node(state):
        pack = state["pack"]

        role = """\
You are the bull researcher in a structured debate about a company listed in India.
Build the strongest case the evidence supports for the stated horizon, and only that
case: a bull case built on thin evidence is a weak bull case.
- Ground each claim in evidence IDs or the analysts' claim IDs.
- State the assumptions your case needs and the falsifiers that would prove it wrong.
- In a rebuttal, name the bear's claim ID you dispute and whether the dispute is about a
  fact, an assumption, a mechanism or valuation.
- If the evidence does not support a bull case, say so plainly."""

        evidence = context.join(
            context.all_evidence(pack),
            context.analyst_reports(state),
            context.debate(state),
            context.vetoes(state),
            debate_instruction("bull", state),
        )
        output, call_ids, error = ask(llm, "bull_researcher", role, evidence, DebateOutput)
        return debate_turn("bull", state, output, call_ids, error)

    return bull_node
