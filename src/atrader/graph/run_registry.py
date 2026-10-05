"""Remembers each run's request and status so a paused run can be resumed."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atrader.contracts import ResearchRequest, RunStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    request_json TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    status TEXT NOT NULL,
    report_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    detail TEXT
);
"""


class RunRegistry:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        with sqlite3.connect(path) as conn:
            conn.executescript(_SCHEMA)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
            if "detail" not in columns:  # databases from before the web app
                conn.execute("ALTER TABLE runs ADD COLUMN detail TEXT")

    def create(self, run_id: str, request: ResearchRequest, dry_run: bool) -> None:
        now = datetime.now(UTC).isoformat()
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                "INSERT INTO runs (run_id, request_json, dry_run, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, request.model_dump_json(), int(dry_run), RunStatus.QUEUED, now, now))

    def exists(self, run_id: str) -> bool:
        with sqlite3.connect(self._path) as conn:
            return conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)).fetchone() \
                is not None

    def get(self, run_id: str) -> tuple[ResearchRequest, bool, RunStatus]:
        with sqlite3.connect(self._path) as conn:
            row = conn.execute("SELECT request_json, dry_run, status FROM runs WHERE run_id = ?",
                               (run_id,)).fetchone()
        if row is None:
            raise LookupError(f"unknown run {run_id}")
        return ResearchRequest.model_validate_json(row[0]), bool(row[1]), RunStatus(row[2])

    def set_status(self, run_id: str, status: RunStatus, report_path: Path | None = None,
                   detail: str | None = None) -> None:
        """Update a run. `detail` (an error or pause reason) is replaced on every call, so a
        run that goes on to complete does not keep its earlier reason."""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                "UPDATE runs SET status = ?, report_path = COALESCE(?, report_path), "
                "detail = ?, updated_at = ? WHERE run_id = ?",
                (status, str(report_path) if report_path else None, detail,
                 datetime.now(UTC).isoformat(), run_id))

    def recent(self, limit: int = 20) -> list[tuple[str, str, str, str | None, str]]:
        with sqlite3.connect(self._path) as conn:
            return conn.execute(
                "SELECT run_id, request_json, status, report_path, created_at FROM runs "
                "ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()

    def row(self, run_id: str) -> dict[str, Any]:
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            found = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if found is None:
            raise LookupError(f"unknown run {run_id}")
        return _as_dict(found)

    def rows(self, limit: int = 30) -> list[dict[str, Any]]:
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            found = conn.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?",
                                 (limit,)).fetchall()
        return [_as_dict(r) for r in found]

    def dry_run_ids(self) -> set[str]:
        """Runs that used placeholder model output, so their reports can say so."""
        with sqlite3.connect(self._path) as conn:
            return {r[0] for r in conn.execute("SELECT run_id FROM runs WHERE dry_run = 1")}

    def interrupt_unfinished(self) -> int:
        """At server start: a run still marked queued or running lost its worker when the
        process stopped. Mark it failed; its checkpoint still allows a resume."""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.execute(
                "UPDATE runs SET status = ?, detail = ?, updated_at = ? WHERE status IN (?, ?)",
                (RunStatus.FAILED, "interrupted: the server stopped while this run was in "
                 "progress", datetime.now(UTC).isoformat(), RunStatus.QUEUED, RunStatus.RUNNING))
        return cursor.rowcount


def _as_dict(row: sqlite3.Row) -> dict[str, Any]:
    out = {key: row[key] for key in row.keys()}  # noqa: SIM118 - Row iterates values
    out["request"] = ResearchRequest.model_validate_json(out.pop("request_json"))
    out["dry_run"] = bool(out["dry_run"])
    return out
