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
    """The three outlook horizons every report scores."""

    ONE_MONTH = "1m"
    SIX_MONTHS = "6m"
    TWO_YEARS = "2y"

    @property
    def label(self) -> str:
        return {Horizon.ONE_MONTH: "1 month", Horizon.SIX_MONTHS: "6 months",
                Horizon.TWO_YEARS: "2 years"}[self]

    @property
    def sessions(self) -> int:
        """Approximate trading sessions in the horizon."""
        return {Horizon.ONE_MONTH: 21, Horizon.SIX_MONTHS: 126, Horizon.TWO_YEARS: 504}[self]


class Pillar(StrEnum):
    """One scored area of the research. Each belongs to the analyst that reviews it."""

    TECHNICAL = "technical"
    GROWTH_QUALITY = "growth_quality"
    VALUATION = "valuation"
    NEWS = "news"

    @property
    def label(self) -> str:
        return {Pillar.TECHNICAL: "Technical", Pillar.GROWTH_QUALITY: "Growth & quality",
                Pillar.VALUATION: "Valuation", Pillar.NEWS: "News & catalysts"}[self]

    @property
    def agent(self) -> str:
        return {Pillar.TECHNICAL: "market_analyst", Pillar.GROWTH_QUALITY: "fundamentals_analyst",
                Pillar.VALUATION: "fundamentals_analyst", Pillar.NEWS: "news_analyst"}[self]


class Signal(StrEnum):
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"
    INSUFFICIENT_DATA = "insufficient_data"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Mode(StrEnum):
    DATA_ONLY = "data_only"  # no model calls; a code-only scorecard
    BASELINE = "baseline"  # one synthesis call, for evaluation against debate workflows
    COMPACT = "compact"  # 6 planned calls
    FULL = "full"  # 11 planned calls


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
