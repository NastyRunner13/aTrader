"""NSE industry classification, and the sector index each industry is compared with.

The Nifty Total Market constituent list (about 750 stocks: the Nifty 500 and the Nifty
Microcap 250) carries NSE's industry for every member. It is today's classification,
not a point-in-time record; industries rarely change. Stocks outside the list get no
sector comparison. The sector index's P/E and closes come from the daily index file
already in the store.
"""

from __future__ import annotations

import csv
import io

from atrader.data.http import PoliteClient

TOTAL_MARKET_URL = ("https://nsearchives.nseindia.com/content/indices/"
                    "ind_niftytotalmarket_list.csv")
_REFRESH_S = 7 * 24 * 3600

# NSE industry -> the NSE sector index it is compared with. Industries without a
# close-fitting index (Services, Textiles, Utilities, Diversified, Forest Materials)
# are left out on purpose rather than matched to a broad index.
SECTOR_INDEX = {
    "Automobile and Auto Components": "Nifty Auto",
    "Capital Goods": "Nifty Capital Goods",
    "Chemicals": "Nifty Chemicals",
    "Construction": "Nifty Construction",
    "Construction Materials": "Nifty Cement",
    "Consumer Durables": "Nifty Consumer Durables",
    "Consumer Services": "Nifty Consumer Services",
    "Fast Moving Consumer Goods": "Nifty FMCG",
    "Financial Services": "Nifty Financial Services",
    "Healthcare": "Nifty Healthcare Index",
    "Information Technology": "Nifty IT",
    "Media Entertainment & Publication": "Nifty Media",
    "Metals & Mining": "Nifty Metal",
    "Oil Gas & Consumable Fuels": "Nifty Oil & Gas",
    "Power": "Nifty Power",
    "Realty": "Nifty Realty",
    "Telecommunication": "Nifty Telecommunications",
}


def parse_industries(text: str) -> dict[str, str]:
    """ISIN -> NSE industry from an index constituent list."""
    industries: dict[str, str] = {}
    for raw in csv.DictReader(io.StringIO(text)):
        row = {(k or "").strip(): (v or "").strip() for k, v in raw.items()}
        isin, industry = row.get("ISIN Code"), row.get("Industry")
        if isin and industry:
            industries[isin.upper()] = industry
    return industries


def fetch_industries(client: PoliteClient) -> dict[str, str]:
    fetched = client.get(TOTAL_MARKET_URL, max_age_s=_REFRESH_S)
    return parse_industries(fetched.content.decode("utf-8", errors="replace"))
