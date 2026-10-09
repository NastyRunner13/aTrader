"""Deterministic claim verification (F21).

This establishes traceability, not truth: every cited ID must exist in the run's
frozen pack, facts and calculations must cite something, and numeric statements
must rest on a reported fact or a computed metric. Semantic faithfulness still needs
human audit samples (docs/04).
"""

from __future__ import annotations

import re

from atrader.contracts import (
    Claim,
    ClaimDraft,
    ClaimKind,
    ClaimStatus,
    DerivedMetric,
    EvidencePack,
    FinancialFact,
    InstitutionalActivity,
    OwnershipPosition,
    Reason,
    SectorFlow,
    ShareholdingSnapshot,
)

_NUMERIC = re.compile(
    r"\d+(?:\.\d+)?\s?%|₹\s?\d|\b(?:rs\.?|inr)\s?\d|\d+\.\d+"
    r"|\d+(?:\.\d+)?\s?(?:x|crore|cr|lakh|bps|bp|basis points)\b",
    re.IGNORECASE,
)


# Evidence that carries reported or computed numbers and can back a numeric statement.
NUMERIC_EVIDENCE = (FinancialFact, DerivedMetric, ShareholdingSnapshot, InstitutionalActivity,
                    OwnershipPosition, SectorFlow)


def normalise_ids(ids: list[str]) -> list[str]:
    return [i.strip().strip("[]()").upper() for i in ids if i and i.strip()]


def is_numeric_statement(text: str) -> bool:
    return bool(_NUMERIC.search(text))


def verify_claims(drafts: list[ClaimDraft], pack: EvidencePack, agent: str,
                  id_prefix: str) -> list[Claim]:
    items = pack.items_by_id()
    claims: list[Claim] = []
    for index, draft in enumerate(drafts, start=1):
        cited = normalise_ids(draft.evidence_ids)
        known = [i for i in cited if i in items]
        unknown = [i for i in cited if i not in items]
        issues: list[str] = []
        status = ClaimStatus.SUPPORTED
        if unknown:
            issues.append("unknown evidence IDs: " + ", ".join(unknown))
            status = ClaimStatus.NEEDS_REVIEW

        if draft.kind in (ClaimKind.FACT, ClaimKind.CALCULATION):
            if not known:
                status = ClaimStatus.UNSUPPORTED
                issues.append(f"{draft.kind.value} without valid evidence")
            elif is_numeric_statement(draft.statement) and not any(
                    isinstance(items[i], NUMERIC_EVIDENCE) for i in known):
                status = ClaimStatus.UNSUPPORTED
                issues.append("numeric statement not backed by a reported figure or metric")
        elif cited and not known:
            status = ClaimStatus.UNSUPPORTED
            issues.append("every cited ID is unknown")
        elif not cited:
            status = ClaimStatus.NEEDS_REVIEW
            issues.append("no evidence cited")

        claims.append(Claim(
            statement=draft.statement, kind=draft.kind, evidence_ids=known,
            assumptions=draft.assumptions, claim_id=f"C-{id_prefix}-{index}", agent=agent,
            status=status, issues=issues,
        ))
    return claims


def verify_reasons(reasons: list[Reason], pack: EvidencePack) -> tuple[list[Reason], list[str]]:
    """Keep reasons whose citations resolve; drop numeric reasons without facts/metrics."""
    items = pack.items_by_id()
    kept: list[Reason] = []
    dropped: list[str] = []
    for reason in reasons:
        known = [i for i in normalise_ids(reason.evidence_ids) if i in items]
        numeric = is_numeric_statement(reason.statement)
        backed = any(isinstance(items[i], NUMERIC_EVIDENCE) for i in known)
        if numeric and not backed:
            dropped.append(f"{reason.statement} (numeric claim without a fact or metric)")
        elif reason.evidence_ids and not known:
            dropped.append(f"{reason.statement} (cited IDs do not exist)")
        else:
            kept.append(Reason(statement=reason.statement, evidence_ids=known))
    return kept, dropped


def known_ids(ids: list[str], pack: EvidencePack) -> list[str]:
    valid = pack.evidence_ids()
    return [i for i in normalise_ids(ids) if i in valid]
