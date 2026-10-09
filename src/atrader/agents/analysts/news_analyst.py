from atrader.agents import context
from atrader.agents.utils import analyst_report, ask, skipped_report
from atrader.contracts import NewsAnalystOutput


def create_news_analyst(llm):
    def news_analyst_node(state):
        pack = state["pack"]
        if not pack.announcements and not pack.news and not pack.documents:
            return skipped_report("news_analyst", "no disclosures or news headlines")

        role = """\
You are the news and catalyst analyst for a company listed in India. Build a short
timeline of material events from its exchange disclosures and news headlines.
- Prefer the company's own disclosures (A IDs) over headlines (N IDs). A headline reports
  that something happened; it is not proof.
- Orders: an order intimation without an amount, status or execution period is not
  secured revenue. Never add a new award to a reported backlog total.
- When disclosed, identify order amount/currency, customer, funding, execution period,
  margins, cancellation terms and working-capital needs; mark absent terms unknown.
  Only D passages establish attachment contents; links alone do not.
- Extract disclosure_terms for order amount, order status, customer, execution period, margin,
  cancellation, funding, working capital, reported backlog and capacity. Each term
  must include an exact quote from a D passage. An omitted term means unknown, not benign.
- Return management_delivery records with exact promise and outcome quotes from dated
  D passages. A later outcome must postdate the promise; absent outcomes stay unverified.
- Governance: credit ratings, auditor or director changes, litigation and regulatory
  actions. Label allegations as allegations.
- Management delivery: pair dated promises with subsequent disclosed outcomes and cite
  both passages. Unmatched promises remain unverified; record capital-allocation and
  minority-shareholder implications without inventing an execution history.
- Screen broad Updates by their content before deciding materiality. An ambiguous
  summary is a coverage gap, not proof that its unread attachment is immaterial.
- Separate confirmed events from commentary. Treat syndicated copies as one event.
- Name upcoming catalysts only when the evidence states them.
- Rate each material event in events: impact from -2 (clearly negative for the
  company's prospects) to +2 (clearly positive), and materiality low, medium or high
  relative to the company's size. Routine filings are not events; an empty list is a
  valid answer. Cite A or N IDs. Code turns your ratings into the news score and
  counts headline-only events at half weight."""

        evidence = context.join(
            context.company(pack),
            context.announcements(pack),
            context.news(pack),
            context.research_sources(pack),
            context.coverage(pack),
            "Write your analysis.",
        )
        output, call_ids, error = ask(llm, "news_analyst", role, evidence, NewsAnalystOutput)
        return analyst_report("news_analyst", pack, output, call_ids, error)

    return news_analyst_node
