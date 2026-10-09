"""ResearchGraph: the entry point (the equivalent of TradingAgentsGraph upstream).

    graph = ResearchGraph()
    report = graph.run("LT", mode=Mode.COMPACT)
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import ExitStack, closing
from datetime import date

from langgraph.checkpoint.sqlite import SqliteSaver

from atrader.config import Settings, get_settings
from atrader.contracts import Mode, ResearchReport, ResearchRequest, RunStatus
from atrader.data.evidence_builder import EvidenceSource, NseEvidenceBuilder
from atrader.data.http import PoliteClient
from atrader.data.store import MarketStore
from atrader.graph.conditional_logic import ConditionalLogic
from atrader.graph.nodes import create_data_steward
from atrader.graph.run_registry import RunRegistry
from atrader.graph.setup import GraphSetup
from atrader.llm import LLM, AuthError, LLMGateway, OpenRouterGateway, QuotaExhausted, RunBudget
from atrader.llm.fake import FakeGateway
from atrader.llm.openrouter import OpenRouterClient
from atrader.llm.policy import FreeModelPolicy
from atrader.llm.usage import UsageLedger
from atrader.report.builder import build_report
from atrader.report.writer import write_report

# Model calls per mode (docs/08). The cap covers retries and schema repairs.
# compact: 3 analysts + bull + bear + portfolio manager.
# full: 3 analysts + 2 debate rounds of 2 + 3 risk reviewers + portfolio manager.
MODES = {
    Mode.DATA_ONLY: {"debate_rounds": 0, "planned_calls": 0, "max_calls": 0},
    Mode.BASELINE: {"debate_rounds": 0, "planned_calls": 1, "max_calls": 2},
    Mode.COMPACT: {"debate_rounds": 1, "planned_calls": 6, "max_calls": 8},
    Mode.FULL: {"debate_rounds": 2, "planned_calls": 11, "max_calls": 14},
}


class RunPaused(RuntimeError):
    def __init__(self, run_id: str, reason: str) -> None:
        super().__init__(f"run {run_id} paused: {reason}")
        self.run_id = run_id


class RunCancelled(RuntimeError):
    def __init__(self, run_id: str) -> None:
        super().__init__(f"run {run_id} cancelled")
        self.run_id = run_id


class ResearchGraph:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        dry_run: bool = False,
        evidence_source: EvidenceSource | None = None,
        selected_analysts: tuple[str, ...] = ("market", "fundamentals", "news"),
        on_progress: Callable[[str], None] | None = None,
        on_event: Callable[[dict[str, str]], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self.dry_run = dry_run
        self.selected_analysts = selected_analysts
        self._evidence_source = evidence_source
        self._on_progress = on_progress
        self._on_event = on_event  # one {"node", "phase"} event as each graph node starts/ends
        self._should_cancel = should_cancel  # checked between nodes; stops new work, not calls
        self._runs = RunRegistry(self.settings.db_path)

    def run(self, symbol: str, *, mode: Mode = Mode.COMPACT, cutoff: date | None = None,
            run_id: str | None = None) -> ResearchReport:
        request = ResearchRequest(symbol=symbol, mode=mode, cutoff=cutoff)
        return self._execute(run_id or uuid.uuid4().hex, request, self.dry_run, new=True)

    def resume(self, run_id: str) -> ResearchReport:
        request, dry_run, _ = self._runs.get(run_id)
        return self._execute(run_id, request, dry_run, new=False)

    # --- internals -----------------------------------------------------------------------

    def _execute(self, run_id: str, request: ResearchRequest, dry_run: bool,
                 new: bool) -> ResearchReport:
        with ExitStack() as stack:
            gateway = self._gateway(run_id, request.mode, dry_run, stack)
            if new and not self._runs.exists(run_id):  # the API registers a run when queued
                self._runs.create(run_id, request, dry_run)
            setup = GraphSetup(
                quick_llm=LLM(gateway, "quick"),
                deep_llm=LLM(gateway, "deep"),
                data_steward=create_data_steward(self._evidence(stack)),
                conditional_logic=ConditionalLogic(MODES[request.mode]["debate_rounds"]),
            )
            workflow = setup.setup_graph(request.mode, self.selected_analysts)
            saver = stack.enter_context(
                SqliteSaver.from_conn_string(str(self.settings.checkpoint_path)))
            graph = workflow.compile(checkpointer=saver)
            config = {"configurable": {"thread_id": run_id}, "recursion_limit": 60}
            inputs = {"run_id": run_id, "request": request} if new else None

            self._runs.set_status(run_id, RunStatus.RUNNING)
            try:
                self._stream(graph, inputs, config, run_id)
                state = graph.get_state(config).values
            except QuotaExhausted as exc:
                self._runs.set_status(run_id, RunStatus.PAUSED_QUOTA, detail=str(exc))
                raise RunPaused(run_id, str(exc)) from exc
            except RunCancelled:
                self._runs.set_status(run_id, RunStatus.CANCELLED)
                raise
            except BaseException as exc:
                self._runs.set_status(run_id, RunStatus.FAILED, detail=str(exc))
                raise
            report = build_report(run_id, request, state, gateway.calls())

        card_path, *_ = write_report(report, self.settings.reports_dir)
        self._runs.set_status(run_id, report.status, card_path)
        return report

    def _stream(self, graph, inputs, config, run_id: str) -> None:  # type: ignore[no-untyped-def]
        """Run the graph to its end, reporting each node as it starts and finishes."""
        with closing(graph.stream(inputs, config, stream_mode="tasks")) as events:
            for event in events:
                if self._on_event is not None:
                    phase = "start" if "triggers" in event else (
                        "error" if event.get("error") else "done")
                    self._on_event({"node": event["name"], "phase": phase})
                if self._should_cancel is not None and self._should_cancel():
                    raise RunCancelled(run_id)

    def _gateway(self, run_id: str, mode: Mode, dry_run: bool, stack: ExitStack) -> LLMGateway:
        cap = MODES[mode]["max_calls"]
        if dry_run or mode == Mode.DATA_ONLY:
            return FakeGateway(run_id, budget=RunBudget(cap))

        settings = self.settings
        if settings.openrouter_api_key is None:
            raise AuthError("Set OPENROUTER_API_KEY in .env, or run with --dry-run.")
        client = OpenRouterClient(settings.openrouter_api_key.get_secret_value(),
                                  settings.openrouter_base_url, settings.request_timeout_s)
        stack.callback(client.close)
        policy = FreeModelPolicy(client.list_models(), frozenset(settings.model_allowlist))
        for model in {settings.quick_model, settings.deep_model}:
            policy.check(model)  # fail before any work if a configured model is not free

        ledger = UsageLedger(settings.db_path, settings.usable_daily_requests)
        used = ledger.dispatched_for_run(run_id)
        if ledger.remaining_today() < cap - used:
            raise QuotaExhausted(
                f"this run may need up to {cap - used} requests but only "
                f"{ledger.remaining_today()} remain today")
        return OpenRouterGateway(
            run_id=run_id, client=client, policy=policy, ledger=ledger,
            budget=RunBudget(cap, already_used=used),
            models={"quick": settings.quick_model, "deep": settings.deep_model},
            max_output_tokens=settings.max_output_tokens, temperature=settings.temperature,
            max_concurrency=settings.max_concurrent_requests,
            reasoning_effort=settings.reasoning_effort,
        )

    def _evidence(self, stack: ExitStack) -> EvidenceSource:
        if self._evidence_source is not None:
            return self._evidence_source
        client = stack.enter_context(
            PoliteClient(self.settings.cache_dir, self.settings.http_min_interval_s))
        return NseEvidenceBuilder(client, MarketStore(self.settings.db_path), self.settings,
                                  on_progress=self._on_progress)
