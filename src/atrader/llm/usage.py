"""Persistent ledger of model attempts and the daily allowance.

Every dispatched attempt is recorded, including errors and timeouts whose provider
outcome is unknown, because each may have consumed quota. The daily window is the
UTC day; OpenRouter's reset time can differ, so the count is conservative.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from atrader.contracts import ModelCall
from atrader.llm.errors import QuotaExhausted

_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_calls (
    call_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    node TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    requested_model TEXT NOT NULL,
    served_model TEXT,
    provider TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cost REAL,
    status TEXT NOT NULL,
    error TEXT,
    latency_ms INTEGER,
    started_at TEXT NOT NULL,
    day_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_model_calls_run ON model_calls (run_id);
CREATE INDEX IF NOT EXISTS ix_model_calls_day ON model_calls (day_utc);
"""


class UsageLedger:
    def __init__(self, path: Path, daily_limit: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._daily_limit = daily_limit
        self._lock = threading.Lock()
        self._in_flight = 0
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path, timeout=30)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @property
    def daily_limit(self) -> int:
        return self._daily_limit

    def used_today(self) -> int:
        today = datetime.now(UTC).date().isoformat()
        with self._connect() as conn:
            (count,) = conn.execute(
                "SELECT COUNT(*) FROM model_calls WHERE day_utc = ? AND status != 'blocked'",
                (today,),
            ).fetchone()
        return int(count)

    def remaining_today(self) -> int:
        return max(0, self._daily_limit - self.used_today() - self._in_flight)

    @contextmanager
    def slot(self) -> Iterator[None]:
        """Reserve one request from today's allowance for the duration of a dispatch."""
        with self._lock:
            if self.used_today() + self._in_flight >= self._daily_limit:
                raise QuotaExhausted(
                    f"daily allowance of {self._daily_limit} requests is used up "
                    "(ATRADER_DAILY_REQUEST_LIMIT minus reserve)")
            self._in_flight += 1
        try:
            yield
        finally:
            with self._lock:
                self._in_flight -= 1

    def record(self, call: ModelCall) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO model_calls VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (call.call_id, call.run_id, call.node, call.attempt, call.requested_model,
                 call.served_model, call.provider, call.prompt_tokens, call.completion_tokens,
                 call.cost, call.status, call.error, call.latency_ms,
                 call.started_at.isoformat(), call.started_at.astimezone(UTC).date().isoformat()),
            )

    def calls_for_run(self, run_id: str) -> list[ModelCall]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM model_calls WHERE run_id = ? ORDER BY started_at", (run_id,)
            ).fetchall()
        # sqlite3.Row iterates over values, so .keys() is required here.
        return [ModelCall(**{k: row[k] for k in row.keys() if k != "day_utc"})  # noqa: SIM118
                for row in rows]

    def dispatched_for_run(self, run_id: str) -> int:
        return sum(1 for c in self.calls_for_run(run_id) if c.status != "blocked")
