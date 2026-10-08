"""End-to-end graph tests with a fake gateway: call counts per mode, parallel steps,
routing, the scorecard, vetoes, report output and resume after a quota pause."""

from __future__ import annotations

import re
import threading

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from atrader.agents.utils import RULES
from atrader.contracts import (
    AnalystOutput,
    DebateOutput,
    Horizon,
    Mode,
    Pillar,
    ResearchRequest,
    RunStatus,
    Signal,
    SynthesisOutput,
)
from atrader.graph.conditional_logic import ConditionalLogic
from atrader.graph.nodes import create_data_steward
from atrader.graph.research_graph import MODES, ResearchGraph, RunPaused
from atrader.graph.setup import GraphSetup
from atrader.llm import LLM, QuotaExhausted, RunBudget
from atrader.llm.fake import FakeGateway, demo_responder
from tests.conftest import StaticEvidence, make_bars, make_index, make_pack

EVIDENCE_ID = re.compile(r"\[([FMASN]\d+)\]")


def _run(mode: Mode, pack=None, responder=None):
    gateway = FakeGateway("run-test", responder, budget=RunBudget(MODES[mode]["max_calls"]))
    evidence = StaticEvidence(pack or make_pack(indices=(make_index(),)))
    setup = GraphSetup(LLM(gateway, "quick"), LLM(gateway, "deep"),
                       create_data_steward(evidence),
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
    rounds = MODES[mode]["debate_rounds"]
    assert [(t.turn_index, t.side) for t in state["debate"]] == [
        (i + 1, side) for i, side in enumerate(["bull", "bear"] * rounds)]
    assert nodes[-1] == "portfolio_manager"
    card = state["scorecard"]
    assert [h.horizon for h in card.horizons] == list(Horizon)
    assert all(h.signal != Signal.INSUFFICIENT_DATA for h in card.horizons)
    if mode == Mode.FULL:
        assert [r.perspective for r in state["risk_reviews"]] == [
            "aggressive", "conservative", "neutral"]
    else:
        assert not state.get("risk_reviews")


def test_agents_in_the_same_step_run_at_the_same_time():
    # Each group waits until all its members are in a call at once. If the graph ran
    # them one after another, the barrier would time out and break the run.
    groups = {"_analyst": threading.Barrier(3, timeout=10),
              "_researcher": threading.Barrier(2, timeout=10),
              "_debator": threading.Barrier(3, timeout=10)}

    def meeting(node, schema, prompt):
        for suffix, barrier in groups.items():
            if node.endswith(suffix):
                barrier.wait()
        return demo_responder(node, schema, prompt)

    state, gateway = _run(Mode.FULL, responder=meeting)
    assert len(gateway.calls()) == MODES[Mode.FULL]["planned_calls"]
    assert len(state["risk_reviews"]) == 3


def test_debate_rounds_see_the_previous_round_only():
    prompts: dict[str, list[str]] = {"bull_researcher": [], "bear_researcher": []}

    def recording(node, schema, prompt):
        if schema is DebateOutput:
            prompts[node].append(prompt)
        return demo_responder(node, schema, prompt)

    state, _ = _run(Mode.FULL, responder=recording)
    for opening, rebuttal in prompts.values():
        assert "## Debate so far" not in opening  # openings are written at the same time
        assert "Turn 1: bull opening" in rebuttal and "Turn 2: bear opening" in rebuttal
        assert "Turn 3" not in rebuttal and "Turn 4" not in rebuttal
    assert [t.phase for t in state["debate"]] == ["opening", "opening", "rebuttal", "rebuttal"]


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
    news = state["scorecard"].pillar(Pillar.NEWS)
    assert news.score is None and "no disclosures" in (news.note or "")


def test_missing_core_evidence_skips_all_models():
    state, gateway = _run(Mode.COMPACT, make_pack(bars=[], facts=[], with_text=False))
    assert gateway.calls() == []
    assert all(h.signal == Signal.INSUFFICIENT_DATA and h.score is None
               for h in state["scorecard"].horizons)


def test_cap_vetoes_hold_scores_at_neutral():
    def eager(node, schema, prompt):
        answer = demo_responder(node, schema, prompt)
        if schema is SynthesisOutput:
            for note in answer["horizons"]:
                note.update(adjustment=5, adjustment_reason="test")
        return answer

    short_history = make_pack(bars=make_bars(sessions=40), indices=(make_index(),))
    state, _ = _run(Mode.COMPACT, short_history, eager)
    six_months = state["scorecard"].horizon(Horizon.SIX_MONTHS)
    assert six_months.score == 55 and six_months.signal == Signal.NEUTRAL
    assert "short_price_history" in six_months.capped_by
    assert all(h.score is None or h.score <= 55 for h in state["scorecard"].horizons)


def test_analyst_adjustments_are_verified_and_clamped():
    def adjusting(node, schema, prompt):
        answer = demo_responder(node, schema, prompt)
        if node == "market_analyst":
            metric = next(i for i in EVIDENCE_ID.findall(prompt) if i.startswith("M"))
            answer["score_adjustments"] = [
                {"pillar": "technical", "points": 30, "reason": "rules miss it",
                 "evidence_ids": [metric]},
                {"pillar": "valuation", "points": -10, "reason": "not mine",
                 "evidence_ids": [metric]}]
        if node == "fundamentals_analyst":
            answer["score_adjustments"] = [{"pillar": "growth_quality", "points": 10,
                                            "reason": "invented", "evidence_ids": ["F999"]}]
        return answer

    state, _ = _run(Mode.COMPACT, responder=adjusting)
    market = state["analyst_reports"]["market_analyst"].score_adjustments
    assert [(a.pillar, a.points) for a in market] == [(Pillar.TECHNICAL, 15)]
    assert state["analyst_reports"]["fundamentals_analyst"].score_adjustments == []
    technical = state["scorecard"].pillar(Pillar.TECHNICAL)
    assert technical.adjustment == 15 and technical.score == min(100, technical.base + 15)
    assert state["scorecard"].pillar(Pillar.GROWTH_QUALITY).adjustment == 0


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
    claims = [c for key in ("market_analyst", "fundamentals_analyst")
              for c in state["analyst_reports"][key].claims]
    assert claims and all(c.status == "unsupported" for c in claims)
    assert all("Revenue rose 40%" not in p for p in seen_prompts)


def test_prompts_carry_rules_scores_and_fence_untrusted_text():
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
    assert "### technical:" in captured["market_analyst"][1]
    assert "### valuation:" in captured["fundamentals_analyst"][1]
    # Business/governance research must receive the disclosure evidence it is asked to read.
    assert "[A1]" in captured["fundamentals_analyst"][1]
    assert "Percentages alone" in captured["fundamentals_analyst"][1]
    assert "## Draft scorecard" in captured["portfolio_manager"][1]


def test_research_graph_writes_card_details_and_json(settings):
    graph = ResearchGraph(settings, dry_run=True, evidence_source=StaticEvidence(make_pack()))
    report = graph.run("TESTCO", mode=Mode.COMPACT)
    assert report.status == RunStatus.COMPLETED
    assert len(report.model_calls) == 6
    card = (settings.reports_dir / f"{report.report_id}.md").read_text(encoding="utf-8")
    assert "| **Signal** |" in card and "## Scores by area" in card and "## Pros" in card
    assert "Experimental" in card and f"{report.report_id}-details.md" in card
    details = (settings.reports_dir / f"{report.report_id}-details.md").read_text(
        encoding="utf-8")
    assert "## Score breakdown" in details and "Bull and bear debate" in details
    assert (settings.reports_dir / f"{report.report_id}.json").exists()


def test_data_only_mode_gives_a_code_only_scorecard(settings):
    graph = ResearchGraph(settings, evidence_source=StaticEvidence(make_pack()))
    report = graph.run("TESTCO", mode=Mode.DATA_ONLY)
    assert report.model_calls == [] and report.status == RunStatus.COMPLETED
    card = report.scorecard
    assert card is not None and not card.model_adjusted
    assert card.pillar(Pillar.NEWS).score is None
    assert card.horizon(Horizon.ONE_MONTH).score is not None  # 60% covered without valuation
    assert card.horizon(Horizon.TWO_YEARS).score is None  # only 50% without valuation or news
    assert card.levels is not None and card.levels.levels and card.levels.flips
    text = (settings.reports_dir / f"{report.report_id}.md").read_text(encoding="utf-8")
    assert "code-only scorecard" in text and "## Pros" in text  # pros from the rules
    assert "## Price levels" in text and "**Last close**" in text and "Signal flips" in text
    details = (settings.reports_dir / f"{report.report_id}-details.md").read_text(
        encoding="utf-8")
    assert "### Signal flips" in details and "_trend_" in details


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
    assert len(report.analyst_reports) == 3 and len(report.debate) == 2


def test_in_memory_checkpointer_compiles():
    gateway = FakeGateway("r", budget=RunBudget(8))
    setup = GraphSetup(LLM(gateway, "quick"), LLM(gateway, "deep"),
                       create_data_steward(StaticEvidence(make_pack())), ConditionalLogic(1))
    graph = setup.setup_graph(Mode.COMPACT).compile(checkpointer=InMemorySaver())
    result = graph.invoke({"run_id": "r", "request": ResearchRequest(symbol="TESTCO")},
                          {"configurable": {"thread_id": "r"}})
    assert result["scorecard"] is not None
