"""End-to-end graph tests with a fake gateway: call counts per mode, routing, vetoes,
report output and resume after a quota pause."""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from atrader.agents.utils import RULES
from atrader.contracts import (
    AnalystOutput,
    Assessment,
    DebateOutput,
    Mode,
    ResearchRequest,
    RunStatus,
    SynthesisOutput,
)
from atrader.graph.conditional_logic import ConditionalLogic
from atrader.graph.nodes import create_data_steward
from atrader.graph.research_graph import MODES, ResearchGraph, RunPaused
from atrader.graph.setup import GraphSetup
from atrader.llm import LLM, QuotaExhausted, RunBudget
from atrader.llm.fake import FakeGateway, demo_responder
from tests.conftest import StaticEvidence, make_bars, make_pack


def _run(mode: Mode, pack=None, responder=None):
    gateway = FakeGateway("run-test", responder, budget=RunBudget(MODES[mode]["max_calls"]))
    setup = GraphSetup(LLM(gateway, "quick"), LLM(gateway, "deep"),
                       create_data_steward(StaticEvidence(pack or make_pack())),
                       ConditionalLogic(MODES[mode]["debate_rounds"]))
    graph = setup.setup_graph(mode).compile()
    request = ResearchRequest(symbol="TESTCO", mode=mode)
    return graph.invoke({"run_id": "run-test", "request": request}), gateway


@pytest.mark.parametrize("mode", [Mode.COMPACT, Mode.FULL])
def test_each_mode_makes_exactly_its_planned_calls(mode):
    state, gateway = _run(mode)
    nodes = [c.node for c in gateway.calls()]
    assert len(nodes) == MODES[mode]["planned_calls"]
    assert set(state["analyst_reports"]) == {"market_analyst", "fundamentals_analyst",
                                             "news_analyst"}
    assert [t.side for t in state["debate"]] == ["bull", "bear"] * MODES[mode]["debate_rounds"]
    assert state["final_assessment"] == Assessment.MIXED
    assert nodes[-1] == "portfolio_manager"
    if mode == Mode.FULL:
        assert [r.perspective for r in state["risk_reviews"]] == [
            "aggressive", "conservative", "neutral"]
        assert state["research_decision"] is not None and state["trader_plan"] is not None
    else:
        assert "research_decision" not in state and "trader_plan" not in state


def test_rebuttals_see_and_challenge_earlier_claims():
    state, _ = _run(Mode.FULL)
    rebuttal = state["debate"][2]
    assert rebuttal.phase == "rebuttal" and rebuttal.side == "bull"
    known = {c.claim_id for t in state["debate"][:2] for c in t.claims}
    known |= {c.claim_id for r in state["analyst_reports"].values() for c in r.claims}
    assert rebuttal.challenges and all(c.target_claim_id in known for c in rebuttal.challenges)


def test_analyst_without_evidence_is_skipped_without_a_call():
    pack = make_pack(with_text=False)  # no announcements or news
    state, gateway = _run(Mode.COMPACT, pack)
    assert state["analyst_reports"]["news_analyst"].status == "skipped"
    assert "news_analyst" not in [c.node for c in gateway.calls()]


def test_missing_core_evidence_skips_all_models():
    state, gateway = _run(Mode.COMPACT, make_pack(bars=[], facts=[], with_text=False))
    assert gateway.calls() == []
    assert state["final_assessment"] == Assessment.INSUFFICIENT_EVIDENCE


def test_vetoes_cap_a_supportive_conclusion():
    def supportive(node, schema, prompt):
        answer = demo_responder(node, schema, prompt)
        if schema is SynthesisOutput:
            answer["assessment"] = "supportive"
        return answer

    short_history = make_pack(bars=make_bars(sessions=40))
    state, _ = _run(Mode.COMPACT, short_history, supportive)
    assert state["final_synthesis"].assessment == Assessment.SUPPORTIVE
    assert state["final_assessment"] == Assessment.MIXED


