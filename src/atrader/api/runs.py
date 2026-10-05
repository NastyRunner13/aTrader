"""Runs started from the web app: one worker, a queue behind it, and an event log per run
that the page follows live. Run state itself lives in the `RunRegistry`; this module adds
only what a browser needs on top of it."""

from __future__ import annotations

import logging
import threading
import uuid
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from atrader.config import Settings
from atrader.contracts import Mode, ResearchRequest, RunStatus
from atrader.graph.research_graph import MODES, ResearchGraph, RunCancelled, RunPaused
from atrader.graph.run_registry import RunRegistry
from atrader.llm import QuotaExhausted
from atrader.llm.usage import UsageLedger

logger = logging.getLogger(__name__)

RESUMABLE = (RunStatus.FAILED, RunStatus.PAUSED_QUOTA, RunStatus.CANCELLED)
KEEP_FINISHED = 50  # finished runs whose event logs stay in memory

# What the run page lists, in order. Node names are the graph's.
_ANALYSTS = ["market_analyst", "fundamentals_analyst", "news_analyst"]
_DEBATE = ["bull_researcher", "bear_researcher"]
_RISK = ["aggressive_debator", "conservative_debator", "neutral_debator"]


class CannotStart(Exception):
    """A run cannot be accepted right now. `code` tells the page which message to show."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def plan(mode: Mode) -> list[dict[str, Any]]:
    stages = [("evidence", "Collect NSE evidence", ["data_steward"])]
    if mode != Mode.DATA_ONLY:
        stages += [("analysts", "Analyst reports", _ANALYSTS),
                   ("debate", "Bull and bear debate", _DEBATE)]
        if mode == Mode.FULL:
            stages.append(("risk", "Risk review", _RISK))
        stages.append(("manager", "Portfolio manager", ["portfolio_manager"]))
    stages.append(("scorecard", "Scorecard", ["finalize"]))
    return [{"key": key, "label": label, "nodes": nodes} for key, label, nodes in stages]


class LiveRun:
    """The event log and progress counters of one run while the server holds it."""

    def __init__(self, run_id: str, request: ResearchRequest, dry_run: bool) -> None:
        self.run_id = run_id
        self.request = request
        self.dry_run = dry_run
        self.events: list[dict[str, Any]] = []
        self.cancel = threading.Event()
        self.active = True
        self.report_id: str | None = None
        self._started: Counter[str] = Counter()
        self._finished: Counter[str] = Counter()
        self._failed: set[str] = set()
        self._changed = threading.Condition()

    def reopen(self) -> None:
        """Resume: keep the log and counters, so the page continues where it stopped."""
        with self._changed:
            self.cancel.clear()
            self.active = True
            self._failed.clear()
            self._started = Counter(self._finished)  # a node cut off mid-call starts again
        self.emit("status", status="queued")

    def emit(self, kind: str, **fields: Any) -> None:
        with self._changed:
            if kind == "node":
                node = fields["node"]
                if fields["phase"] == "start":
                    self._started[node] += 1
                elif fields["phase"] == "done":
                    self._finished[node] += 1
                else:
                    self._failed.add(node)
            self.events.append({"id": len(self.events) + 1, "type": kind, **fields})
            self._changed.notify_all()

    def finish(self, status: str, **fields: Any) -> None:
        self.emit("end", status=status, **fields)
        with self._changed:
            self.active = False
            self._changed.notify_all()

    def wait_for(self, after: int, timeout: float) -> tuple[list[dict[str, Any]], bool]:
        """Events after id `after`, waiting up to `timeout` s for one; and whether the run
        is still going."""
        with self._changed:
            if len(self.events) <= after and self.active:
                self._changed.wait(timeout)
            return self.events[after:], self.active

    def stages(self, mode: Mode, status: str) -> list[dict[str, Any]]:
        rounds = MODES[mode]["debate_rounds"]
        out = []
        for stage in plan(mode):
            nodes = stage["nodes"]
            expected = {n: rounds if n in _DEBATE else 1 for n in nodes}
            running = any(self._started[n] > self._finished[n] for n in nodes)
            complete = all(self._finished[n] >= expected[n] for n in nodes)
            touched = any(self._started[n] or self._finished[n] for n in nodes)
            out.append({**stage, "state": "error" if self._failed & set(nodes) else
                        "running" if running else "done" if complete else
                        "partial" if touched else "pending"})
        # Stages run in order, so activity in a later stage means the earlier ones are done:
        # this also covers a resumed run, whose finished stages never fire again.
        last_active = max((i for i, s in enumerate(out) if s["state"] != "pending"), default=-1)
        for i, stage in enumerate(out):
            if stage["state"] in ("pending", "partial") and i < last_active:
                stage["state"] = "done"
        if status in (RunStatus.COMPLETED, RunStatus.PARTIAL):
            for stage in out:  # never reached: the graph went straight to the scorecard
                if stage["state"] == "pending":
                    stage["state"] = "skipped"
        return out


class RunManager:
    def __init__(self, settings: Settings,
                 make_graph: Callable[..., ResearchGraph] | None = None) -> None:
        self._settings = settings
        self._registry = RunRegistry(settings.db_path)
        self._registry.interrupt_unfinished()
        self._ledger = UsageLedger(settings.db_path, settings.usable_daily_requests)
        self._make_graph = make_graph or (lambda **kw: ResearchGraph(settings, **kw))
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="atrader-run")
        self._live: dict[str, LiveRun] = {}
        self._lock = threading.Lock()

    # --- commands ------------------------------------------------------------------------

    def submit(self, request: ResearchRequest, dry_run: bool) -> str:
        """Queue a run and return its ID. An identical run already queued or running is
        returned instead of starting a second one."""
        self._check_can_start(request.mode, dry_run)
        with self._lock:
            active = [r for r in self._live.values() if r.active]
            for run in active:
                if run.request == request and run.dry_run == dry_run:
                    return run.run_id
            if len(active) >= self._settings.max_queued_runs:
                raise CannotStart("queue_full", f"{len(active)} runs are already waiting; "
                                  "wait for one to finish or cancel it")
            run_id = uuid.uuid4().hex
            self._registry.create(run_id, request, dry_run)
            live = self._live[run_id] = LiveRun(run_id, request, dry_run)
            live.emit("status", status="queued")
            self._prune()
        self._pool.submit(self._work, run_id, request, dry_run, False)
        return run_id

    def resume(self, run_id: str) -> str:
        row = self._registry.row(run_id)
        with self._lock:
            live = self._live.get(run_id)
            if (live and live.active) or RunStatus(row["status"]) not in RESUMABLE:
                raise CannotStart("not_resumable", "only a failed, cancelled or quota-paused "
                                  "run can be resumed")
            self._check_can_start(row["request"].mode, row["dry_run"])
            live = self._live[run_id] = live or LiveRun(run_id, row["request"], row["dry_run"])
            live.reopen()
        self._pool.submit(self._work, run_id, row["request"], row["dry_run"], True)
        return run_id

    def cancel(self, run_id: str) -> None:
        """Stop scheduling new work. A model call already in flight still finishes."""
        self._registry.row(run_id)  # unknown run: LookupError
        live = self._live.get(run_id)
        if live and live.active and not live.cancel.is_set():
            live.cancel.set()
            live.emit("status", status="cancel_requested")

    # --- reads ---------------------------------------------------------------------------

    def snapshot(self, run_id: str) -> dict[str, Any]:
        out = self._summary(self._registry.row(run_id))
        live = self._live.get(run_id)
        out["stages"] = live.stages(Mode(out["request"]["mode"]), out["status"]) if live else []
        out["last_event_id"] = len(live.events) if live else 0
        return out

    def recent(self, limit: int = 30) -> list[dict[str, Any]]:
        return [self._summary(row) for row in self._registry.rows(limit)]

    def live(self, run_id: str) -> LiveRun | None:
        return self._live.get(run_id)

    def usage(self) -> dict[str, int]:
        s = self._settings
        return {"used_today": self._ledger.used_today(), "usable": s.usable_daily_requests,
                "remaining": self._ledger.remaining_today(), "daily_limit": s.daily_request_limit,
                "reserve": s.daily_request_reserve}

    def active_count(self) -> int:
        return sum(1 for r in self._live.values() if r.active)

    # --- internals -----------------------------------------------------------------------

    def _summary(self, row: dict[str, Any]) -> dict[str, Any]:
        live = self._live.get(row["run_id"])
        path = row["report_path"]
        request = row["request"]
        return {
            "run_id": row["run_id"],
            "status": row["status"],
            "detail": row["detail"],
            "request": {"symbol": request.symbol, "mode": request.mode.value,
                        "cutoff": request.cutoff.isoformat() if request.cutoff else None},
            "dry_run": row["dry_run"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "report_id": (live.report_id if live and live.report_id else
                          Path(path).stem if path else None),
            "cancel_requested": bool(live and live.active and live.cancel.is_set()),
        }

    def _check_can_start(self, mode: Mode, dry_run: bool) -> None:
        if dry_run or mode == Mode.DATA_ONLY:
            return  # no model request is made
        if self._settings.openrouter_api_key is None:
            raise CannotStart("no_api_key", "No OpenRouter key is set. Add OPENROUTER_API_KEY "
                              "to .env, or run a data-only scorecard.")
        needed, remaining = MODES[mode]["max_calls"], self._ledger.remaining_today()
        if remaining < needed:
            raise CannotStart("quota", f"This run may need up to {needed} model requests but "
                              f"only {remaining} remain today. Try data-only, or wait for the "
                              "daily allowance to reset.")

    def _prune(self) -> None:
        finished = [r for r in self._live.values() if not r.active]
        for run in finished[:-KEEP_FINISHED]:
            del self._live[run.run_id]

    def _work(self, run_id: str, request: ResearchRequest, dry_run: bool, resume: bool) -> None:
        live = self._live[run_id]
        if live.cancel.is_set():  # cancelled while it waited in the queue
            self._registry.set_status(run_id, RunStatus.CANCELLED)
            live.finish(RunStatus.CANCELLED.value)
            return
        live.emit("status", status="running")
        try:
            graph = self._make_graph(
                dry_run=dry_run, should_cancel=live.cancel.is_set,
                on_progress=lambda message: live.emit("progress", message=message),
                on_event=lambda event: live.emit("node", **event))
            report = (graph.resume(run_id) if resume else
                      graph.run(request.symbol, mode=request.mode, cutoff=request.cutoff,
                                run_id=run_id))
        except RunPaused as exc:
            live.finish(RunStatus.PAUSED_QUOTA.value, detail=str(exc))
        except RunCancelled:
            live.finish(RunStatus.CANCELLED.value)
        except QuotaExhausted as exc:  # raised before the graph starts: today's allowance
            self._registry.set_status(run_id, RunStatus.PAUSED_QUOTA, detail=str(exc))
            live.finish(RunStatus.PAUSED_QUOTA.value, detail=str(exc))
        except Exception as exc:
            logger.exception("run %s failed", run_id)
            detail = f"{type(exc).__name__}: {exc}"
            self._registry.set_status(run_id, RunStatus.FAILED, detail=detail)
            live.finish(RunStatus.FAILED.value, detail=detail)
        else:
            live.report_id = report.report_id
            live.finish(report.status.value, report_id=report.report_id)
