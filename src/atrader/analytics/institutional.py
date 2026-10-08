"""Market cash-flow trends: complete trading-session windows, separated by scope/basis."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from atrader.contracts import DerivedMetric, InstitutionalActivity


def institutional_metrics(rows: Sequence[InstitutionalActivity], sessions: Sequence[date]
                          ) -> list[DerivedMetric]:
    calendar = sorted(set(sessions))
    if not calendar:
        return []
    groups: dict[tuple[str, str, str, str], dict[date, InstitutionalActivity]] = defaultdict(dict)
    for row in rows:
        group = (row.participant, row.scope, row.basis, row.source.provider)
        if row.session in groups[group]:
            raise ValueError("flow metrics need one observation per session and series")
        groups[group][row.session] = row
    out = []
    for (participant, scope, basis, provider), by_session in groups.items():
        for window in (5, 20, 60):
            days = calendar[-window:]
            selected = [by_session[d] for d in days if d in by_session]
            complete = len(days) == window and len(selected) == window
            out.append(DerivedMetric(
                name=f"{participant.lower()}_{scope}_{basis}_{provider}_net_{window}s",
                label=f"{participant} net cash activity, {window} sessions ({scope}, {basis})",
                value=sum(r.net_inr for r in selected) if complete else None,
                unit="INR", as_of=calendar[-1], category="institutional",
                formula=f"sum(net cash activity, last {window} recorded market sessions)",
                inputs=tuple(r.evidence_id for r in selected),
                detail=f"{len(selected)}/{window} sessions available; {provider}; "
                       "market-wide context, not company buying or selling",
                quality_flags=("market sessions come from stored NSE price/index data",
                               "no automatic scoring weight")
                + (() if complete else ("incomplete window; no partial sum reported",)),
            ))
    return out
