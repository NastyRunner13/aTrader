from atrader.agents.risk_mgmt.review import review_scorecard


def create_conservative_debator(llm):
    def conservative_node(state):
        role = """\
You are the conservative risk analyst. Object wherever the draft scores under-weight the
chance of losing capital: downside scenarios, gap risk around events, liquidity,
leverage, stale or missing data, and scores resting on a single source. Every objection
must be specific and tied to the evidence or to a named gap."""
        return review_scorecard(llm, state, "conservative", role)

    return conservative_node
