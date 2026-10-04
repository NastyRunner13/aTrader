"""Offline tests for source parsers: XBRL, bhavcopy, filings index, NSE timestamps."""

from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from atrader.contracts import StatementBasis
from atrader.data.providers.gdelt_news import company_aliases, mentions_company
from atrader.data.providers.nse_bhavcopy import parse_bhavcopy, parse_index_close
from atrader.data.providers.nse_filings import (
    FilingRef,
    parse_integrated_index,
    parse_legacy_index,
    select_filings,
)
from atrader.data.providers.nse_shareholding import parse_shareholding
from atrader.data.xbrl import parse_results_xbrl
from atrader.formatting import format_value, indian_grouping
from atrader.timeutil import IST, parse_nse_datetime

FIXTURES = Path(__file__).parent / "fixtures"


def test_xbrl_reads_metadata_and_entity_level_facts():
    parsed = parse_results_xbrl((FIXTURES / "results_sample.xml").read_bytes())

    assert parsed.symbol == "TESTCO"
    assert parsed.basis == StatementBasis.CONSOLIDATED
    assert parsed.audited is False
    assert parsed.rounding == "Crores"
    assert parsed.reporting_period == (date(2026, 4, 1), date(2026, 6, 30))

    by_key = {(f.metric, f.duration): f for f in parsed.facts}
    revenue_q = by_key[("RevenueFromOperations", "quarter")]
    assert revenue_q.value == Decimal("12000000000.00")  # base rupees, not crore
    assert revenue_q.label == "Revenue from operations"
    assert ("RevenueFromOperations", "nine_months") in by_key
    assert by_key[("BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
                   "quarter")].unit == "INR/share"


def test_xbrl_skips_segment_dimensions_and_text_facts():
    parsed = parse_results_xbrl((FIXTURES / "results_sample.xml").read_bytes())
    metrics = {f.metric for f in parsed.facts}
    assert "SegmentRevenue" not in metrics  # dimensional context
    assert "CommentOnResults" not in metrics  # text, and never a prompt instruction
    assert "SegmentAssets" in metrics  # non-dimensional instant fact is kept
    assert next(f for f in parsed.facts if f.metric == "SegmentAssets").duration == "instant"


