"""The report archive as the web app sees it: summaries for lists, one report for the
workspace, evidence lookups and downloads. Reports are the JSON files `write_report`
saves; this module only reads them."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from atrader.contracts import ResearchReport

EVIDENCE_GROUPS = ("facts", "metrics", "announcements", "shareholding", "news",
                   "institutional_activity", "documents", "ownership", "sector_flows",
                   "corporate_actions")
EXPORTS = {"card": (".md", "text/markdown"), "details": ("-details.md", "text/markdown"),
           "json": (".json", "application/json")}


class ReportLibrary:
    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._lock = threading.Lock()
        # file stem -> (mtime_ns, size, summary). A report file never changes once written,
        # so the summary is read from disk once.
        self._summaries: dict[str, tuple[int, int, dict[str, Any]]] = {}

    def summaries(self, symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        found = [s for s in self._scan() if symbol is None or s["symbol"] == symbol.upper()]
        found.sort(key=lambda s: s["generated_at"], reverse=True)
        return found[:limit]

    def latest(self, symbol: str) -> dict[str, Any] | None:
        found = self.summaries(symbol, limit=1)
        return found[0] if found else None

    def get(self, report_id: str) -> ResearchReport:
        return ResearchReport.model_validate_json(
            self._path(report_id, ".json").read_text(encoding="utf-8"))

    def evidence(self, report_id: str, evidence_id: str) -> dict[str, Any]:
        pack = json.loads(self._path(report_id, ".json").read_text(encoding="utf-8")).get("pack")
        for group in EVIDENCE_GROUPS:
            for item in (pack or {}).get(group, []):
                if item.get("evidence_id") == evidence_id:
                    return {"kind": group, "item": item}
        raise LookupError(f"{evidence_id} is not in report {report_id}")

    def export_path(self, report_id: str, kind: str) -> tuple[Path, str]:
        suffix, media_type = EXPORTS[kind]
        return self._path(report_id, suffix), media_type

    # --- internals -----------------------------------------------------------------------

    def _path(self, report_id: str, suffix: str) -> Path:
        """Resolve an ID by looking it up among the files that exist, never by building a
        path from it, so a crafted ID cannot reach outside the reports directory."""
        for stem in self._stems():
            if stem == report_id:
                path = self._directory / f"{stem}{suffix}"
                if path.is_file():
                    return path
        raise LookupError(f"unknown report {report_id}")

    def _stems(self) -> list[str]:
        if not self._directory.is_dir():
            return []
        return [p.stem for p in self._directory.glob("*.json")]

    def _scan(self) -> list[dict[str, Any]]:
        out = []
        with self._lock:
            for stem in self._stems():
                path = self._directory / f"{stem}.json"
                try:
                    stat = path.stat()
                    cached = self._summaries.get(stem)
                    if cached is None or cached[:2] != (stat.st_mtime_ns, stat.st_size):
                        summary = _summarise(stem, json.loads(path.read_text(encoding="utf-8")))
                        cached = (stat.st_mtime_ns, stat.st_size, summary)
                        self._summaries[stem] = cached
                    out.append(cached[2])
                except (OSError, ValueError, KeyError):
                    continue  # a half-written or foreign file is not a report
        return out


def _summarise(stem: str, report: dict[str, Any]) -> dict[str, Any]:
    pack = report.get("pack") or {}
    listing = pack.get("listing") or {}
    card = report.get("scorecard") or {}
    request = report["request"]
    levels = card.get("levels") or {}
    return {
        "report_id": stem,
        "run_id": report["run_id"],
        "symbol": listing.get("symbol") or request["symbol"].upper(),
        "name": listing.get("name"),
        "cutoff": pack.get("cutoff") or request.get("cutoff"),
        "mode": request["mode"],
        "status": report["status"],
        "generated_at": report["generated_at"],
        "model_adjusted": card.get("model_adjusted", False),
        "close": levels.get("close"),
        "horizons": [{"horizon": h["horizon"], "score": h["score"], "signal": h["signal"],
                      "confidence": h["confidence"]} for h in card.get("horizons", [])],
    }
