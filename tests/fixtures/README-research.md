# Research-depth fixture provenance

These small public-source excerpts test parsing, not investment quality. XML
fixtures retain selected facts and the contexts they reference; they are not
complete filings. Private identifiers such as PAN fields are excluded.

| Fixture | Public source | Selection |
| --- | --- | --- |
| lt_statement_excerpt.xml | https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1664542_07052026062845_WEB.xml | Industrial annual, cash flow, closing balances and segment axes |
| hdfcbank_statement_excerpt.xml | https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_BANKING_1654391_18042026073048_WEB.xml | Bank annual and closing balances |
| shriramfin_statement_excerpt.xml | https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_NBFC_INDAS_1658606_24042026060140_WEB.xml | NBFC annual and closing balances |
| ownership_excerpt.xml | https://nsearchives.nseindia.com/corporate/xbrl/SHP_1694210_16072026041111_WEB.xml | L&T mutual-fund category and named institutional holders, including cross-context names |
| pledge_excerpt.xml | https://nsearchives.nseindia.com/corporate/xbrl/SHP_1694672_16072026082530_WEB.xml | Promoter pledge/encumbrance fields |
| nsdl_daily_layout.html | https://pilot.fpi.nsdl.co.in/Reports/Latest.aspx | Captured equity rows and merged headers, displayed reporting date 30 October 2025 |
| nsdl_sector_layout.html | Synthetic reduced layout based on NSDL fortnightly tables | Separate INR/USD and AUC/net groups; deliberately distinctive values |

Captured during implementation on 8–9 October 2026. NSDL pilot material is only a
layout fixture: it is not treated as current production data. The production
collector does not fall back to the pilot host. Sector layout was compared with
https://pilot.fpi.nsdl.co.in/StaticReports/Fortnightly_Sector_wise_FII_Investment_Data/FIIInvestSector_Sep302026.html.

Synthetic tests supplement excerpts with explicitly constructed opening balances,
corporate actions and dated document quotes. Missing opening balances in an actual
fixture do not become invented ROIC or ROA observations.
