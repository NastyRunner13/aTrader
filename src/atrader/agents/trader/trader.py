from atrader.agents import context
from atrader.agents.utils import ask
from atrader.contracts import AgentStatus, StrategyOutput, StrategyPlan
from atrader.verification import known_ids


def create_trader(llm):
    def trader_node(state):
        pack = state["pack"]

        role = """\
You are the trader. Turn the research manager's verdict into a hypothetical plan for the
stated horizon. You place no orders and have no execution tools.
- stance: consider_long, watch, avoid or no_view.
- Conditions to consider: observable events or metric levels that would have to hold
  before the thesis is actionable.
- Invalidation: what would end the thesis. Use price levels only if a metric supplies them.
- At most four scenarios, each with triggers. No probabilities: they are not calibrated."""

        evidence = context.join(
            context.company(pack),
            context.metrics(pack, "technical", "pattern", "liquidity",
                            title="Technicals and liquidity"),
            context.metrics(pack, "valuation", "market", title="Valuation and market context"),
            context.research_decision(state),
            context.vetoes(state),
            "Write the hypothetical plan.",
        )
        output, call_ids, error = ask(llm, "trader", role, evidence, StrategyOutput)
        if output is None:
            return {"trader_plan": StrategyPlan(
                stance="no_view", conditions_to_consider=[f"Trader unavailable: {error}"],
                status=AgentStatus.FAILED, model_call_ids=call_ids)}

        plan = StrategyPlan(
            **output.model_dump(exclude={"evidence_ids"}),
            evidence_ids=known_ids(output.evidence_ids, pack), model_call_ids=call_ids,
        )
        return {"trader_plan": plan}

    return trader_node
