# Indian data strategy

Reviewed 4 October 2026. **Publicly viewable, free of charge, programmatically accessible, and reusable are different properties.** These sources are candidates, not tested working integrations. No authenticated API or end-to-end Indian data retrieval was exercised during this research.

## Provider plan

| Dataset | Preferred route | Cost/access classification | Fallback and initial decision |
| --- | --- | --- | --- |
| Listing master, ISIN, symbols | Exchange instrument lists; verified broker instrument master | Public/conditional; check current terms | Seed a reviewed pilot master; preserve effective-dated aliases |
| Daily OHLCV | User-permitted CSV; personal-use yfinance prototype | No required fee for import; unofficial remote source | Verify coverage/adjustments; replace adapter without changing agents |
| Historical/intraday broker candles | Upstox V3 candidate | Account/entitlement dependent; price not established for this user | Opt-in later after access proof; do not block CSV pilot |
| Financial statements | NSE/BSE filings and issuer investor-relations reports | Public documents; automated reuse terms need verification | User-supplied documents and reviewed metric import |
| Structured broker fundamentals | Upstox fundamentals candidate | Documented endpoints; access/pricing to verify | Optional cross-check; filings remain authoritative references |
| Announcements/corporate actions | Exchange corporate filings plus issuer disclosures | Public/conditional | Imported source documents with original publication time |
| Ownership, pledges, governance | Filed shareholding patterns and company reports | Public/conditional | Manual structured entry with document/page references |
| Company backlog/order awards | Issuer presentations, annual reports, exchange notices | Public documents; incomplete standardization | No universal free API assumed; structured extraction + review |
| News | Publisher-authorized RSS, official announcements, GDELT discovery | Feed/source-specific; discovery is not article licensing | Metadata + original links; accept permitted article uploads |
| Reddit | Approved official access with permitted processing | Conditional; not guaranteed free or approved | Show unavailable; keep community branch optional |
| Other social sources | Explicit APIs/feeds/permissions | Conditional | No dependency on X, Telegram, WhatsApp, or private groups |
| RBI macro | RBI releases and DBIE tables | Public releases; verify download/reuse routes | Versioned local table imports |
| GDP, inflation, policy | MoSPI publications, PIB and relevant ministries | Public publication routes; terms vary | Manual release ingestion with dates and revisions |
| International events | GDELT discovery + original official/publisher sources | Coverage and source rights vary | Bounded approved source list; no unlimited free search promise |
| Market depth | Entitled broker quote/stream feed | Conditional; depth level and retention rights vary | P2 only; unavailable is explicit |
| FII/DII, delivery, bulk/block deals | Exchange/regulator/broker publications where available | Dataset-specific | P1 candidates; market-level flows never treated as company-specific holdings |

