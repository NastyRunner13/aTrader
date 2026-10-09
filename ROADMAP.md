# aTrader roadmap

Last updated **9 October 2026**. Feature IDs (F01–F37) come from [docs/03](docs/03-feature-map.md) and delivery stages from [docs/09](docs/09-validation-and-roadmap.md). Update this file whenever a feature changes status.

**Where we are:** the first working version runs end to end on live NSE data **with a real model**, and ends in a **signal card**: 0–100 scores and signals for 1 month, 6 months and 2 years. Agents in the same step run in parallel. On 4 October 2026, a compact run on L&T made 6 calls, all valid on the first attempt, at zero cost, in 52 s of model time (about 88 s before the parallel graph). On 5 October the scorecard moved to `scorecard/2`: technical rules are grouped and capped, valuation compares the P/E with the NSE sector index, volume and delivery flows are scored, and the card shows price levels and the closes that would flip each signal. The scoring rules and weights are still starting priors; the next step is to validate them with the `--cutoff` backtest (M2) and run the other nine pilot companies.

Status key: ✅ done · 🟡 partial · ⬜ not started · ⏸ deferred by decision

**Investor-research foundation (8 October):** `scorecard/3` removes quarterly PEG and
unexplained promoter-percentage scoring. Eight-quarter comparisons, reverse EPS
sensitivity, content review of broad Updates, expanded agent responsibilities and
explicit institutional-data gaps are implemented. On 9 October, the latest-session
NSE FPI/DII cash collector, stored-history trends and cited thesis/failure/event
records were added across agents, API and reports. Financial-statement depth,
sector FPI and detailed ownership collectors remain pending; see
[the implementation checklist](docs/11-investor-research.md).

## Completed so far

