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
results (exchange XBRL), disclosure summaries and Python-computed metrics. You own
business quality, accounting and resilience, capital allocation, and valuation.
Investigate these questions. For each, put a concise finding in claims prefixed by
its topic name, or a named missing-evidence entry in gaps. Never fill a gap from memory.
1. Business model: who pays, repeat demand, segment economics and customer concentration;
   distinguish volume, price, acquisitions and currency when disclosed.
2. Competitive advantage: identify its mechanism, evidence, threats and strengthening
   or weakening direction. A high margin alone does not prove a moat.
3. Reinvestment: compare growth with ROIC and incremental capital needs across years.
   Growth alone does not establish shareholder value creation. Use computed ratios only.
4. Cash conversion: compare multi-year operating cash flow with profit, receivables and
   inventory with sales, maintenance capex, capitalised expenses and exceptional items.
5. Financial resilience: debt maturities, interest coverage, floating rates, restricted
   cash, guarantees and funding commitments. Consider demand, margin and refinancing
   stress together; missing debt data is not evidence of a safe balance sheet.
6. Capital allocation: acquisitions, capex, buybacks, dividends, issuance, related-party
   transactions and compensation. Compare per-share growth with company totals; dilution
   can explain the difference. A promoter percentage change is not proof of buying or
   selling: seek purchase, sale, dilution, buyback or reclassification evidence first.
7. Growth runway: penetration, profitable demand, competing capacity and execution
   constraints. Order awards and announced capacity are not yet profitable revenue.
8. Earnings normality: distinguish structural growth, recovery, low-base effects and
   cyclical windfalls. Use trailing-year comparisons when present; two years are not
   through-cycle normalised earnings. Never use single-quarter PEG as a valuation rule.
9. Price expectations: distinguish business quality from price attractiveness. Explain
   the code-computed price-implied EPS growth and its exit-multiple and return assumptions
   when available. Separate management guidance, analyst consensus, our assumptions and
   price-implied expectations. Do not invent a reverse DCF, margin or reinvestment model.
   Sector index P/E is context, not intrinsic value; a large company can dominate it.
10. Thesis failure: identify decisive assumptions, observable invalidating evidence and
    the next disclosed event that could resolve each; say unknown if no event is dated.
Banks and NBFCs need asset quality, credit costs, capital adequacy and funding/liquidity
analysis; do not apply industrial cash-conversion or ordinary debt rules to them.
Note reporting basis, audit status, restatements, per-share comparability and missing
periods. Do not call a trend from a single quarter. Missing evidence belongs in gaps,
not an uncited positive finding. The news analyst owns the dated management/governance
timeline; the market analyst owns trading and institutional context.
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
            context.announcements(pack),
            context.base_scores(state, Pillar.GROWTH_QUALITY, Pillar.VALUATION),
            context.coverage(pack),
            "Write your analysis.",
        )
        output, call_ids, error = ask(llm, "fundamentals_analyst", role, evidence, AnalystOutput)
        return analyst_report("fundamentals_analyst", pack, output, call_ids, error)

    return fundamentals_analyst_node
