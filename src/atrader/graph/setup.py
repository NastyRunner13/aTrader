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
)
from atrader.contracts import Mode
from atrader.graph.conditional_logic import DEBATERS, ConditionalLogic
from atrader.graph.nodes import debate_round_node, finalize_node

ANALYSTS = {
    "market": create_market_analyst,
    "fundamentals": create_fundamentals_analyst,
    "news": create_news_analyst,
}
RISK_TEAM = ["aggressive_debator", "conservative_debator", "neutral_debator"]


class GraphSetup:
    """Builds the research workflow. Agents joined by ∥ run at the same time.

    compact:   analysts ∥ → bull ∥ bear (1 round) → portfolio manager
    full:      analysts ∥ → bull ∥ bear (2 rounds) → aggressive ∥ conservative ∥ neutral
               → portfolio manager
    data_only: no agents.
    All end in `finalize`, where code builds the scorecard and applies the vetoes.
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

        if mode == Mode.BASELINE:
            workflow.add_node("portfolio_manager", create_portfolio_manager(self.deep_llm))
            workflow.add_conditional_edges(
                "data_steward",
                lambda state: self.conditional_logic.should_run_analysts(
                    state, ["portfolio_manager"]), ["portfolio_manager", "finalize"])
            workflow.add_edge("portfolio_manager", "finalize")
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

        # Research team: once every analyst has filed, bull and bear argue in parallel
        # rounds. `debate_round` waits for both sides before the next round starts.
        workflow.add_node("debate_round", debate_round_node)
        workflow.add_node("bull_researcher", create_bull_researcher(self.quick_llm))
        workflow.add_node("bear_researcher", create_bear_researcher(self.quick_llm))
        workflow.add_edge(analyst_nodes, "debate_round")
        workflow.add_edge(DEBATERS, "debate_round")

        after_debate = RISK_TEAM if mode == Mode.FULL else ["portfolio_manager"]
        workflow.add_conditional_edges(
            "debate_round",
            lambda state: self.conditional_logic.should_continue_debate(state, after_debate),
            [*DEBATERS, *after_debate],
        )

        workflow.add_node("portfolio_manager", create_portfolio_manager(self.deep_llm))
        workflow.add_edge("portfolio_manager", "finalize")

        # Full mode only: the risk team reviews the draft scorecard in parallel.
        if mode == Mode.FULL:
            workflow.add_node("aggressive_debator", create_aggressive_debator(self.quick_llm))
            workflow.add_node("conservative_debator",
                              create_conservative_debator(self.quick_llm))
            workflow.add_node("neutral_debator", create_neutral_debator(self.quick_llm))
            workflow.add_edge(RISK_TEAM, "portfolio_manager")
        return workflow
