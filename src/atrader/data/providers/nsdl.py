"""NSDL sector data: equity flows and custody values remain separate quantities."""

import calendar
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from atrader.contracts import InstitutionalActivity, SectorFlow, SourceRef
from atrader.data.http import FetchError, PoliteClient
from atrader.timeutil import IST

ROOT = "https://www.fpi.nsdl.co.in/web/StaticReports/Fortnightly_Sector_wise_FII_Investment_Data"
DAILY = "https://www.fpi.nsdl.co.in/web/Reports/Latest.aspx"


def parse_confirmed(content: bytes, source: SourceRef) -> list[InstitutionalActivity]:
    """Expand HTML rowspans; retain equity routes and reporting dates, never subtotals."""
    soup = BeautifulSoup(content, "html.parser")
    tables = [t for t in soup.find_all("table") if "Investment Route" in t.get_text()]
    if not tables or source.retrieved_at is None:
        raise ValueError("confirmed report table or observation timestamp missing")
    table = min(tables, key=lambda t: len(t.get_text()))
    active: dict[int, tuple[str, int]] = {}
    started, out = False, []
    routes = {"Stock Exchange": "stock_exchange", "Primary market & others": "primary_other"}
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        texts = [c.get_text(" ", strip=True) for c in cells]
        if "Investment Route" in texts:
            if (
                len(texts) != 8
                or "Reporting" not in texts[0]
                or not all("Crore" in texts[i] for i in (3, 4, 5))
            ):
                raise ValueError("confirmed report column layout changed")
            started = True
            continue
        if not started:
            continue
        expanded = {i: value for i, (value, _) in active.items()}
        active = {i: (v, n - 1) for i, (v, n) in active.items() if n > 1}
        column = 0
        for cell, value in zip(cells, texts, strict=True):
            while column in expanded:
                column += 1
            span = int(str(cell.get("colspan", 1)))
            for i in range(column, column + span):
                expanded[i] = value
                remaining = int(str(cell.get("rowspan", 1))) - 1
                if remaining:
                    active[i] = value, remaining
            column += span
        if expanded.get(1) != "Equity" or expanded.get(2) not in routes:
            continue
        day = datetime.strptime(expanded[0], "%d-%b-%Y").date()
        if day > source.retrieved_at.astimezone(IST).date():
            raise ValueError("confirmed report is future dated")
        amounts = [
            float(
                Decimal(expanded[i].replace(",", "").replace("(", "-").replace(")", ""))
                * 10_000_000
            )
            for i in (3, 4, 5)
        ]
        route = routes[expanded[2]]
        out.append(
            InstitutionalActivity(
                session=day,
                participant="FPI",
                scope="combined",
                basis="confirmed",
                date_basis="reporting",
                route=route,
                purchases_inr=amounts[0],
                sales_inr=amounts[1],
                net_inr=amounts[2],
                available_at=source.retrieved_at,
                source=source.model_copy(update={"provider": f"nsdl.confirmed.{route}"}),
            )
        )
    if not out or len({(r.session, r.route) for r in out}) != len(out):
        raise ValueError("missing or duplicate confirmed equity routes")
    return out


def collect_confirmed(client: PoliteClient) -> tuple[list[InstitutionalActivity], list[str]]:
    try:
        fetched = client.get(DAILY, max_age_s=3600)
        return parse_confirmed(
            fetched.content,
            SourceRef(
                provider="nsdl.confirmed",
                url=DAILY,
                retrieved_at=fetched.retrieved_at,
                content_hash=fetched.sha256,
            ),
        ), []
    except (FetchError, ValueError, KeyError, InvalidOperation) as exc:
        return [], [str(exc)]


