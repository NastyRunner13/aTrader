from atrader.agents import context
from atrader.agents.utils import analyst_report, ask, skipped_report
from atrader.contracts import AnalystOutput, Pillar


def create_market_analyst(llm):
    def market_analyst_node(state):
        pack = state["pack"]
        if not pack.bars:
            return skipped_report("market_analyst", "no price history")

        role = """\
You are the market analyst for a company listed in India. Python has already computed
every indicator and rule-based chart signal from NSE end-of-day data; you explain them.
- Trend (moving-average state), momentum (RSI, MACD histogram, period returns),
  volatility (ATR, realised volatility), volume, and relative strength versus the index.
- A chart signal counts only as its rule defines it. Do not invent patterns.
- State the levels that would invalidate the current reading, using metric values only.
- Note liquidity and the length of the price history.
- Python also turned these metrics into a technical score (below, with the points each
  rule added). Adjust it in score_adjustments only if the rules miss something the
  evidence shows, by at most 15 points, with a reason and evidence IDs. Usually no
  adjustment is right."""

        evidence = context.join(
            context.company(pack),
            context.metrics(pack, "technical", title="Technical indicators"),
            context.metrics(pack, "pattern", title="Rule-based chart signals"),
            context.metrics(pack, "liquidity", "market", title="Liquidity and market context"),
            context.base_scores(state, Pillar.TECHNICAL),
            context.coverage(pack),
            "Write your analysis.",
        )
        output, call_ids, error = ask(llm, "market_analyst", role, evidence, AnalystOutput)
        return analyst_report("market_analyst", pack, output, call_ids, error)

    return market_analyst_node
