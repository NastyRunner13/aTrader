from collections.abc import Hashable

from langgraph.graph import END, START, StateGraph

from atrader.agents import (
    AgentState,
    create_aggressive_debator,
    create_bear_researcher,
    create_bull_researcher,
    create_conservative_debator,
    create_fundamentals_analyst,
    create_market_analyst,
    create_neutral_debator,
    create_news_analyst,
    create_portfolio_manager,
    create_research_manager,
    create_trader,
)
from atrader.contracts import Mode
from atrader.graph.conditional_logic import DEBATE_DONE, ConditionalLogic
from atrader.graph.nodes import finalize_node

ANALYSTS = {
    "market": create_market_analyst,
    "fundamentals": create_fundamentals_analyst,
    "news": create_news_analyst,
}


class GraphSetup:
    """Builds the research workflow.

    compact: analysts → bull ⇄ bear (1 round) → portfolio manager
    full:    analysts → bull ⇄ bear (2 rounds) → research manager → trader
             → aggressive → conservative → neutral → portfolio manager
    Both end in `finalize`, where code applies the vetoes.
    """

    def __init__(self, quick_llm, deep_llm, data_steward, conditional_logic: ConditionalLogic):
        self.quick_llm = quick_llm
        self.deep_llm = deep_llm
        self.data_steward = data_steward
        self.conditional_logic = conditional_logic

    def setup_graph(self, mode: Mode, selected_analysts=("market", "fundamentals", "news")):
        workflow = StateGraph(AgentState)
        workflow.add_node("data_steward", self.data_steward)
        workflow.add_node("finalize", finalize_node)
        workflow.add_edge(START, "data_steward")
        workflow.add_edge("finalize", END)

        if mode == Mode.DATA_ONLY:
            workflow.add_edge("data_steward", "finalize")
            return workflow

        # Analyst team: runs in parallel once the evidence pack is frozen.
        analyst_nodes = []
        for key in selected_analysts:
            name = f"{key}_analyst"
            workflow.add_node(name, ANALYSTS[key](self.quick_llm))
            analyst_nodes.append(name)
        workflow.add_conditional_edges(
            "data_steward",
            lambda state: self.conditional_logic.should_run_analysts(state, analyst_nodes),
            [*analyst_nodes, "finalize"],
        )

        # Research team: the debate starts when every analyst has filed its report.
        workflow.add_node("bull_researcher", create_bull_researcher(self.quick_llm))
        workflow.add_node("bear_researcher", create_bear_researcher(self.quick_llm))
        workflow.add_edge(analyst_nodes, "bull_researcher")

        after_debate = "research_manager" if mode == Mode.FULL else "portfolio_manager"
        debate_paths: dict[Hashable, str] = {"bull_researcher": "bull_researcher",
                        "bear_researcher": "bear_researcher",
                        DEBATE_DONE: after_debate}
        for node in ("bull_researcher", "bear_researcher"):
            workflow.add_conditional_edges(node, self.conditional_logic.should_continue_debate,
                                           debate_paths)

        # Full mode only: research manager, trader and the risk team.
        if mode == Mode.FULL:
            workflow.add_node("research_manager", create_research_manager(self.deep_llm))
            workflow.add_node("trader", create_trader(self.quick_llm))
            workflow.add_node("aggressive_debator", create_aggressive_debator(self.quick_llm))
            workflow.add_node("conservative_debator",
                              create_conservative_debator(self.quick_llm))
            workflow.add_node("neutral_debator", create_neutral_debator(self.quick_llm))
            workflow.add_edge("research_manager", "trader")
            workflow.add_edge("trader", "aggressive_debator")
            workflow.add_edge("aggressive_debator", "conservative_debator")
            workflow.add_edge("conservative_debator", "neutral_debator")
            workflow.add_edge("neutral_debator", "portfolio_manager")

        workflow.add_node("portfolio_manager", create_portfolio_manager(self.deep_llm))
        workflow.add_edge("portfolio_manager", "finalize")
        return workflow