def parse_sector_report(content: bytes, source: SourceRef) -> list[SectorFlow]:  # noqa: PLR0912
    soup = BeautifulSoup(content, "html.parser")
    table = next(
        (
            t
            for t in soup.find_all("table")
            if "AUC as on" in t.get_text() and "Net Investment" in t.get_text()
        ),
        None,
    )
    if table is None or source.retrieved_at is None:
        raise ValueError("sector report table or observation time missing")
    trs = table.find_all("tr")
    headings = trs[0].find_all(["td", "th"])
    offset, groups = 0, []
    for cell in headings:
        text = cell.get_text(" ", strip=True)
        span = int(str(cell.get("colspan", 1)))
        if text:
            groups.append((offset, span, text))
        offset += span
    # Verify each group starts with INR crore, equity; do not rely on fixed column counts.
    currency = [
        (c.get_text(" ", strip=True), int(str(c.get("colspan", 1))))
        for c in trs[1].find_all(["td", "th"])
        if c.get_text(strip=True)
    ]
    if not currency or not all("IN INR Cr" in currency[i][0] for i in range(0, len(currency), 2)):
        raise ValueError("sector currency layout changed")
    if not all("Equity" in tr.get_text() for tr in trs[2:4]):
        raise ValueError("sector equity column layout changed")
    leaves = [c.get_text(" ", strip=True) for c in trs[3].find_all(["td", "th"])]
    if any(column >= len(leaves) or leaves[column] != "Equity" for column, _, _ in groups):
        raise ValueError("sector equity column position changed")
    rows = []
    for tr in trs[4:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) != offset or not cells[0].isdigit():
            continue
        sector = cells[1]
        auc: dict[date, float] = {}
        nets = []
        for column, _, heading in groups:
            try:
                value = Decimal(cells[column].replace(",", "").replace("(", "-").replace(")", ""))
            except InvalidOperation as exc:
                raise ValueError("invalid sector amount") from exc
            if not value.is_finite():
                raise ValueError("nonfinite sector amount")
            amount = float(value * 10_000_000)
            if heading.startswith("AUC as on "):
                day = datetime.strptime(heading.removeprefix("AUC as on "), "%B %d, %Y").date()
                auc[day] = amount
            else:
                match = re.fullmatch(r"Net Investment (\w+) (\d+)-(\d+), (\d{4})", heading)
                if not match:
                    raise ValueError("unrecognised fortnight heading")
                month, first, last, year = match.groups()
                start = datetime.strptime(f"{month} {first} {year}", "%B %d %Y").date()
                end = datetime.strptime(f"{month} {last} {year}", "%B %d %Y").date()
                if end > source.retrieved_at.astimezone(IST).date() or start > end:
                    raise ValueError("invalid sector reporting period")
                nets.append((start, end, amount))
        for start, end, amount in nets:
            rows.append(
                SectorFlow(
                    sector=sector,
                    period_start=start,
                    period_end=end,
                    net_equity_inr=amount,
                    equity_auc_inr=auc.get(end),
                    available_at=source.retrieved_at,
                    source=source,
                )
            )
    if not rows:
        raise ValueError("no sector equity rows parsed")
    return rows


def collect_sectors(client: PoliteClient, cutoff: date) -> tuple[list[SectorFlow], list[str]]:
    # Reports have no trustworthy publication timestamp. Retrieval, not period-end,
    # bounds historical availability. The builder only calls this for today's pack.
    end = cutoff.replace(day=15) if cutoff.day > 15 else cutoff.replace(day=1) - timedelta(days=1)
    errors: list[str] = []
    for _ in range(2):
        url = f"{ROOT}/FIIInvestSector_{end:%b%d%Y}.html"
        try:
            fetched = client.get(url, max_age_s=86400)
            return parse_sector_report(
                fetched.content,
                SourceRef(
                    provider="nsdl.sectors",
                    url=url,
                    retrieved_at=fetched.retrieved_at,
                    content_hash=fetched.sha256,
                ),
            ), errors
        except (FetchError, ValueError) as exc:
            errors.append(str(exc))
        previous = end.replace(day=1) - timedelta(days=1)
        end = (
            previous.replace(day=calendar.monthrange(previous.year, previous.month)[1])
            if end.day == 15
            else end.replace(day=15)
        )
    return [], errors
