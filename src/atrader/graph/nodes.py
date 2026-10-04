"""The two non-LLM nodes: the data steward at the start and the veto check at the end."""

from atrader.agents.state import AgentState
from atrader.analytics.vetoes import compute_vetoes, enforce
from atrader.contracts import AgentStatus, Assessment, Mode
from atrader.data.evidence_builder import EvidenceSource


def create_data_steward(source: EvidenceSource):
    def data_steward_node(state: AgentState):
        pack = source.build(state["request"])
        return {"pack": pack, "vetoes": compute_vetoes(pack)}

    return data_steward_node


def finalize_node(state: AgentState):
    """Apply the code-enforced vetoes to the portfolio manager's assessment."""
    if state["request"].mode == Mode.DATA_ONLY:
        return {"final_assessment": None}
    synthesis = state.get("final_synthesis")
    if synthesis is None or synthesis.status == AgentStatus.FAILED:
        return {"final_assessment": Assessment.INSUFFICIENT_EVIDENCE}
    return {"final_assessment": enforce(synthesis.assessment, state.get("vetoes", []))}
