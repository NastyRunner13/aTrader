"""Instrument identity.

A listing is one traded line of a security on one exchange. The issuer/listing split
in docs/07 arrives with BSE mapping; until then the ISIN carries issuer identity.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

_ISIN = re.compile(r"^IN[A-Z0-9]{9}\d$")


class Listing(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    exchange: Literal["NSE", "BSE"] = "NSE"
    isin: str
    name: str
    series: str = "EQ"
    listed_on: date | None = None
    face_value: float | None = None
    source: str = "nse.equity_list"

    @field_validator("symbol")
    @classmethod
    def _upper_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("isin")
    @classmethod
    def _valid_isin(cls, value: str) -> str:
        value = value.strip().upper()
        if not _ISIN.match(value):
            raise ValueError(f"not an Indian ISIN: {value!r}")
        return value

    @property
    def listing_id(self) -> str:
        return f"{self.exchange}:{self.symbol}"
