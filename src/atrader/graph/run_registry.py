"""Remembers each run's request and status so a paused run can be resumed."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from atrader.contracts import ResearchRequest, RunStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    request_json TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    status TEXT NOT NULL,
    report_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class RunRegistry:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        with sqlite3.connect(path) as conn:
            conn.executescript(_SCHEMA)

    def create(self, run_id: str, request: ResearchRequest, dry_run: bool) -> None:
        now = datetime.now(UTC).isoformat()
        with sqlite3.connect(self._path) as conn:
            conn.execute("INSERT INTO runs VALUES (?, ?, ?, ?, NULL, ?, ?)",
                         (run_id, request.model_dump_json(), int(dry_run), RunStatus.QUEUED,
                          now, now))

    def get(self, run_id: str) -> tuple[ResearchRequest, bool, RunStatus]:
        with sqlite3.connect(self._path) as conn:
            row = conn.execute("SELECT request_json, dry_run, status FROM runs WHERE run_id = ?",
                               (run_id,)).fetchone()
        if row is None:
            raise LookupError(f"unknown run {run_id}")
        return ResearchRequest.model_validate_json(row[0]), bool(row[1]), RunStatus(row[2])

    def set_status(self, run_id: str, status: RunStatus, report_path: Path | None = None) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                "UPDATE runs SET status = ?, report_path = COALESCE(?, report_path), "
                "updated_at = ? WHERE run_id = ?",
                (status, str(report_path) if report_path else None,
                 datetime.now(UTC).isoformat(), run_id))

    def recent(self, limit: int = 20) -> list[tuple[str, str, str, str | None, str]]:
        with sqlite3.connect(self._path) as conn:
            return conn.execute(
                "SELECT run_id, request_json, status, report_path, created_at FROM runs "
                "ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
