"""Minimal usage example, in the spirit of TradingAgents' main.py.

    uv run python main.py
"""

from atrader.contracts import Horizon, Mode
from atrader.graph.research_graph import ResearchGraph

# dry_run=True runs the whole graph on real NSE data with placeholder model output,
# so you can see the pipeline before spending any free-tier requests.
graph = ResearchGraph(dry_run=True)
report = graph.run("LT", mode=Mode.COMPACT, horizon=Horizon.SWING)

print(report.assessment, report.status)
print(f"see reports/{report.report_id}.md")
