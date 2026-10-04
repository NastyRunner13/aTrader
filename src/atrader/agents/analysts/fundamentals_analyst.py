from atrader.agents import context
from atrader.agents.utils import analyst_report, ask, skipped_report
from atrader.contracts import AnalystOutput


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        pack = state["pack"]
        if not pack.facts:
            return skipped_report("fundamentals_analyst", "no reported financial results")

        role = """\
You are the fundamentals analyst for a company listed in India. You read its filed
quarterly results (exchange XBRL) and the ratios Python computed from them.
- Growth: revenue and profit, year on year for the same quarter, and quarter on quarter.
- Earnings quality: margins, the share of profit from other income, exceptional items,
  finance costs.
- Valuation: trailing P/E and market capitalisation where computed. Read the index P/E
  as context only; different businesses are not directly comparable.
- Ownership: the promoter and public holding trend across quarters.
- Note the reporting basis, audit status, restatements and missing periods.
Do not call a trend from a single quarter."""

        evidence = context.join(
            context.company(pack),
            context.financials(pack),
            context.metrics(pack, "fundamental", title="Computed fundamentals"),
            context.metrics(pack, "valuation", "market", title="Valuation and market context"),
            context.shareholding(pack),
            context.coverage(pack),
            "Write your analysis for the stated horizon.",
        )
        output, call_ids, error = ask(llm, "fundamentals_analyst", role, evidence, AnalystOutput)
        return analyst_report("fundamentals_analyst", pack, output, call_ids, error)

    return fundamentals_analyst_node
