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
every indicator, rule-based chart signal and price level from NSE end-of-day data; you
explain them.
- Trend (moving averages), momentum (RSI, MACD histogram, period returns), volatility
  (ATR, realised volatility), and relative strength versus the Nifty 50 and the
  stock's sector index.
- Volume and delivery: delivered and traded volume on up days versus down days, the
  delivery share against its recent norm, and the volume EMA trend. Read these as
  accumulation or distribution. They do not say who traded: per-stock FII flows are
  not in this data.
- A chart signal counts only as its rule defines it. Do not invent patterns.
- Price levels: name the nearest support and resistance zones, the moving averages
  and VWAPs near the price, and the close that breaks the nearest support, using the
  level metrics only. Levels describe the past; do not call them targets.
- Note liquidity and the length of the price history.
- Python also turned these metrics into a technical score (below, with the points each
  rule added; rules in one group are capped together). Adjust it in score_adjustments
  only if the rules miss something the evidence shows, by at most 15 points, with a
  reason and evidence IDs. Usually no adjustment is right."""

        evidence = context.join(
            context.company(pack),
            context.metrics(pack, "technical", title="Technical indicators"),
            context.metrics(pack, "pattern", title="Rule-based chart signals"),
            context.metrics(pack, "flow", title="Volume and delivery"),
            context.metrics(pack, "level", title="Price levels (past turning points and volume)"),
            context.metrics(pack, "liquidity", "market", title="Liquidity and market context"),
            context.base_scores(state, Pillar.TECHNICAL),
            context.coverage(pack),
            "Write your analysis.",
        )
        output, call_ids, error = ask(llm, "market_analyst", role, evidence, AnalystOutput)
        return analyst_report("market_analyst", pack, output, call_ids, error)

    return market_analyst_node
