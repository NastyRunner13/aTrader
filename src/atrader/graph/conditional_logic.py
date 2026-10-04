from atrader.agents.state import AgentState
from atrader.contracts import Mode

DEBATE_DONE = "debate_done"


class ConditionalLogic:
    """Routing decisions for the research graph."""

    def __init__(self, max_debate_rounds: int = 1) -> None:
        self.max_debate_rounds = max_debate_rounds

    def should_run_analysts(self, state: AgentState, analyst_nodes: list[str]) -> list[str] | str:
        """Fan out to the analysts, unless this is a data-only run or the pack lacks the
        minimum evidence for any AI conclusion."""
        pack = state.get("pack")
        if state["request"].mode == Mode.DATA_ONLY or pack is None or not pack.has_core_evidence:
            return "finalize"
        return analyst_nodes

    def should_continue_debate(self, state: AgentState) -> str:
        """Bull and bear alternate until each has spoken `max_debate_rounds` times."""
        turns = state.get("debate", [])
        if len(turns) >= 2 * self.max_debate_rounds:
            return DEBATE_DONE
        return "bear_researcher" if turns[-1].side == "bull" else "bull_researcher"
