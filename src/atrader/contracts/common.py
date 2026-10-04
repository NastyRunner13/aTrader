"""Shared enumerations used across contracts, agents and the graph."""

from __future__ import annotations

from enum import StrEnum


class Coverage(StrEnum):
    """Availability of one source category for a run (docs/05, "Freshness and coverage")."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    STALE = "stale"
    MISSING = "missing"
    ACCESS_BLOCKED = "access_blocked"
    NOT_APPLICABLE = "not_applicable"
    NOT_REQUESTED = "not_requested"


class Horizon(StrEnum):
    SWING = "swing"  # roughly 5-20 trading sessions
    INVESTMENT = "investment"  # roughly 6-12 months

    @property
    def description(self) -> str:
        return {
            Horizon.SWING: "swing research, roughly 5-20 trading sessions",
            Horizon.INVESTMENT: "investment research, roughly 6-12 months",
        }[self]


class Mode(StrEnum):
    DATA_ONLY = "data_only"  # no model calls
    COMPACT = "compact"  # 6 planned calls
    FULL = "full"  # 16 planned calls


class Assessment(StrEnum):
    SUPPORTIVE = "supportive"
    MIXED = "mixed"
    ADVERSE = "adverse"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ClaimKind(StrEnum):
    FACT = "fact"
    CALCULATION = "calculation"
    INTERPRETATION = "interpretation"
    SCENARIO = "scenario"


class ClaimStatus(StrEnum):
    SUPPORTED = "supported"  # every cited ID resolves and the kind rules pass
    NEEDS_REVIEW = "needs_review"  # traceable, but semantic support is unverified
    UNSUPPORTED = "unsupported"  # removed from downstream context


class AgentStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    ABSTAINED = "abstained"
    SKIPPED = "skipped"  # deterministically not run, e.g. no evidence for the role
    FAILED = "failed"


class StatementBasis(StrEnum):
    STANDALONE = "standalone"
    CONSOLIDATED = "consolidated"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED_QUOTA = "paused_quota"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
