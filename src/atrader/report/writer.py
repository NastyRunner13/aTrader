"""Write a report as three files: the signal card (Markdown, read this first), the full
analysis (Markdown) and everything as JSON (machine-readable)."""

from __future__ import annotations

from pathlib import Path

from atrader.contracts import ResearchReport
from atrader.report.card import render_card
from atrader.report.markdown import render_details


def write_report(report: ResearchReport, directory: Path) -> tuple[Path, Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    stem = report.report_id.replace(":", "_").replace("/", "_")
    card_path = directory / f"{stem}.md"
    details_path = directory / f"{stem}-details.md"
    json_path = directory / f"{stem}.json"
    card_path.write_text(render_card(report, details_path.name), encoding="utf-8")
    details_path.write_text(render_details(report, card_path.name), encoding="utf-8")
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return card_path, details_path, json_path
