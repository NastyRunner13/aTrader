from atrader.agents.risk_mgmt.review import review_scorecard


def create_aggressive_debator(llm):
    def aggressive_node(state):
        role = """\
You are the aggressive risk analyst. Make the best defensible case that the draft scores
under-weight upside: the opportunity cost of waiting, catalysts the rules cannot see,
and the conditions under which taking the risk is reasonable. Being aggressive does not
license unsupported claims."""
        return review_scorecard(llm, state, "aggressive", role)

    return aggressive_node
