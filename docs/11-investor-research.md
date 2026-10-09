# Investor research

The 8 October 2026 brief is implemented through the existing analysts, evidence
archive, deterministic calculations and report workspace. Compact/full retain their
6/11 planned model calls. These features add research evidence, not scoring weights.

## Investigations and their boundaries

| Investigation | Implemented | Limit of the evidence |
| --- | --- | --- |
| Business model | Ten-topic structured findings, segment revenue/results, customers and revenue-driver passages | Segment disclosures and extracted passages can be incomplete |
| Competitive advantage | Quoted evidence, mechanism, threats, direction and explicit gaps | Quotes establish traceability; moat judgements require human review |
| Reinvestment | Annual capital history, ROIC/incremental-return accounting proxies, comparable per-share history | Accounting capital is not economic capital; missing opening balances suppress returns |
| Cash conversion | Annual and contiguous three-year OCF/PAT, FCF after total capex, working-capital ratios, exceptional/capitalisation passages | Maintenance capex is not inferred from total capex |
| Resilience | Cash/debt, liquidity, interest coverage and joint demand/margin/rate stress; disclosed funding terms | Stress is conditional; restricted cash, maturities and guarantees remain gaps when undisclosed |
| Management | Capital allocation history and dated, quoted promise/outcome pairs in saved reports | Later publication is required for outcomes; delivery assessments remain model judgements |
| Growth runway | Capacity/customer/order passages and structured amount, status, execution, margin, funding and cancellation terms | Awards are not added to reported backlog or treated as secured revenue |
| Earnings normality | Up to 24 quarterly filings, annual margin history and a historical-median-margin EPS sensitivity | Available history is not automatically a complete business cycle |
| Valuation | Reverse EPS sensitivity, revenue/margin/reinvestment DCF roots and nine conditional valuation scenarios | No root or multiple roots remain explicit; assumed incremental returns are not forecasts |
| Thesis failure | Three cited assumptions/falsifiers, disclosed upcoming events and supplied-portfolio concentration | No holdings or correlations are inferred; unavailable events remain unknown |

Banks/NBFCs use loans, deposits, provisions, NPA and regulatory capital fields where
reported. Industrial cash/debt and DCF rules are excluded for these businesses.
The taxonomy does not yet cover every insurer or specialist financial business.

The earlier corrections remain: no single-quarter PEG or promoter-percentage
bonus, comparable trailing-year growth, and broad Updates disclosures included.
Index-relative valuation remains a low-confidence comparison. No new institutional
or research score weights are fitted or enabled automatically.

## Sources and point-in-time behaviour

The steward preserves XBRL statement basis, duration, units, dimensions and filing
date. Missing, incompatible or ambiguous inputs suppress calculations. Curated
segment axes are retained without adding overlapping segments to group totals.

Official annual reports (latest three eligible years), presentations and recent
announcement PDFs produce page-linked passages. Full extracted passages persist in
SQLite; a bounded, topic-balanced selection of up to 80 enters each pack and up to
20 shortened passages enters agent context. Older and newer disclosures support
management comparisons. Scanned pages need OCR and appear as gaps. Extraction can
lose table layout; collection is not a complete annual-report review.

Findings must cite known evidence. Document citations require exact quoted text
(after whitespace normalization). Invalid quotations are discarded and missing
topics become unknown. These checks do not establish semantic support for an
interpretation. Filing text is treated as untrusted evidence in prompts.

| Dataset | Identity and handling |
| --- | --- |
| NSE provisional daily cash | Separate NSE-only/combined scope, participant, gross purchases/sales/net, observation date; 5/20/60 trading-session windows require complete stored history |
| NSDL confirmed FPI | Reporting dates and stock-exchange/primary-other routes stay separate from provisional trading-date series |
| NSDL fortnightly sector | Source taxonomy, period, equity net investment and equity assets under custody kept distinct |
| Exchange ownership | ISIN, category/named holder, shares, company percentage, pledge/encumbrance, period and publication date; overlapping categories are never summed |
| Mutual funds | AMFI directory discovery plus official .xlsx quantity imports; fund NAV percentage is never company ownership |
| Corporate actions | Explicit split/bonus ratios adjust comparable holdings; unrecognized actions or incomplete history suppress quantity changes |

