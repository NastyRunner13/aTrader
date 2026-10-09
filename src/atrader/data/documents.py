"""Bounded PDF extraction. Pages remain attributable; image-only pages stay gaps."""

import io
import json
import re
from collections.abc import Sequence
from datetime import date
from urllib.parse import urlencode
from zipfile import BadZipFile, ZipFile

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from atrader.contracts import Announcement, DocumentPassage, SourceRef
from atrader.data.http import FetchError, PoliteClient
from atrader.timeutil import end_of_day_ist, parse_nse_datetime

TOPICS = {
    "business_model": r"segment|customer|volume|pricing|revenue mix|currency|acquisition",
    "competitive_advantage": r"market share|retention|switching|patent|distribution|pricing power",
    "reinvestment": r"capital expenditure|capex|return on|capital employed|commission|capacity",
    "cash_conversion": r"receivable|inventory|inventories|cash flow|capitalis|exceptional",
    "financial_resilience": (r"maturit|refinanc|floating|guarantee|restricted cash|"
                             r"commitment|liquidity"),
    "governance": r"related.party|remuneration|buyback|dividend|dilution|guidance|outlook|target",
    "growth_runway": r"order|backlog|capacity|cancellation|execution|working capital|funding",
    "earnings_normality": r"cycle|commodity|credit cost|windfall|one.off|normalis",
    "valuation": r"guidance|margin|growth|reinvestment",
    "banking": (r"non.performing|npa|stage.?3|capital adequacy|cet.?1|credit cost|"
                r"liquidity coverage"),
}


def extract_pdf(
    content: bytes, title: str, source: SourceRef, max_pages: int = 60
) -> tuple[list[DocumentPassage], list[str]]:
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
        if reader.is_encrypted:
            return [], [f"{title}: encrypted PDF"]
        passages, gaps = [], []
        if len(reader.pages) > max_pages:
            gaps.append(f"{title}: {len(reader.pages) - max_pages} pages beyond extraction limit")
        for index, page in enumerate(reader.pages[:max_pages], 1):
            text = " ".join((page.extract_text() or "").split())
            if len(text) < 40:
                gaps.append(f"{title}, page {index}: image-only or no extractable text")
                continue
            # Retain literal chunks: quoted support can be checked deterministically later.
            for start in range(0, len(text), 5500):
                chunk = text[start : start + 5500]
                topics = tuple(
                    topic
                    for topic, pattern in TOPICS.items()
                    if re.search(pattern, chunk, re.IGNORECASE)
                )
                if topics:
                    passages.append(
                        DocumentPassage(
                            title=title, page=index, text=chunk, topics=topics, source=source
                        )
                    )
        return passages, gaps
    except (PdfReadError, ValueError, KeyError, OSError) as exc:
        return [], [f"{title}: PDF extraction failed ({type(exc).__name__})"]


def collect_documents(
    client: PoliteClient, announcements: Sequence[Announcement], limit: int = 12
) -> tuple[list[DocumentPassage], list[str]]:
    eligible = [
        a
        for a in announcements
        if a.attachment_url and a.attachment_url.lower().split("?")[0].endswith(".pdf")
    ]
    # Give investor presentations and annual reports room beside frequent order notices.
    eligible.sort(
        key=lambda a: (
            bool(
                re.search(
                    r"presentation|annual report|financial result", a.category + a.summary, re.I
                )
            ),
            a.published_at,
        ),
        reverse=True,
    )
    passages: list[DocumentPassage] = []
    gaps = (
        [f"{len(eligible) - limit} documents beyond collection limit"]
        if len(eligible) > limit
        else []
    )
    seen = set()
    for item in eligible[:limit]:
        assert item.attachment_url is not None
        if item.attachment_url in seen:
            continue
        seen.add(item.attachment_url)
        try:
            fetched = client.get(item.attachment_url)
            extracted, errors = extract_pdf(
                fetched.content,
                item.category,
                SourceRef(
                    provider="nse.document",
                    url=item.attachment_url,
                    published_at=item.published_at,
                    retrieved_at=fetched.retrieved_at,
                    content_hash=fetched.sha256,
                ),
            )
            passages.extend(extracted)
            gaps.extend(errors)
        except FetchError as exc:
            gaps.append(str(exc))
    if len(passages) > 80:
        gaps.append(f"{len(passages) - 80} passages beyond report limit")
    return passages[:80], gaps


def collect_annual_reports(
    client: PoliteClient, symbol: str, cutoff: date, archived: Sequence[DocumentPassage]
) -> tuple[list[DocumentPassage], list[str]]:
    url = "https://www.nseindia.com/api/annual-reports?" + urlencode(
        {"index": "equities", "symbol": symbol}
    )
    passages: list[DocumentPassage] = []
    errors: list[str] = []
    try:
        index = client.get(url, max_age_s=86400)
        items = json.loads(index.content)["data"]
        candidates = []
        for item in items:
            published = parse_nse_datetime(item.get("disseminationDateTime")) or parse_nse_datetime(
                item.get("broadcast_dttm")
            )
            if (published or index.retrieved_at) <= end_of_day_ist(cutoff):
                candidates.append((int(item["toYr"]), item["fileName"], published))
        for year, file_url, published in sorted(
            candidates, key=lambda c: (c[0], c[2] or index.retrieved_at), reverse=True
        )[:3]:
            prior = [d for d in archived if d.source.url == file_url]
            if prior:
                passages.extend(prior)
                continue
            try:
                fetched = client.get(file_url)
                source = SourceRef(
                    provider="nse.annual_report",
                    url=file_url,
                    published_at=published,
                    retrieved_at=fetched.retrieved_at,
                    content_hash=fetched.sha256,
                )
                files = [(f"Annual report {year}", fetched.content)]
                if fetched.content.startswith(b"PK"):
                    with ZipFile(io.BytesIO(fetched.content)) as archive:
                        pdfs = [
                            f for f in archive.infolist() if f.filename.lower().endswith(".pdf")
                        ]
                        if sum(f.file_size for f in pdfs) > 75_000_000 or len(pdfs) > 5:
                            raise ValueError("annual report archive exceeds extraction limits")
                        files = [
                            (f"Annual report {year}: {f.filename}", archive.read(f)) for f in pdfs
                        ]
                for title, content in files:
                    rows, gaps = extract_pdf(content, title, source, max_pages=800)
                    passages.extend(rows)
                    errors.extend(gaps)
            except (FetchError, ValueError, BadZipFile, OSError) as exc:
                errors.append(str(exc))
    except (FetchError, ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    return passages, errors


def select_passages(passages: Sequence[DocumentPassage], limit: int = 80) -> list[DocumentPassage]:
    """Keep recent and older support for every topic, across distinct reports and pages."""
    unique = {(d.source.url, d.source.content_hash, d.page, d.text): d for d in passages}
    ordered = list(unique.values())
    ordered.sort(key=lambda d: str(d.source.published_at or d.source.retrieved_at), reverse=True)
    selected: list[DocumentPassage] = []
    for topic in TOPICS:
        matches = [d for d in ordered if topic in d.topics]
        sources: dict[str, list[DocumentPassage]] = {}
        for doc in matches:
            sources.setdefault(str(doc.source.url), []).append(doc)
        for group in [*sources.values()][:2] + [*sources.values()][-1:]:
            for doc in (group[0], group[len(group) // 2], group[-1]):
                if doc not in selected:
                    selected.append(doc)
    selected.extend(d for d in ordered if d not in selected)
    return selected[:limit]
