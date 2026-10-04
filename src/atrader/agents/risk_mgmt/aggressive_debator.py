from atrader.agents.risk_mgmt.review import review_plan


def create_aggressive_debator(llm):
    def aggressive_node(state):
        role = """\
You are the aggressive risk analyst. Make the best defensible case for accepting the
plan's risks: the opportunity cost of waiting, upside the plan may under-weight, and the
constraints under which taking the risk is reasonable. Being aggressive does not
license unsupported claims."""
        return review_plan(llm, state, "aggressive", role)

    return aggressive_node
