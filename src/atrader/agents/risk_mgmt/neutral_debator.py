from atrader.agents.risk_mgmt.review import review_plan


def create_neutral_debator(llm):
    def neutral_node(state):
        role = """\
You are the neutral risk analyst. Weigh the aggressive and conservative reviews against
the shared evidence. Do not split the difference by default: if one view is better
supported, say so. Name the constraints that should bind any decision."""
        return review_plan(llm, state, "neutral", role)

    return neutral_node