Absence is not an exit; an explicit zero is needed. Percentage changes can reflect
dilution. Aggregate cash activity and delivery volume do not identify buyers of a
particular stock. Holdings value/AUC changes can reflect market prices.

Captures and revisions persist. A source without a publication timestamp uses its
actual observation time, never a backdated reporting period. Historical research
uses only eligible archives. Imports require the operator to supply the real
publication/observation date; the software cannot independently authenticate it.

Live NSE filings, annual-report extraction and the AMFI directory were checked.
NSDL production endpoints refused access during this implementation. Their parsers
were checked against captured layout fixtures, and failure is recorded as missing
coverage. Pilot pages are never substituted automatically for production data.
Fund imports support explicit ISIN/quantity .xlsx tables; legacy .xls and arbitrary
AMC layouts need separate adapters. There is no automatic AMC download crawler or
installed collection scheduler.

## Commands

Run these from the project root after installing dependencies:

```powershell
uv run atrader ingest-institutional
uv run atrader fund-disclosures
uv run atrader import-document report.pdf ISIN "2026-05-14T18:30:32+05:30" SOURCE_URL
uv run atrader import-fund-portfolio holdings.xlsx "Fund name" 2026-09-30 "2026-10-08T12:00:00+05:30" SOURCE_URL
uv run atrader import-institutional capture.html nsdl-confirmed "2026-10-08T12:00:00+05:30" SOURCE_URL
uv run atrader reverse-valuation assumptions.json valuation.json
uv run atrader portfolio-risk positions.json exposure.json
uv run atrader benchmark frozen-pack.json reports/benchmark --ablations
uv run atrader evaluate reports/benchmark reports/evaluation.json
uv run atrader audit-summary reports/evaluation.json reports/audit-summary.json
```

`ingest-institutional` captures NSE provisional observations; current-date research
also attempts NSDL confirmed and sector collection. Institutional import datasets
are `nse`, `combined` (JSON), `nsdl-confirmed` and `nsdl-sectors` (HTML).
`frozen-pack.json` is the `pack` object from an exported report, not the full report.
Benchmark defaults to fake-model workflow checks; `--live` explicitly enables the
existing free-only gateway and quota. It runs data-only, one-call baseline, compact,
full, and optionally four compact evidence ablations, removing dependent metrics.
Ablation coverage explicitly identifies omitted sources.

Valuation input uses amounts in one common currency and rates as fractions:

```json
{"revenue":1000,"operating_margin":0.15,"tax_rate":0.25,"return_on_new_capital":0.2,"discount_rate":0.12,"terminal_growth":0.04,"years":5,"net_debt":100,"equity_value":1200}
```

Portfolio input is a list of supplied positions in one common valuation currency:

```json
[{"isin":"EXAMPLE1","market_value":1000,"currency":"INR","sector":"Industrials","shared_exposures":["public infrastructure"]}]
```

## Evaluation and remaining validation

Evaluation reports citation failures, future filing dates, calls, cost and latency,
and prepares ungraded source-linked claims for human review. Fill `human_support`
with a boolean and `human_notes` in the exported `human_audit` entries, then run
`audit-summary`. It reports the actual reviewed denominator and a Wilson interval;
a machine-valid citation is never counted as a human-supported claim.

Forward returns use the next stored session open and stored 21/126/504-session
horizons, when available. They exclude dividends and costs; sparse archives, sample
selection and model training-data hindsight limit interpretation. The harness does
not fit score weights or establish predictive accuracy.

Regression coverage includes real industrial/bank/NBFC filing excerpts, unit and
period traps, ownership/corporate-action comparisons, NSDL route/sector layouts,
quote and chronology validation, valuation recovery and graph call budgets.
API additions have empty defaults so existing reports still load. Evidence drawers
and Markdown exports expose the new sources, assumptions and investigations.

Still outstanding are successful production NSDL collection, broader AMC layout
coverage, the ten-company live pilot, a blinded human research-quality audit and
out-of-sample score validation. No claim that full mode beats compact or that these
signals predict returns has been established. Unrelated macro, screener, alert and
derivatives work remains tracked in the main roadmap.
