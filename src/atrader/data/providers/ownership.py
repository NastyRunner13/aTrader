"""Detailed exchange ownership. Category totals and named holders are never summed."""

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree

from atrader.contracts import OwnershipPosition, SourceRef
from atrader.data.http import FetchError, PoliteClient
from atrader.data.providers.nse_shareholding import shareholding_url
from atrader.timeutil import end_of_day_ist, parse_nse_datetime


def parse_ownership(  # noqa: PLR0912 — reject incompatible units and incomplete contexts in place
    content: bytes, isin: str, source: SourceRef
) -> list[OwnershipPosition]:
    root = ElementTree.fromstring(content)
    by_context: dict[str, dict[str, str]] = {}
    units: dict[tuple[str, str], str | None] = {}
    for element in root:
        if element.get("contextRef") and element.text:
            by_context.setdefault(element.get("contextRef", ""), {})[element.tag.split("}")[-1]] = (
                element.text.strip()
            )
            units[(element.get("contextRef", ""), element.tag.split("}")[-1])] = element.get(
                "unitRef"
            )
    declared = {v["ISIN"] for v in by_context.values() if v.get("ISIN")}
    if declared and isin not in declared:
        raise ValueError("ownership filing belongs to a different ISIN")
    observed = source.published_at or source.retrieved_at
    if observed is None or observed.tzinfo is None:
        raise ValueError("ownership requires a dated publication or observation")
    rows = []
    names = {}
    for ctx in root.findall("{http://www.xbrl.org/2003/instance}context"):
        identity = tuple(
            sorted(
                (e.get("dimension", ""), " ".join(e.itertext()))
                for e in ctx.iter()
                if e.tag.endswith(("}explicitMember", "}typedMember"))
            )
        )
        name = by_context.get(ctx.get("id", ""), {}).get("NameOfTheShareholder")
        if name:
            names[identity] = name
    for ctx in root.findall("{http://www.xbrl.org/2003/instance}context"):
        values = by_context.get(ctx.get("id", ""), {})
        members = [e for e in ctx.iter() if e.tag.endswith(("}explicitMember", "}typedMember"))]
        category = " ".join(
            (e.get("dimension", "") + " " + " ".join(e.itertext())) for e in members
        )
        if not re.search(
            r"Mutual|Portfolio|Institution|Insurance|Pension|Promoter|Bank", category
        ) and not any("Encumbered" in tag for tag in values):
            continue
        period = ctx.findtext(".//{http://www.xbrl.org/2003/instance}instant") or ctx.findtext(
            ".//{http://www.xbrl.org/2003/instance}endDate"
        )
        if not period:
            continue
        identity = tuple(sorted((e.get("dimension", ""), " ".join(e.itertext())) for e in members))
        holder = names.get(identity)
        member = next((e.text or "" for e in members if e.tag.endswith("}explicitMember")), "")
        label = holder if holder else member.split(":")[-1].removesuffix("Member")
        if not label:
            continue

        def amount(tag: str, fields: dict[str, str] = values) -> float | None:
            try:
                n = Decimal(fields.get(tag, ""))
                return float(n) if n.is_finite() else None
            except InvalidOperation:
                return None

        shares = amount("NumberOfShares")
        fraction = amount("ShareholdingAsAPercentageOfTotalNumberOfShares")
        if shares is None and fraction is None:
            continue
        for tag, expected in (("NumberOfShares", "shares"),
                              ("ShareholdingAsAPercentageOfTotalNumberOfShares", "pure")):
            if tag in values and units.get((ctx.get("id", ""), tag)) != expected:
                raise ValueError(f"unexpected ownership unit for {tag}")
        if fraction is not None and not 0 <= fraction <= 1:
            raise ValueError("unexpected ownership fractional unit")
        rows.append(
            OwnershipPosition(
                isin=isin,
                period_end=date.fromisoformat(period),
                holder=label,
                category=re.sub(
                    r"(?<=[a-z])(?=[A-Z])",
                    " ",
                    (members[0].get("dimension", "") if holder else label)
                    .split(":")[-1]
                    .removeprefix("DetailsOfSharesHeldBy")
                    .removesuffix("Axis"),
                ),
                level="holder" if holder else "category",
                shares=shares,
                ownership_pct=fraction * 100 if fraction is not None else None,
                pledged_shares=amount("NumberOfSharesEncumberedUnderPledged"),
                encumbered_shares=amount("NumberOfSharesEncumbered")
                if "NumberOfSharesEncumbered" in values
                else amount("NumberOfSharesPledgedOrOtherwiseEncumbered"),
                available_at=observed,
                source=source,
            )
        )
    unique = {(r.period_end, r.level, r.category, r.holder): r for r in rows}
    return list(unique.values())


def collect_ownership(
    client: PoliteClient, symbol: str, isin: str, cutoff: date
) -> tuple[list[OwnershipPosition], list[str]]:
    rows: list[OwnershipPosition] = []
    errors: list[str] = []
    try:
        index = client.get(shareholding_url(symbol), max_age_s=12 * 3600)
        payload = json.loads(index.content)
        if not isinstance(payload, list):
            raise ValueError("unexpected shareholding index")
        candidates = []
        for item in payload:
            published = parse_nse_datetime(item.get("broadcastDate"))
            available = published or index.retrieved_at
            if available <= end_of_day_ist(cutoff) and str(item.get("xbrl", "")).endswith(".xml"):
                candidates.append((available, published, item["xbrl"]))
        for _, published, url in sorted(candidates, key=lambda c: c[0], reverse=True)[:8]:
            try:
                fetched = client.get(url)
                rows.extend(
                    parse_ownership(
                        fetched.content,
                        isin,
                        SourceRef(
                            provider="nse.ownership",
                            url=url,
                            published_at=published,
                            retrieved_at=fetched.retrieved_at,
                            content_hash=fetched.sha256,
                        ),
                    )
                )
            except (FetchError, ValueError, ElementTree.ParseError) as exc:
                errors.append(str(exc))
    except (FetchError, ValueError) as exc:
        errors.append(str(exc))
    # Later-filed revisions supersede older values only within this cutoff.
    latest: dict[tuple[object, ...], OwnershipPosition] = {}
    for row in sorted(rows, key=lambda r: r.available_at):
        if row.period_end <= cutoff:
            latest[(row.period_end, row.level, row.category, row.holder)] = row
    return list(latest.values()), errors
