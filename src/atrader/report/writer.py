"""Write a report as Markdown (for reading) and JSON (complete, machine-readable)."""

from __future__ import annotations

from pathlib import Path

from atrader.contracts import ResearchReport
from atrader.report.markdown import render_markdown


def write_report(report: ResearchReport, directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    stem = report.report_id.replace(":", "_").replace("/", "_")
    markdown_path = directory / f"{stem}.md"
    json_path = directory / f"{stem}.json"
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return markdown_path, json_path
