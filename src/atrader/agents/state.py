"""Graph state shared by every agent.

Agents in the same step run in parallel (the analysts; bull and bear in each debate
round; the three risk reviewers), so each writes to a reducer instead of overwriting a
shared field. The reducers keep a stable order whatever order the writes arrive in.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from atrader.contracts import (
    AgentReport,
    DebateTurn,
    EvidencePack,
    PillarScore,
    ResearchRequest,
    RiskReview,
    Scorecard,
    Synthesis,
    Veto,
)

_PERSPECTIVES = ("aggressive", "conservative", "neutral")


def merge_reports(left: dict[str, AgentReport] | None,
                  right: dict[str, AgentReport] | None) -> dict[str, AgentReport]:
    return {**(left or {}), **(right or {})}


def add_turns(left: list[DebateTurn] | None, right: list[DebateTurn] | None) -> list[DebateTurn]:
    return sorted([*(left or []), *(right or [])], key=lambda t: t.turn_index)


def add_reviews(left: list[RiskReview] | None, right: list[RiskReview] | None) -> list[RiskReview]:
    return sorted([*(left or []), *(right or [])],
                  key=lambda r: _PERSPECTIVES.index(r.perspective))


class AgentState(TypedDict, total=False):
    run_id: str
    request: ResearchRequest

    # data steward (code)
    pack: EvidencePack | None
    vetoes: list[Veto]
    base_scores: dict[str, PillarScore]  # keyed by pillar value

    # analyst team
    analyst_reports: Annotated[dict[str, AgentReport], merge_reports]

    # research team
    debate: Annotated[list[DebateTurn], add_turns]

    # risk team
    risk_reviews: Annotated[list[RiskReview], add_reviews]

    # portfolio manager, then the scorecard built in code
    final_synthesis: Synthesis | None
    scorecard: Scorecard | None
