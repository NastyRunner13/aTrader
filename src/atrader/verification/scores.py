"""Checks on what agents propose for the scorecard, applied before code uses it.

An adjustment or event rating survives only if it cites evidence that exists in the
run's pack. Analysts may adjust only their own areas, by at most the allowed points,
and news events must rest on a disclosure (A) or a headline (N).
"""

from __future__ import annotations

from atrader.analytics.scoring import MAX_ANALYST_ADJUSTMENT, clamp
from atrader.contracts import EventRating, EvidencePack, Pillar, ScoreAdjustment
from atrader.verification.claims import known_ids


def verify_adjustments(adjustments: list[ScoreAdjustment], pack: EvidencePack,
                       agent: str) -> list[ScoreAdjustment]:
    kept: dict[Pillar, ScoreAdjustment] = {}
    for adjustment in adjustments:
        ids = known_ids(adjustment.evidence_ids, pack)
        owned = adjustment.pillar.agent == agent and adjustment.pillar != Pillar.NEWS
        points = round(clamp(adjustment.points, -MAX_ANALYST_ADJUSTMENT,
                             MAX_ANALYST_ADJUSTMENT))
        if owned and ids and points and adjustment.pillar not in kept:
            kept[adjustment.pillar] = adjustment.model_copy(
                update={"evidence_ids": ids, "points": points})
    return list(kept.values())


def verify_events(events: list[EventRating], pack: EvidencePack) -> list[EventRating]:
    kept = []
    for event in events:
        ids = [i for i in known_ids(event.evidence_ids, pack) if i[0] in "AN"]
        if ids:
            kept.append(event.model_copy(
                update={"evidence_ids": ids, "impact": round(clamp(event.impact, -2, 2))}))
    return kept
