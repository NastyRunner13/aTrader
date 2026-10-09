"""Disclosed position changes; absence never creates a synthetic zero holding."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from itertools import pairwise
from math import prod

from atrader.contracts import DerivedMetric, OwnershipPosition
from atrader.contracts.evidence import CorporateAction


def ownership_metrics(
    positions: Sequence[OwnershipPosition],
    actions: Sequence[CorporateAction],
    *,
    actions_since: date | None,
) -> list[DerivedMetric]:
    groups: dict[tuple[str, ...], list[OwnershipPosition]] = defaultdict(list)
    for row in positions:
        groups[(row.isin, row.level, row.category, row.holder, row.source.provider)].append(row)
    out = []
    for rows in groups.values():
        for old, new in pairwise(sorted(rows, key=lambda r: r.period_end)):
            if old.period_end == new.period_end:
                continue
            events = [a for a in actions if old.period_end < a.ex_date <= new.period_end]
            known = (
                actions_since is not None
                and old.period_end >= actions_since
                and all(a.share_factor is not None for a in events)
            )
            factor = prod(a.share_factor for a in events if a.share_factor is not None)
            prefix = f"ownership_{old.evidence_id}_{new.evidence_id}"
            inputs = (old.evidence_id, new.evidence_id, *(a.evidence_id for a in events))
            flags = (
                "disclosed positions, not daily purchases/sales; ISINs are not auto-merged",
                "category and holder levels overlap; no automatic scoring weight",
            )
            if old.ownership_pct is not None and new.ownership_pct is not None:
                out.append(
                    DerivedMetric(
                        name=f"{prefix}_pp",
                        label=f"{new.holder}: ownership change",
                        value=round(new.ownership_pct - old.ownership_pct, 4),
                        unit="pp",
                        as_of=new.period_end,
                        category="institutional",
                        inputs=inputs[:2],
                        formula="current disclosed ownership % - prior disclosed ownership %",
                        detail=f"{old.period_end} to {new.period_end}; "
                        "dilution or reclassification "
                        "can change percentages without a sale",
                        quality_flags=flags,
                    )
                )
            if old.shares is None or new.shares is None:
                continue
            change = new.shares - old.shares * factor if known else None
            status = (
                "confirmed new position"
                if known and old.shares == 0 < new.shares
                else "confirmed exit"
                if known and new.shares == 0 < old.shares
                else "comparable disclosed quantity change"
                if known
                else "quantity comparison withheld: corporate-action coverage incomplete"
            )
            out.append(
                DerivedMetric(
                    name=f"{prefix}_shares",
                    label=f"{new.holder}: adjusted share change",
                    value=change,
                    unit="shares",
                    as_of=new.period_end,
                    category="institutional",
                    inputs=inputs,
                    formula="current shares - prior shares * split/bonus factor",
                    detail=f"{old.period_end} to {new.period_end}; {status}; factor {factor:g}",
                    quality_flags=flags,
                )
            )
    return out
