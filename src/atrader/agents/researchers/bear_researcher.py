from atrader.agents import context
from atrader.agents.utils import ask, debate_instruction, debate_turn
from atrader.contracts import DebateOutput


def create_bear_researcher(llm):
    def bear_node(state):
        pack = state["pack"]

        role = """\
You are the bear researcher in a structured debate about a company listed in India.
Build the strongest counter-thesis the evidence supports for the 1-month, 6-month and
2-year outlook: downside mechanisms, weak assumptions in the bull case, data gaps that
matter and risks that may be under-weighted.
- Ground each claim in evidence IDs or the analysts' claim IDs.
- Challenge the bull's claims by claim ID: fact, assumption, mechanism or valuation.
- Missing evidence is a risk to name, not a fact to assert. Do not invent problems.
- State falsifiers that would prove the bear case wrong.
- Where the draft scorecard looks too high, say which area or horizon and why."""

        evidence = context.join(
            context.all_evidence(pack),
            context.analyst_reports(state),
            context.draft_scorecard(state),
            context.debate(state),
            context.vetoes(state),
            debate_instruction("bear", state),
        )
        output, call_ids, error = ask(llm, "bear_researcher", role, evidence, DebateOutput)
        return debate_turn("bear", state, output, call_ids, error)

    return bear_node
