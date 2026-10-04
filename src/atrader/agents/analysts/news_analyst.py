from atrader.agents import context
from atrader.agents.utils import analyst_report, ask, skipped_report
from atrader.contracts import AnalystOutput


def create_news_analyst(llm):
    def news_analyst_node(state):
        pack = state["pack"]
        if not pack.announcements and not pack.news:
            return skipped_report("news_analyst", "no disclosures or news headlines")

        role = """\
You are the news and catalyst analyst for a company listed in India. Build a short
timeline of material events from its exchange disclosures and news headlines.
- Prefer the company's own disclosures (A IDs) over headlines (N IDs). A headline reports
  that something happened; it is not proof.
- Orders: an order intimation without an amount, status or execution period is not
  secured revenue. Never add a new award to a reported backlog total.
- Governance: credit ratings, auditor or director changes, litigation and regulatory
  actions. Label allegations as allegations.
- Separate confirmed events from commentary. Treat syndicated copies as one event.
- Name upcoming catalysts only when the evidence states them."""

        evidence = context.join(
            context.company(pack),
            context.announcements(pack),
            context.news(pack),
            context.coverage(pack),
            "Write your analysis for the stated horizon.",
        )
        output, call_ids, error = ask(llm, "news_analyst", role, evidence, AnalystOutput)
        return analyst_report("news_analyst", pack, output, call_ids, error)

    return news_analyst_node
