from atrader.agents import context
from atrader.agents.utils import analyst_report, ask, skipped_report
from atrader.contracts import AnalystOutput, Pillar


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
Do not call a trend from a single quarter.
- Python also scored growth_quality and valuation (below, with the points each rule
  added). Adjust either in score_adjustments only if the rules miss something the
  evidence shows (for example a known seasonal quarter or a one-off item), by at most
  15 points, with a reason and evidence IDs. Usually no adjustment is right."""

        evidence = context.join(
            context.company(pack),
            context.financials(pack),
            context.metrics(pack, "fundamental", title="Computed fundamentals"),
            context.metrics(pack, "valuation", "market", title="Valuation and market context"),
            context.shareholding(pack),
            context.base_scores(state, Pillar.GROWTH_QUALITY, Pillar.VALUATION),
            context.coverage(pack),
            "Write your analysis.",
        )
        output, call_ids, error = ask(llm, "fundamentals_analyst", role, evidence, AnalystOutput)
        return analyst_report("fundamentals_analyst", pack, output, call_ids, error)

    return fundamentals_analyst_node