def _bhavcopy_zip(rows: list[str]) -> bytes:
    header = ("TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,"
              "FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,"
              "LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,"
              "TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("BhavCopy.csv", "\n".join([header, *rows]))
    return buffer.getvalue()


def test_bhavcopy_keeps_valid_equity_rows_only():
    good = ("2026-10-01,2026-10-01,CM,NSE,STK,1,INE000T01019,TESTCO,EQ,,,,,TEST CO,100,105,99,"
            "104,104,101,,104,,,5000,520000,120,F1,1,,,,,")
    bad_ohlc = ("2026-10-01,2026-10-01,CM,NSE,STK,2,INE000T01027,BADCO,EQ,,,,,BAD,100,90,99,"
                "104,104,101,,104,,,5000,520000,120,F1,1,,,,,")
    bond = ("2026-10-01,2026-10-01,CM,NSE,STK,3,INE000T01035,GSEC,GS,,,,,GSEC,100,100,100,"
            "100,100,100,,100,,,1,100,1,F1,1,,,,,")
    rows = list(parse_bhavcopy(_bhavcopy_zip([good, bad_ohlc, bond])))
    assert [r.symbol for r in rows] == ["TESTCO"]
    bar = rows[0].bar
    assert (bar.open, bar.high, bar.low, bar.close, bar.prev_close) == (100, 105, 99, 104, 101)
    assert bar.volume == 5000 and bar.trades == 120 and rows[0].isin == "INE000T01019"


def test_index_close_parses_pe_and_dashes():
    text = ("Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,"
            "Closing Index Value,Points Change,Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,"
            "Div Yield\nNifty 50,01-10-2026,22543.7,22610.6,22217.3,22421.95,-198.5,-.88,"
            "451303049,36534.26,19.19,2.75,1.23\nSome Index,01-10-2026,-,-,-,100,0,0,0,0,-,-,-\n")
    rows = parse_index_close(text)
    assert rows[0][0] == "Nifty 50" and rows[0][5] == 22421.95 and rows[0][6] == 19.19
    assert rows[1][2] is None and rows[1][6] is None


def test_nse_timestamps_are_ist():
    parsed = parse_nse_datetime("17-JUL-2026 19:50:03")
    assert parsed == datetime(2026, 7, 17, 19, 50, 3, tzinfo=IST)
    assert parse_nse_datetime("16-Jan-2025 20:20") is not None
    assert parse_nse_datetime("not a date") is None


def _ref(period: date, basis: StatementBasis, filed: datetime) -> FilingRef:
    return FilingRef("TESTCO", period, basis, False, filed, f"https://x/{period}-{filed}.xml",
                     "test")


def test_filing_selection_respects_cutoff_basis_and_revisions():
    q1, q2 = date(2026, 3, 31), date(2026, 6, 30)
    original = _ref(q2, StatementBasis.CONSOLIDATED, datetime(2026, 7, 20, tzinfo=IST))
    revised = _ref(q2, StatementBasis.CONSOLIDATED, datetime(2026, 8, 1, tzinfo=IST))
    standalone = _ref(q2, StatementBasis.STANDALONE, datetime(2026, 7, 20, tzinfo=IST))
    earlier = _ref(q1, StatementBasis.CONSOLIDATED, datetime(2026, 4, 25, tzinfo=IST))
    refs = [original, revised, standalone, earlier]

    chosen = select_filings(refs, datetime(2026, 9, 30, tzinfo=IST), quarters=5)
    assert chosen == [revised, earlier]  # consolidated only; the revision supersedes

    as_of_july = select_filings(refs, datetime(2026, 7, 25, tzinfo=IST), quarters=5)
    assert as_of_july == [original, earlier]  # the revision was not public yet


def test_filings_index_parsers_read_both_eras():
    legacy = [{"consolidated": "Non-Consolidated", "broadCastDate": "16-Jan-2025 20:20:21",
               "toDate": "31-Dec-2024", "audited": "Un-Audited",
               "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/A.xml"},
              {"consolidated": "Consolidated", "toDate": "31-Dec-2024", "xbrl": "-"}]
    integrated = {"data": [{"consolidated": "Consolidated", "broadcast_Date":
                            "17-Jul-2026 19:50:03", "qe_Date": "30-JUN-2026",
                            "audited": "Un-Audited", "type_Sub": "Original",
                            "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/B.xml"}]}
    old = parse_legacy_index(legacy, "TESTCO")
    new = parse_integrated_index(integrated, "TESTCO")
    assert len(old) == 1 and old[0].basis == StatementBasis.STANDALONE
    assert new[0].period_end == date(2026, 6, 30) and new[0].audited is False


def test_shareholding_parser_rejects_impossible_percentages():
    rows = [{"date": "30-JUN-2026", "pr_and_prgrp": "50.48", "public_val": "49.52",
             "broadcastDate": "16-JUL-2026 19:24:44"},
            {"date": "31-MAR-2026", "pr_and_prgrp": "150", "public_val": "x"}]
    snaps = parse_shareholding(rows, datetime.now(IST), "https://x")
    assert snaps[0].promoter_pct == 50.48
    assert snaps[1].promoter_pct is None and snaps[1].public_pct is None


def test_indian_number_formatting():
    assert indian_grouping(1234567.8) == "12,34,567.80"
    assert indian_grouping(-999) == "-999.00"
    assert format_value(Decimal("2438650000000"), "INR") == "₹2,43,865.00 cr"


def test_news_relevance_uses_company_aliases():
    aliases = company_aliases("Larsen & Toubro Limited", "LT")
    assert "l&t" in aliases and "larsen" in aliases and "lt" not in aliases
    assert mentions_company("L & T Extends Hyderabad Metro Stake Sale Deadline", aliases)
    assert mentions_company("Larsen & Toubro bags ultra-mega order", aliases)
    assert not mentions_company("Sensex tanks 1,124 pts to six-month low", aliases)
    assert not mentions_company("Saltwater project update", company_aliases("Salt Ltd", "SALT"))


def test_negative_amounts_put_the_sign_first():
    assert format_value(Decimal("-17910900000"), "INR") == "-₹1,791.09 cr"
    assert format_value(-12.5, "INR/share") == "-₹12.50/share"
    assert format_value(3693.25, "INR/share") == "₹3,693.25/share"
