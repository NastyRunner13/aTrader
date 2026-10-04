"""Graph state shared by every agent.

Analysts run in parallel, so each writes its own key in `analyst_reports` (merged by a
reducer) instead of overwriting a shared field. Debate turns and risk reviews append.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from atrader.contracts import (
    AgentReport,
    Assessment,
    DebateTurn,
    EvidencePack,
    JudgeVerdict,
    ResearchRequest,
    RiskReview,
    StrategyPlan,
    Synthesis,
    Veto,
)


def merge_reports(left: dict[str, AgentReport] | None,
                  right: dict[str, AgentReport] | None) -> dict[str, AgentReport]:
    return {**(left or {}), **(right or {})}


class AgentState(TypedDict, total=False):
    run_id: str
    request: ResearchRequest

    # data steward
    pack: EvidencePack | None
    vetoes: list[Veto]

    # analyst team
    analyst_reports: Annotated[dict[str, AgentReport], merge_reports]

    # research team
    debate: Annotated[list[DebateTurn], operator.add]
    research_decision: JudgeVerdict | None  # research manager

    # trader (hypothetical plan, never an order)
    trader_plan: StrategyPlan | None

    # risk team
    risk_reviews: Annotated[list[RiskReview], operator.add]

    # portfolio manager + code-enforced vetoes
    final_synthesis: Synthesis | None
    final_assessment: Assessment | None
