from atrader.agents.risk_mgmt.review import review_plan


def create_conservative_debator(llm):
    def conservative_node(state):
        role = """\
You are the conservative risk analyst. Object wherever capital could be lost: downside
scenarios, gap risk around events, liquidity, leverage, stale or missing data, and
conclusions resting on a single source. Every objection must be specific and tied to
the evidence or to a named gap."""
        return review_plan(llm, state, "conservative", role)

    return conservative_node