The [yfinance project](https://github.com/ranaroussi/yfinance) describes itself as unofficial and points to personal-use restrictions for Yahoo data. The default adapter is therefore a replaceable personal-research experiment, not a licensed data feed for a public product.

[Upstox historical V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/) and its [income-statement documentation](https://upstox.com/developer/api-documentation/get-income-statement/) establish candidate endpoints, not this user's entitlement. A pricing page could not be verified in this review, so no zero-cost guarantee is made. By contrast, [Kite's current pricing](https://zerodha.com/products/api/) puts live streaming and historical candles in its paid Connect tier; it is not a baseline free-data dependency.

[SEBI's corporate-filings directory](https://www.sebi.gov.in/curation/corporate_filings.html) links NSE/BSE disclosure categories. The [NSE announcements page](https://www.nseindia.com/companies-listing/corporate-filings-announcements) is a source-discovery route, not proof of an unrestricted stable API. [NSE data policy](https://www.nseindia.com/static/market-data/nse-data-policy) governs use and redistribution. Do not treat a working endpoint as permission to redistribute its data.

## Retrieval policy

Maintain a provider registry with dataset, allowed uses, authentication, last terms review, rate limit, retention, permitted display/export, and health status. Approved domains and explicit adapters control retrieval. Respect denials and rate limits; do not bypass access controls or disguise blocked traffic.

P0 retrieval is bounded: up to 20 unique company news items and 10 macro items per research window, selected by entity relevance and materiality; these are product limits, not source guarantees. Deduplicate syndication and exchange/issuer copies into one event while retaining each source reference.

[GDELT DOC](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/amp/) is useful for news discovery. Its historical API announcement is not a current coverage/SLA guarantee; verify actual response windows in the data pilot. A discovered URL does not grant access to the article text.

[Reddit's access guidance](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Reddit-Developer-Interfaces) ties eligibility to the use case and review. Its [Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki) also warns about outdated legacy guidance. Verify permitted aggregation, storage, deletion, and transmission to a model provider before enabling this adapter. User-uploaded content still needs suitable rights; import is not a bypass.

## Company-data coverage checklist

The company agent should report a coverage checklist, rather than claim to have found “all company data.” Build basic financial/disclosure coverage in P0 and sector depth/history in P1.

| Area | Fields and questions to support |
| --- | --- |
| Income statement | Revenue, operating profit, margins, finance costs, tax, exceptional items, profit attributable to owners, diluted EPS; comparable growth periods |
| Balance sheet | Cash, borrowings, lease obligations, receivables, inventory, working capital, equity, minority interests, contingent liabilities |
| Cash flow | Operating cash flow, capital expenditure, financing flows, dividends, acquisitions, cash conversion; explicit free-cash-flow definition |
| Capital allocation | Capex commitments, capacity additions, debt maturities, dilution, buybacks, dividends, acquisition terms, related-party transactions |
| Business quality | Segment growth/margins, capacity utilization, customer/supplier concentration, pricing power, geographic revenue, input costs |
| Governance | Promoter holdings and pledges, ownership changes, auditor qualifications/resignations, related parties, material litigation, exchange actions; allegations labeled as allegations |
| Management | Guidance, changes to guidance, stated targets, earnings-call statements where permitted, comparison of earlier promises with later reported outcomes |
| Banks/NBFCs | Asset quality, provisions, capital adequacy, net interest margin, loan/deposit mix and growth; distinguish the business models |
| Other sector extensions | Insurer disclosures, IT order/deal metrics, industrial backlog, commodity volumes/costs, real-estate bookings/collections; only where definitions are comparable |
| Valuation | Share count/date, market capitalization, enterprise-value bridge, P/E or P/B where meaningful, peer selection, assumptions and sensitivities |

Historical ownership events, ratings/rationale documents, insider disclosures, and bulk/block deals are later source candidates. Their availability and permitted use must be demonstrated before enabling them. An LLM may summarize a financial footnote, but must not fill an absent line item with an industry average unless explicitly modeling a labeled scenario.

## Company order backlog versus exchange order book

**Company backlog** is the unexecuted contracted business a company reports. Store period end, reported total, currency, unit, scope, gross/JV share, segment, source page, and publication time. For awards, capture announcement date, customer if disclosed, value/range, status, execution duration, and whether the award is already included in reported backlog.

Statuses include signed contract, letter of award, letter of intent, preferred/lowest bidder, framework agreement, cancellation, and unclear. Do not count a tentative award as secured revenue. Separate maximum contract value from committed value.

The conceptual reconciliation is:

`closing backlog = opening backlog + recognized order inflow - executed work - cancellations + FX/scope adjustments`

Only calculate a reconciled total when comparable components are available. Otherwise show disclosed totals and an unexplained bridge. Never add news about a new award to a later reported total without checking whether it is already included. Backlog/revenue is a context ratio, not a guaranteed number of revenue years.

**Exchange order book** means bid/ask prices and quantities at a particular time. It belongs in a separate `MarketDepthSnapshot` record. Daily OHLCV cannot reconstruct depth, hidden liquidity, cancellations, or queue position. Live broker depth and historical order-level records are different datasets; the latter may require paid exchange products. [NSE historical data products](https://www.nse.in/static/market-data/eod-historical-data-subscription).

## Normalization and time

- Separate issuer from listing. An NSE ticker and a BSE code may describe the same security; use verified mappings rather than string heuristics alone.
- Store numeric values in base INR with original units retained. Display crore/lakh when useful. Preserve original currency and FX date for foreign amounts.
- Capture actual period start/end and duration; do not assume every company shares one year end. Distinguish quarter, year-to-date, annual, and trailing periods.
- Keep standalone and consolidated statements separate. Record audited/unaudited and original/restated versions.
- Store raw and adjusted prices separately, with adjustment factors and the information date of each corporate action. Never mix adjustment bases inside one calculation.
- Use exchange sessions and Asia/Kolkata display time. Weekends, holidays, special sessions, suspensions, and absent bars are not interchangeable.
- Record `event_at`, `published_at`, `first_seen_at`, `retrieved_at`, `period_end`, and `revision_of` where applicable.
- Historical eligibility requires publication before the cutoff and a defensible historical version. A document downloaded today does not prove what was available then.

## Freshness and coverage

Price-based research requires the latest completed eligible session for a current report; if unavailable, suppress current technical conclusions or mark them stale. Financial data shows its actual period and filing age, not just a cache refresh time. News displays the searched interval and retrieval outcome. Backlog shows the reporting period, even if the document was fetched today.

Use `available`, `partial`, `stale`, `missing`, `access_blocked`, `not_applicable`, and `not_requested`. These states must survive through the final report. Missing social data is never a neutral sentiment score.

RBI's [Handbook release](https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=58701) documents DBIE's economic-data role. Macro inputs should retain release dates and vintages so later revisions do not silently enter historical analyses.

## Data pilot results (4 October 2026)

Tested from the development machine with plain HTTPS requests, no login, at about one request per second. Personal-research use only; redistribution rights are unchanged by these results.

| Dataset | Route that worked | Notes | Adapter |
| --- | --- | --- | --- |
| Instrument master | `nsearchives.nseindia.com/content/equities/EQUITY_L.csv` | Symbol, name, series, listing date, ISIN, face value | `nse_instruments.py` |
| Daily prices | UDiFF bhavcopy `content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip` | All equities in one file, with ISIN, OHLC, previous close, volume, value, trades. Holidays return 404. Unadjusted; the published previous close reveals split/bonus factors. | `nse_bhavcopy.py` |
| Index closes | `content/indices/ind_close_all_DDMMYYYY.csv` | All NSE indices, with P/E, P/B and dividend yield | `nse_bhavcopy.py` |
| Results, up to Q3 FY25 | `www.nseindia.com/api/corporates-financial-results` | Filing time, period, standalone/consolidated, audited flag and XBRL link per filing | `nse_filings.py` |
| Results, from Q4 FY25 | `www.nseindia.com/api/integrated-filing-results?type=Integrated Filing- Financials` | Same fields; includes Q1 FY27 | `nse_filings.py` |
| Results XBRL | `nsearchives.nseindia.com/corporate/xbrl/*.xml` | `in-bse-fin` elements in base rupees; period from context dates; segment facts carry XBRL dimensions | `xbrl.py` |
| Announcements | `www.nseindia.com/api/corporate-announcements` | Category, summary, timestamp, attachment PDF. Order wins are tagged "Bagging/Receiving of orders/contracts", with the amount only in the PDF. | `nse_announcements.py` |
| Shareholding | `www.nseindia.com/api/corporate-share-holdings-master` | Promoter/public % per quarter with broadcast time; pledges not in this summary | `nse_shareholding.py` |
| News discovery | GDELT DOC 2.0 | Enforces one request per 5 seconds | `gdelt_news.py` |
| Delivery position (added 5 Oct) | `nsearchives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv` | Per stock and day: traded quantity, delivered quantity, delivery %. Header and cells are padded with spaces; `-` where nothing was reported. No ISIN, so rows join on symbol, series and session. | `nse_bhavcopy.py` |
| Industry classification (added 5 Oct) | `nsearchives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv` | About 755 stocks (Nifty 500 + Microcap 250) with NSE's industry. Today's classification, not point-in-time. The industry maps to a sector index whose P/E and closes come from the index file above. | `nse_sectors.py` |

Checked on 5 October 2026 and **not built yet**:

| Dataset | Route | Result |
| --- | --- | --- |
| FII/DII cash flows | `www.nseindia.com/api/fiidiiTradeReact` | Works; market-wide net buy/sell for the latest day only, so history must be collected daily. Never a per-stock figure. |
| Participant-wise open interest | `nsearchives.nseindia.com/content/nsccl/fao_participant_oi_DDMMYYYY.csv` | Works; FII/DII/client/pro long and short contracts in index and stock futures and options |
| F&O bhavcopy | `content/fo/BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip` | Works; open interest and its change per contract (price/OI build-up for F&O stocks) |
| Bulk and block deals | `content/equities/bulk.csv`, `block.csv` | Work for the latest day only; `api/historical/bulk-deals` returned 503 |
| Shareholding detail | the `xbrl` link in each shareholding-master row (`SHP_*.xml`) | Has FPI category I/II, mutual fund, insurance and pledge contexts: the per-stock, quarterly view of FII and DII holdings |
| Quote API | `www.nseindia.com/api/quote-equity` | 403; not usable without a browser session |

The `www.nseindia.com/api/*` endpoints are unofficial website APIs. They answered without session cookies on the test day, but can change or start refusing at any time; coverage then shows `access_blocked` rather than failing the run.
