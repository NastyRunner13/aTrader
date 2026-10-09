"""Portfolio concentration only from supplied positions and dated exposures."""

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PortfolioPosition(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    isin: str
    market_value: float = Field(gt=0)
    sector: str | None = None
    currency: str = "INR"
    shared_exposures: list[str] = Field(default_factory=list)


def portfolio_exposures(positions: list[PortfolioPosition]) -> dict[str, Any]:
    if not positions or len({p.currency for p in positions}) != 1:
        raise ValueError("supply nonempty positions in one common valuation currency")
    total = sum(p.market_value for p in positions)
    names: dict[str, float] = defaultdict(float)
    sectors: dict[str, float] = defaultdict(float)
    shared: dict[str, float] = defaultdict(float)
    for p in positions:
        weight = p.market_value / total
        names[p.isin] += weight
        sectors[p.sector or "Unknown"] += weight
        for exposure in set(p.shared_exposures):
            shared[exposure] += weight
    return {
        "total_value": total,
        "currency": positions[0].currency,
        "weights": dict(names),
        "sector_weights": dict(sectors),
        "shared_exposure_weights": dict(shared),
        "largest_position": max(names.values()),
        "concentration_hhi": sum(w * w for w in names.values()),
        "limitations": [
            "shared exposures overlap and must not be summed",
            "unknown sectors stay unknown; no correlations inferred",
            "cash and liabilities count only when explicitly supplied",
        ],
    }