def test_invented_citations_never_reach_the_debate():
    def fabricating(node, schema, prompt):
        if schema is AnalystOutput:
            return {"stance": "supportive", "summary": "s", "claims": [
                {"statement": "Revenue rose 40%.", "kind": "fact", "evidence_ids": ["F999"]}]}
        return demo_responder(node, schema, prompt)

    seen_prompts = []

    def recording(node, schema, prompt):
        if schema is DebateOutput:
            seen_prompts.append(prompt)
        return fabricating(node, schema, prompt)

    state, _ = _run(Mode.COMPACT, responder=recording)
    claims = [c for r in state["analyst_reports"].values() for c in r.claims]
    assert claims and all(c.status == "unsupported" for c in claims)
    assert all("Revenue rose 40%" not in p for p in seen_prompts)


def test_prompts_carry_rules_and_fence_untrusted_text():
    captured = {}

    class Spy(FakeGateway):
        def structured(self, *, node, tier, system, user, schema):
            captured[node] = (system, user)
            return super().structured(node=node, tier=tier, system=system, user=user,
                                      schema=schema)

    gateway = Spy("run-test", budget=RunBudget(8))
    setup = GraphSetup(LLM(gateway, "quick"), LLM(gateway, "deep"),
                       create_data_steward(StaticEvidence(make_pack())), ConditionalLogic(1))
    setup.setup_graph(Mode.COMPACT).compile().invoke(
        {"run_id": "r", "request": ResearchRequest(symbol="TESTCO")})
    system, user = captured["news_analyst"]
    assert RULES in system
    assert "<<<DATA" in user and "<<<END DATA>>>" in user


def test_research_graph_writes_reports(settings):
    graph = ResearchGraph(settings, dry_run=True, evidence_source=StaticEvidence(make_pack()))
    report = graph.run("TESTCO", mode=Mode.COMPACT)
    assert report.status == RunStatus.COMPLETED
    assert len(report.model_calls) == 6
    markdown = (settings.reports_dir / f"{report.report_id}.md").read_text(encoding="utf-8")
    assert "Assessment: Mixed" in markdown and "Bull and bear debate" in markdown
    assert (settings.reports_dir / f"{report.report_id}.json").exists()


def test_data_only_mode_makes_no_calls(settings):
    graph = ResearchGraph(settings, evidence_source=StaticEvidence(make_pack()))
    report = graph.run("TESTCO", mode=Mode.DATA_ONLY)
    assert report.model_calls == [] and report.assessment is None
    assert report.status == RunStatus.COMPLETED


def test_quota_pause_resumes_without_repeating_work(settings, monkeypatch):
    evidence = StaticEvidence(make_pack())
    graph = ResearchGraph(settings, dry_run=True, evidence_source=evidence)
    original = FakeGateway.structured
    state = {"fail": True}

    def flaky(self, *, node, tier, system, user, schema):
        if node == "bear_researcher" and state["fail"]:
            raise QuotaExhausted("daily allowance used up")
        return original(self, node=node, tier=tier, system=system, user=user, schema=schema)

    monkeypatch.setattr(FakeGateway, "structured", flaky)
    with pytest.raises(RunPaused) as paused:
        graph.run("TESTCO", mode=Mode.COMPACT)

    state["fail"] = False
    report = graph.resume(paused.value.run_id)
    assert report.status == RunStatus.COMPLETED
    assert len(evidence.requests) == 1  # the evidence pack was not rebuilt
    nodes = [c.node for c in report.model_calls]
    assert nodes.count("market_analyst") == 0  # completed before the pause, not re-run
    assert nodes == ["bear_researcher", "portfolio_manager"]
    assert len(report.analyst_reports) == 3


def test_in_memory_checkpointer_compiles():
    gateway = FakeGateway("r", budget=RunBudget(8))
    setup = GraphSetup(LLM(gateway, "quick"), LLM(gateway, "deep"),
                       create_data_steward(StaticEvidence(make_pack())), ConditionalLogic(1))
    graph = setup.setup_graph(Mode.COMPACT).compile(checkpointer=InMemorySaver())
    result = graph.invoke({"run_id": "r", "request": ResearchRequest(symbol="TESTCO")},
                          {"configurable": {"thread_id": "r"}})
    assert result["final_assessment"] == Assessment.MIXED
