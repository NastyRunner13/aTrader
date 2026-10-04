from atrader.agents import context
from atrader.agents.utils import ask
from atrader.contracts import AgentStatus, Assessment, JudgeOutput, JudgeVerdict


def create_research_manager(llm):
    def research_manager_node(state):
        pack = state["pack"]

        role = """\
You are the research manager. Judge the bull/bear debate for the stated horizon.
- Weigh factual support and decision relevance, not eloquence or the number of points.
- For each material dispute, say whether the evidence settles it (resolved) or not
  (unresolved). A missing fact stays unresolved.
- List the claim IDs that decided your assessment.
- "balanced" and insufficient_evidence are legitimate outcomes."""

        evidence = context.join(
            context.all_evidence(pack),
            context.analyst_reports(state),
            context.debate(state),
            context.vetoes(state),
            "Give your verdict on the debate.",
        )
        output, call_ids, error = ask(llm, "research_manager", role, evidence, JudgeOutput)
        if output is None:
            return {"research_decision": JudgeVerdict(
                stronger_side="balanced", assessment=Assessment.INSUFFICIENT_EVIDENCE,
                rationale=f"Research manager unavailable: {error}", status=AgentStatus.FAILED,
                model_call_ids=call_ids)}

        known = {c.claim_id for r in state.get("analyst_reports", {}).values() for c in r.claims}
        known |= {c.claim_id for t in state.get("debate", []) for c in t.claims}
        decision = JudgeVerdict(
            **output.model_dump(exclude={"decisive_claim_ids"}),
            decisive_claim_ids=[c for c in output.decisive_claim_ids if c in known],
            model_call_ids=call_ids,
        )
        return {"research_decision": decision}

    return research_manager_node