**Research and planning**
- 10-document plan in `docs/`, reviewed against TradingAgents v0.6.0, which is pinned at commit `1394a3f`.
- Data pilot: every core NSE source was tested from this machine. Results are in [docs/05](docs/05-indian-data-strategy.md#data-pilot-results-4-october-2026).

**Data layer** (`src/atrader/data/`)
- NSE instrument master: symbol ↔ ISIN, with candidate suggestions for unknown symbols.
- NSE daily bhavcopy for all equities, plus all NSE index closes, stored in local SQLite. Holidays are remembered, and splits/bonuses are detected from the exchange's published previous close. A 404 for today or yesterday is no longer recorded as a holiday (it may be unpublished), and such early records are retried.
- NSE delivery position (`sec_bhavdata_full`) for the last ~100 sessions: delivered quantity and delivery % per stock and day.
- NSE industry for each Nifty Total Market stock, mapped to a sector index (17 industries; 5 without a close-fitting index are left unmapped).
- XBRL quarterly results from both NSE eras (legacy up to Q3 FY25, Integrated Filing after). Standalone and consolidated stay separate, and restatements are flagged.
- Corporate announcements, with order-win intimations identified. Shareholding (promoter/public %).
- GDELT headlines, filtered to stories that name the company.
- A point-in-time `--cutoff`: only data public by that date is used.
- The evidence pack: every item gets an ID (`F3`, `M12`, `A2`…), and every source gets a coverage status (available, partial, stale, missing, access_blocked, not_requested).

**Analytics** (`src/atrader/analytics/`)
- Indicators: SMA and EMA 20/50/200, RSI, MACD, ATR, volatility, period returns, volume ratio, liquidity, and relative strength vs Nifty 50 and the sector index.
- Flows (`flows.py`): average volume and delivered volume on up days vs down days, delivery share vs its 60-session norm, volume EMA 20/50 trend, average trade size.
- Levels (`levels.py`): support/resistance zones from confirmed swing points, the close that breaks the nearest support, anchored VWAPs (since results, 52-week high and low), the heaviest-traded price band.
- Signal flips (`flips.py`): the next close at which each horizon's signal changes, found by re-scoring a hypothetical session.
- Chart signals (versioned rules): moving-average trend, confirmed range breakout, unusual volume.
- Fundamentals: YoY/QoQ growth, margins, other income as a share of PBT, trailing EPS, P/E, approximate market cap, and the P/E of the sector index and the Nifty 50.
- Vetoes: stale prices, short history, old results, low liquidity and missing core data hold the signal at Neutral or withhold it.
- Scorecard (`scoring.py`, `ranges.py`): rule-based area scores with cited points, technical rules in five capped groups (trend, momentum, performance, breakout, flows), P/E against the sector index first, analyst adjustments (±15, verified), news from rated events, horizon weights, a manager adjustment (±5), signal bands, volatility ranges (1M/6M) and EPS × P/E scenarios (2Y).

**Agents and graph** (`src/atrader/agents/`, `src/atrader/graph/`)
- TradingAgents-style agents, one file each: market, fundamentals and news analysts; bull and bear researchers; aggressive, conservative and neutral debators; portfolio manager. The trader and research manager were removed on 4 October 2026: the signal card replaces the trader's plan, and the portfolio manager judges the debate.
- Parallel steps: the analysts; bull and bear in each debate round; the three risk debators. Up to 4 model calls at once.
- Modes: `data_only` (0 calls, code-only scorecard), `compact` (6 calls, cap 8) and `full` (11 calls, cap 14).
- Claim verification: invented citations, and numbers without a backing fact or metric, are marked unsupported and never reach later agents.

**Model gateway** (`src/atrader/llm/`)
- Free-only OpenRouter routing: `:free` routes only, pricing checked live, unknown pricing rejected, and any reported cost disables the route.
- Per-run call cap, a daily allowance with a reserve, one repair attempt for invalid output, and a ledger of every attempt.
- Checkpointed runs: a run paused by the daily quota resumes without repeating finished agents.

**Product and quality**
- CLI: `research`, `resume`, `ingest`, `search`, `models`, `usage`, `runs`.
- Reports in Markdown and JSON, with coverage, a results table, metrics, catalysts, debate, model calls, filings used and limitations.
- Offline regression tests use synthetic data and fake model calls; backend checks are documented in [CONTRIBUTING.md](CONTRIBUTING.md).

## Feature status

### Research capabilities

| ID | Feature | Priority | Status | What exists / what is missing |
|---|---|---|---|---|
| F01 | Company and listing search | P0 | 🟡 | NSE symbol/ISIN resolution and `atrader search`. Missing: BSE codes, symbol-change history |
| F02 | Watchlists and saved reports | P0 | ✅ | Reports saved with pack, cutoff and sources; run registry; a watchlist in the web app with each company's last close and latest signals |
| F03 | Daily price/volume history | P0 | ✅ | NSE bhavcopy, adjustment basis, holidays, last complete bar. Missing: user CSV import path |
| F04 | Financial statements and key ratios | P0 | 🟡 | Quarterly/annual P&L, balance sheet/cash flow, capital returns and bank/NBFC fields. Missing: comprehensive insurer taxonomy and broader live validation |
| F05 | Annual reports and presentations | P0 | ✅ | Bounded annual/presentation PDF extraction, archived page passages and exact-quote checks; scanned pages remain gaps |
| F06 | Announcements and catalysts | P0 | ✅ | NSE disclosures with timestamps, dedup, routine filings filtered. BSE cross-posts not merged |
| F07 | Business segments and exposures | P0 basic | ✅ | Curated XBRL segment dimensions, revenue/results/margins and cited business investigations |
| F08 | Company order backlog | P0 basic | 🟡 | Page-cited extraction of amounts, status, execution and backlog/contract terms. Missing: broader live EPC quality validation |
| F09 | Ownership and governance | P0 basic | 🟡 | Detailed categories/holders, pledges/encumbrances, split/bonus comparisons, fund workbook imports and quoted management outcomes. Missing: comprehensive AMC layouts and dedicated auditor/director event parsing |
| F10 | Sector-aware valuation | P0 simple | 🟡 | Trailing P/E scored against the NSE sector index P/E, then the Nifty 50; approximate market cap. Missing: peer sets, own-history P/E, bank metrics (P/B, ROA) |
| F11 | Company and sector news | P0 | 🟡 | GDELT company headlines with a relevance filter. Missing: sector news, publisher RSS, a reliable fallback when GDELT rate-limits |
| F12 | Macro and geopolitics | P0 basic | ⬜ | No RBI/MoSPI adapters, so no macro analyst yet |
| F13 | Reddit/community research | P1 cond. | ⏸ | Disabled until approved access and permitted processing are confirmed |
| F14 | Hindi/regional-language research | P1 | ⬜ | |
| F15 | Trend, momentum, volume, volatility | P0 | ✅ | Tested indicators, plus volume and delivery flows (up/down-day averages, delivery share, volume EMA) |
| F16 | Chart-pattern detection | P0 simple | ✅ | Three versioned rules. Held-out validation is part of F32 |
| F17 | Relative strength and sector context | P0 | ✅ | 3M vs Nifty 50 and vs the stock's NSE sector index. Stocks outside the Nifty Total Market list, or in an unmapped industry, get the Nifty 50 only |
| F18 | Bull/bear debate and judge | P0 | ✅ | Claim IDs, validated challenges, bounded parallel rounds; the portfolio manager judges |
| F19 | Hypothetical strategy planner | P0 | 🟡 | Replaced by the signal card: per-horizon score, signal, drivers, up/down triggers, price ranges, price levels and code-computed signal-flip closes. Scores not yet validated (F32) |
| F20 | Risk review + final manager | P0 | ✅ | Three parallel risk debators review the draft scorecard (full); portfolio manager; code vetoes on the scorecard |
| F21 | Evidence verification and coverage | P0 | ✅ | Citation and number checks; coverage carried into the report. Human semantic audit is part of F32 |
| F22 | Research memory and change detection | P0 archive | 🟡 | Report archive. Missing: compare-to-previous-report, reflection |

### Product and platform

| ID | Feature | Priority | Status | What exists / what is missing |
|---|---|---|---|---|
| F23 | Report workspace and live progress | P0 | ✅ | FastAPI + Next.js workspace: search, signal card with evidence drawer, price chart with levels, run history, live run progress over server-sent events |
| F24 | Free-only OpenRouter gateway | P0 | ✅ | Live-tested 2026-10-04: zero cost reported; the run cap held at 8 when a bad config produced empty answers; reasoning models get a bounded effort and output budget |
| F25 | Resume, cancel, retry, partial result | P0 | ✅ | Resume after a quota pause, failure or cancel; retry, repair, partial reports; cancel stops new work (a model call already in flight still finishes) |
| F26 | Evidence-grounded follow-up questions | P1 | ⬜ | |
| F27 | Markdown/JSON export; print view | P0 | ✅ | Signal card (Markdown and terminal), full-analysis Markdown and JSON for every run |
| F28 | Side-by-side comparison | P1 | ⬜ | |
| F29 | Deterministic stock screener | P1 | ⬜ | Groundwork done: bhavcopy already stores every NSE equity |
| F30 | Local watchlist event alerts | P1 | ⬜ | |
| F31 | Prospective paper journal | P1 | ⬜ | |
| F32 | Historical evaluation and ablations | P0 harness | 🟡 | Frozen-pack four-mode benchmark, evidence ablations, human-audit export and forward outcomes. Missing: blinded audit and held-out score validation |
| F33 | Hypothetical portfolio risk | P1 | ✅ | Supplied-position concentration, sector and shared exposures in one valuation currency; no inferred correlations |
| F34 | Market depth / order flow | P2 cond. | ⏸ | Needs an entitled broker feed |
| F35 | F&O, option chains, OI, IV | P2 cond. | ⏸ | The F&O bhavcopy (open interest) and participant-wise OI files were reachable on 5 Oct; not built |
| F36 | Public / multi-user deployment | P2 cond. | ⏸ | Needs data rights and a SEBI review |
| F37 | Broker execution | Out of scope | ⏸ | Not planned |

**Tally (37 features):** 16 done, 9 partial, 7 not started, 5 deferred. Of the 25 first-release (P0) features, 15 are done, 9 partial and 1 not started (F12).

### Delivery stages (docs/09)

| Stage | Status | Remaining to exit |
|---|---|---|
| 0 — Prove data access | 🟡 nearly done | Zero-cost inference ✅ (4 Oct). Remaining: pull data for all ten pilot companies, not just L&T |
| 1 — Data foundation | 🟡 mostly done | Broader filing coverage and CSV import. Balance sheet/cash flow and document extraction implemented. The web company page is deferred |
| 2 — Compact vertical slice | 🟡 first company passed | L&T passed end to end with a real model (6/8 calls). Remaining: the other nine pilot companies |
| 3 — Full research | 🟡 graph built | Evidence that full mode beats compact on a blinded evaluation set |
| 4 — Screening, monitoring, paper evaluation | ⬜ | |
| 5 — Conditional extensions | ⏸ | |

## Next milestones

Ordered by dependency. Each milestone ends with something you can run.

### M1 — Prove the AI layer (next)
- [x] Add `OPENROUTER_API_KEY` and choose a model (`stealth/space-bunny-alpha` for both tiers).
- [x] Live smoke test: compact run on L&T, cost 0, 6 calls, all valid first time (report `LT-2026-10-04-compact-4fa57527`).
- [x] Fixes from the live run: bounded reasoning effort and output budget for reasoning models, no repair call for truncated answers, shareholding figures accepted as numeric evidence, no duplicated citations.
- [ ] Choose a `:free` model as well, for repeatable evaluation: a stealth model is anonymous and may be withdrawn.
- [ ] Choose the ten pilot companies (financials, IT, industrials/EPC, consumer, commodities; at least one backlog reporter). Run `atrader ingest` for the full history.
- [ ] Run compact mode on all ten; record failures, invalid outputs, latency and unsupported claims; tune prompts.
- **Exit:** ten real reports with zero fabricated citations and zero paid calls.

### M2 — Evaluation harness (F32)
- [ ] Build a 30-case research-quality set (unit traps, restatements, missing data, injection text in documents).
- [ ] Human-audit sampled claims for support; report the denominator.
- [x] Baselines: data-only, single-model synthesis, compact and full; frozen-pack replay and evidence ablations. Real-model quality comparison remains pending.
- [ ] Validate the scorecard: run code-only scorecards at monthly `--cutoff` dates across the pilot set (no model calls), check whether higher scores preceded better 1M/6M returns, then tune the rule points, group caps and horizon weights. Test in particular whether 1-month weakness predicts further weakness or a rebound: published research generally finds short-term reversal.
- **Exit:** a measured answer to "is full mode worth 2× the calls?"

### M3 — Indian data depth (F04, F05, F07, F08, F09, F17)
- [x] Investor-research foundation: eight-quarter comparisons, reverse EPS sensitivity, removal of quarterly PEG/promoter-percentage scoring, Updates retained, and explicit missing institutional coverage (8 Oct). Remaining ten-question research and institutional requirements are tracked in [docs/11](docs/11-investor-research.md).
- [x] Balance sheet and cash flow from annual/half-yearly XBRL; bank/NBFC line items.
- [x] Structured order-award extraction from PDF passages: amount or range, status, customer, execution period, with exact quotes and page citations.
- [x] Structured reported-backlog extraction from presentation passages, distinct from awards; live quality review remains pending.
- [x] Promoter pledges and other encumbrances from shareholding filings.
- [x] Segment revenue and results from XBRL dimensions.
- [x] Sector index relative strength and sector P/E (5 Oct).
- [x] Institutional categories, named holders and pledges from quarterly shareholding XBRL.
- [x] Separate NSE provisional and NSDL confirmed adapters, archived captures and complete-window 5/20/60 trading-session trends. Production NSDL access is currently blocked.
- [x] Fortnightly sector net investment versus AUC; detailed exchange ownership and fund .xlsx imports with known corporate-action adjustments. Missing histories remain unknown; no new weights enabled.
- [ ] Participant-wise futures OI as market context, preserving its separation from cash activity.
- [ ] F&O open-interest build-up for F&O stocks; bulk and block deals collected daily.
- **Exit:** the order-backlog section works for at least one EPC company.

### M4 — Macro and news (F11, F12)
- [ ] RBI (policy rate, inflation) and MoSPI release adapters with release dates.
- [ ] Macro analyst: one new agent file plus one line in `graph/setup.py`.
- [ ] Sector news and a fallback when GDELT rate-limits.

### M5 — Research workspace (F02, F22, F23, F25, F28)
- [x] Watchlists and run cancel (5 Oct 2026, with the web app).
- [ ] Compare with the previous report.
- [x] FastAPI backend and Next.js workspace (`atrader serve`, `apps/web`).

### M6 — Screening and forward testing (F29–F31, F33)
- [ ] Deterministic screener over the stored bhavcopy universe.
- [ ] Local alerts on new material disclosures.
- [ ] Prospective paper journal: freeze each assessment before its outcome; review after 60+ sessions.
- [x] Supplied-portfolio concentration, sector and shared-exposure analysis (`portfolio-risk`).

### Later / conditional
F13 Reddit, F14 Hindi sources, F34–F35 depth and derivatives, and F36 public deployment, each once its access or legal gate is cleared. F37 broker execution is not planned.

## Open decisions

| Decision | Options | Notes |
|---|---|---|
| OpenRouter capacity | Stay at 50 requests/day, or buy $10 once for 1,000/day | 50/day allows about 5 compact runs; M2 evaluation needs hundreds of calls |
| Pilot companies | Your choice of ten | Should include at least one company that reports an order backlog |
| Second price/fundamentals source | Upstox (free, fundamentals by ISIN) or Angel One (free candles) | Optional cross-check; needs your broker account |
| Project location | Keep in OneDrive or move out | `.venv` inside OneDrive causes file locks and sync load |

## Known issues

- NSE `www.nseindia.com/api/*` endpoints are unofficial; if they start refusing, coverage shows `access_blocked`.
- GDELT rate-limits (HTTP 429); news is then missing for that run.
- A full `ingest` takes 30–40 minutes the first time (about 7 s per trading day at a polite rate). The first run after the delivery change also fetches ~100 delivery files (about 2–3 minutes).
- Sector comparisons use today's industry list, not a point-in-time one. A large company can dominate its own sector index (L&T in Nifty Construction), which makes the sector P/E partly a comparison with itself.
- The 2-year base scenario uses trailing-year EPS growth (eight comparable quarters), holds today's P/E and caps growth at 20%, so capped growers still get approximately close × 1.2² (+44%). This remains a sensitivity sketch, not through-cycle valuation; missing comparable history suppresses the range.
- In `--dry-run`, model-call records are kept in memory only, so a resumed dry run lists only the calls made after resuming.
- The issuer/listing split from docs/07 is collapsed onto the ISIN until BSE mapping arrives.
- Cancel (web app and API) stops new steps from starting; a model call already in flight still finishes. On Windows, closing a terminal does not always stop the Python process, which can keep running until its call cap (this happened once on 4 October: 8 wasted calls, cap held). Stop a run from the app instead.
- `stealth/space-bunny-alpha` is zero-priced but not a `:free` route, so it needs `ATRADER_MODEL_ALLOWLIST`. Its provider is anonymous, and its data-retention terms could not be confirmed.
