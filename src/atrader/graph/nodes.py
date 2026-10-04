"""The non-LLM nodes: the data steward at the start, the debate-round join, and the
scorecard at the end."""

from atrader.agents.state import AgentState
from atrader.analytics.scoring import base_scores, build_scorecard, score_pillars
from atrader.analytics.vetoes import compute_vetoes
from atrader.contracts import AgentStatus, Mode
from atrader.data.evidence_builder import EvidenceSource


def create_data_steward(source: EvidenceSource):
    def data_steward_node(state: AgentState):
        pack = source.build(state["request"])
        return {"pack": pack, "vetoes": compute_vetoes(pack), "base_scores": base_scores(pack)}

    return data_steward_node


def debate_round_node(state: AgentState):
    """Waits for every speaker of a step (the analysts, or bull and bear), so the next
    debate round starts from the same state on both sides. It changes nothing."""
    return {}


def finalize_node(state: AgentState):
    """Build the scorecard: code scores plus the analysts' verified adjustments and news
    ratings, horizon weights, the portfolio manager's ±5, then the vetoes."""
    pack = state.get("pack")
    if pack is None:
        return {"scorecard": None}
    pillars = score_pillars(state.get("base_scores", {}), state.get("analyst_reports", {}))
    synthesis = state.get("final_synthesis")
    notes = synthesis.horizons if synthesis and synthesis.status == AgentStatus.COMPLETED else []
    model_adjusted = state["request"].mode != Mode.DATA_ONLY and bool(
        state.get("analyst_reports"))
    return {"scorecard": build_scorecard(pack, pillars, state.get("vetoes", []), notes,
                                         model_adjusted=model_adjusted)}
