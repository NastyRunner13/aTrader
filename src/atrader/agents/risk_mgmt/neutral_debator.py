from atrader.agents.risk_mgmt.review import review_scorecard


def create_neutral_debator(llm):
    def neutral_node(state):
        role = """\
You are the neutral risk analyst. Weigh upside and downside in the draft scores against
the shared evidence and the debate. Do not split the difference by default: if the
scores lean too far one way, say which area or horizon and why. Name the conditions that
should hold before anyone relies on the signal."""
        return review_scorecard(llm, state, "neutral", role)

    return neutral_node
