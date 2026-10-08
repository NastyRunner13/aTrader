# Investor research: implementation and remaining work

The 8 October 2026 brief broadens research to business economics, financial
resilience, governance and expectations. Implementation through 9 October uses the
existing agents and call budgets. Prompt instructions do not supply financial
data the collectors do not yet have.

## Implemented foundation

- `scorecard/3` removes promoter-percentage rewards/penalties and single-quarter
  PEG. Ownership changes remain visible for investigation. Positive-earnings
  valuation needs a positive sector or market index P/E; missing comparisons leave
  it unscored. Loss-making trailing earnings retain the existing loss rule.
  Index-relative valuation has low confidence: earnings are not normalised.
- The steward requests eight result filings instead of five, subject to source
  availability and the knowledge cutoff. Revenue, profit and basic EPS growth
  compare two separate four-quarter totals. Missing, overlapping or incompatible
  periods suppress these metrics; non-positive prior totals produce no growth rate.
- Two-year scenarios use trailing-year EPS growth instead of one quarter's
  revenue/profit growth. Without eight comparable quarters, the range is absent.
  Reported EPS still requires corporate-action comparability review.
- Reverse earnings sensitivity calculates annual EPS growth needed for a 10%
  annual price return over two years, assuming an exit P/E equal to the positive
  sector index P/E, or market index as fallback. Inputs are cited and assumptions
  labelled. Dividends are excluded. It earns no scoring points and is not a reverse DCF.
- Broad `Updates` disclosures reach content review. The latest 25 eligible
  disclosures remain the prompt limit; truncation is counted and coverage becomes
  partial. Existing narrow routine categories are still omitted. PDFs are not read.
- Agent prompts cover all ten questions using existing cited claims and named
  gaps. Fundamentals and risk reviewers now receive disclosure summaries. Topic
  completeness is a prompt requirement, not a new enforced output schema.
- Coverage names missing business economics, financial resilience, sector FPI
  activity and detailed institutional ownership separately.
- Daily NSE provisional FPI/DII cash activity is collected with separate NSE-only
  and combined-exchange identities. Observations and revisions persist in SQLite;
  5/20/60-session sums require complete windows against the stored price/index
  calendar. Missing sessions produce unknown values, not shortened sums or zero.
  Figures, observation dates, source links and gaps appear in agents, the evidence
  drawer and exported reports. No automatic scoring weight is added.
- The manager returns up to three structured thesis assumptions, observable failure
  conditions and next events. Assumptions require known citations; next events
  require official announcement citations and, when dated, a date after the cutoff.
  Unknown events remain unknown and missing assumptions are reported as unresolved.
  These checks establish traceability; they do not verify semantic entailment.

Reverse sensitivity formula (dividends excluded):

```text
required EPS CAGR = sqrt(current trailing P/E / assumed exit P/E) * 1.10 - 1
```

Historical growth, management guidance, analyst consensus, our assumptions and
price-implied requirements are distinct. Two trailing years are not a business cycle.

## Responsibilities and next deliverables

| Investigation | Owner | Data/implementation still needed |
| --- | --- | --- |
| Business model | Fundamentals | Structured revenue drivers, customer concentration, segment economics and source passages |
| Competitive advantage | Fundamentals | Mechanism, retention/pricing/share evidence, threats and change over time |
| Value-creating reinvestment | Fundamentals | Multi-year ROIC, incremental returns, capital requirements and per-share results |
| Cash conversion | Fundamentals | Cash-flow/balance-sheet facts, collections, inventory, maintenance capex, capitalisation and recurring exceptionals |
| Financial resilience | Fundamentals + conservative review | Debt schedule, rates, restricted cash, guarantees, commitments and joint stress calculations; bank/NBFC taxonomy |
| Management and governance | Fundamentals + news | Dated capital-allocation decisions and persisted promise/outcome records with both source passages |
| Growth runway | Fundamentals + news | Penetration and capacity economics; order value, margins, funding, cancellation terms and working capital from documents |
| Earnings normality | Fundamentals | Longer history, through-cycle earnings/margins and sector operating indicators; distinguish recovery from structural growth |
| Valuation expectations | Fundamentals + manager | Normalised valuation ranges and reverse growth/margin/reinvestment scenarios beyond the EPS sensitivity |
| Thesis failure and estimation error | Manager + debate | Structured cited assumptions, falsifiers and next events implemented; semantic evaluation, margin for estimation error and portfolio exposures still needed |

Banks and NBFCs need credit quality, credit costs, capital and funding analysis.
Industrial cash-conversion and ordinary debt rules cannot substitute for that
framework. Missing data stays a gap rather than a favourable assessment.

## Institutional datasets: separate collectors and identities

| Dataset | Required identity and measures | Status |
| --- | --- | --- |
| Daily FPI/DII cash activity | Session, participant, exchange scope, basis, gross buys/sales/net in base INR, observation time and source; 5/20/60-session sums | Latest-session provisional collector and stored-history trends implemented; historical backfill and custodian-confirmed data pending |
| Sector FPI context | Fortnight, sector taxonomy, source, net investment separate from assets under custody | Collector pending |
| Company institutional ownership | ISIN, holder/category, reporting/publication dates, shares, percentage, corporate-action adjustment and source; new positions/exits | Exchange XBRL and mutual-fund disclosure collectors pending |
| Volume and delivery | Security/session, turnover, volume and delivery participation | Collected; cannot identify institutional buyers/sellers |

Keep NSE-only activity separate from combined NSE/BSE/MSEI data, provisional exchange
cash activity separate from custodian-confirmed reporting, and stock-exchange
investment separate from primary/other investment. Do not blindly merge or sum
these series. Holdings value can rise with prices; ownership percentages can fall
through dilution. Derivatives can hedge cash positions. Aggregate purchases cannot
establish buying in a particular security.

The collector uses the [official NSE report](https://www.nseindia.com/reports/fii-dii)
and is tested against captured response fixtures. Its endpoints expose the latest
session only. Run `atrader ingest-institutional` after market reporting to accumulate
observations; normal ingestion and current-date research also collect them. No
scheduler is installed. Publication timestamps are absent, so retrieval time is
the conservative knowledge boundary; captures are never backdated to session dates.
Historical-cutoff research uses stored observations only. Price/index ingestion
supplies the market calendar; institutional-only ingestion does not create it.

Keep incomplete windows explicit. Evaluate whether flows improve one-month
analysis, with business economics and valuation still central at two years.

## Validation and compatibility

Regression tests cover scoring invariance to quarterly growth and promoter
percentages, period continuity/comparability, the reverse-sensitivity equation and
citations, announcement cutoff/truncation, explicit coverage gaps, institutional
units/scopes/revisions/cutoffs, incomplete session windows and thesis filtering. Graph tests
exercise both AI modes with a fake gateway and unchanged model-call counts.

API and stored-report schemas add optional institutional activity and thesis tests;
older reports load with empty defaults. Archived reports retain their original
scorecard version. New reports can have fewer signals or no two-year range because
missing valuation/history no longer gets a quarterly-growth substitute. Live-source
access and real-model research quality still need separate evaluation.
