# aTrader roadmap

Last updated **4 October 2026**. Feature IDs (F01–F37) come from [docs/03](docs/03-feature-map.md) and delivery stages from [docs/09](docs/09-validation-and-roadmap.md). Update this file whenever a feature changes status.

**Where we are:** the first working version runs end to end on live NSE data **with a real model**. On 4 October 2026, a compact run on L&T through OpenRouter (`stealth/space-bunny-alpha`) made 6 calls, all valid on the first attempt, at zero cost. Every figure checked against the XBRL facts was correct. Next: run the other nine pilot companies.

Status key: ✅ done · 🟡 partial · ⬜ not started · ⏸ deferred by decision

## Completed so far

**Research and planning**
- 10-document plan in `docs/`, reviewed against TradingAgents v0.6.0, which is pinned at commit `1394a3f`.
- Data pilot: every core NSE source was tested from this machine. Results are in [docs/05](docs/05-indian-data-strategy.md#data-pilot-results-4-october-2026).

**Data layer** (`src/atrader/data/`)
- NSE instrument master: symbol ↔ ISIN, with candidate suggestions for unknown symbols.
- NSE daily bhavcopy for all equities, plus all NSE index closes, stored in local SQLite. Holidays are remembered, and splits/bonuses are detected from the exchange's published previous close.
- XBRL quarterly results from both NSE eras (legacy up to Q3 FY25, Integrated Filing after). Standalone and consolidated stay separate, and restatements are flagged.
- Corporate announcements, with order-win intimations identified. Shareholding (promoter/public %).
- GDELT headlines, filtered to stories that name the company.
- A point-in-time `--cutoff`: only data public by that date is used.
- The evidence pack: every item gets an ID (`F3`, `M12`, `A2`…), and every source gets a coverage status (available, partial, stale, missing, access_blocked, not_requested).

**Analytics** (`src/atrader/analytics/`)
- Indicators: SMA 20/50/200, RSI, MACD, ATR, volatility, period returns, volume ratio, liquidity, and relative strength vs Nifty 50.
- Chart signals (versioned rules): moving-average trend, confirmed range breakout, unusual volume.
- Fundamentals: YoY/QoQ growth, margins, other income as a share of PBT, trailing EPS, P/E, approximate market cap, and Nifty P/E context.
- Vetoes: stale prices, short history, old results, low liquidity and missing core data cap or block the final assessment.

**Agents and graph** (`src/atrader/agents/`, `src/atrader/graph/`)
- TradingAgents-style agents, one file each: market, fundamentals and news analysts; bull and bear researchers; research manager; trader; aggressive, conservative and neutral debators; portfolio manager.
- Modes: `data_only` (0 calls), `compact` (6 calls, cap 8) and `full` (13 calls, cap 17).
- Claim verification: invented citations, and numbers without a backing fact or metric, are marked unsupported and never reach later agents.

**Model gateway** (`src/atrader/llm/`)
- Free-only OpenRouter routing: `:free` routes only, pricing checked live, unknown pricing rejected, and any reported cost disables the route.
- Per-run call cap, a daily allowance with a reserve, one repair attempt for invalid output, and a ledger of every attempt.
- Checkpointed runs: a run paused by the daily quota resumes without repeating finished agents.

**Product and quality**
- CLI: `research`, `resume`, `ingest`, `search`, `models`, `usage`, `runs`.
- Reports in Markdown and JSON, with coverage, a results table, metrics, catalysts, debate, model calls, filings used and limitations.
- 51 offline tests on synthetic data; ruff and mypy (strict) clean. Git repository initialised; nothing committed yet.

## Feature status

### Research capabilities

| ID | Feature | Priority | Status | What exists / what is missing |
|---|---|---|---|---|
| F01 | Company and listing search | P0 | 🟡 | NSE symbol/ISIN resolution and `atrader search`. Missing: BSE codes, symbol-change history |
| F02 | Watchlists and saved reports | P0 | 🟡 | Reports saved with pack, cutoff and sources; run registry. Missing: watchlists |
| F03 | Daily price/volume history | P0 | ✅ | NSE bhavcopy, adjustment basis, holidays, last complete bar. Missing: user CSV import path |
| F04 | Financial statements and key ratios | P0 | 🟡 | Quarterly P&L from XBRL, growth, margins. Missing: balance sheet, cash flow, bank/NBFC/insurer line items |
| F05 | Annual reports and presentations | P0 | ⬜ | No PDF extraction yet |
| F06 | Announcements and catalysts | P0 | ✅ | NSE disclosures with timestamps, dedup, routine filings filtered. BSE cross-posts not merged |
| F07 | Business segments and exposures | P0 basic | ⬜ | Segment facts exist in XBRL but are skipped for now |
| F08 | Company order backlog | P0 basic | 🟡 | Order-win intimations flagged; prompts forbid treating them as secured revenue. Missing: amounts and status from PDFs, reported backlog totals |
| F09 | Ownership and governance | P0 basic | 🟡 | Promoter/public % by quarter; governance disclosures reach the news analyst. Missing: pledges, auditor/director change parsing |
| F10 | Sector-aware valuation | P0 simple | 🟡 | Trailing P/E, approximate market cap, index P/E context. Missing: peer sets, bank metrics (P/B, ROA) |
| F11 | Company and sector news | P0 | 🟡 | GDELT company headlines with a relevance filter. Missing: sector news, publisher RSS, a reliable fallback when GDELT rate-limits |
| F12 | Macro and geopolitics | P0 basic | ⬜ | No RBI/MoSPI adapters, so no macro analyst yet |
| F13 | Reddit/community research | P1 cond. | ⏸ | Disabled until approved access and permitted processing are confirmed |
| F14 | Hindi/regional-language research | P1 | ⬜ | |
| F15 | Trend, momentum, volume, volatility | P0 | ✅ | Tested indicators |
| F16 | Chart-pattern detection | P0 simple | ✅ | Three versioned rules. Held-out validation is part of F32 |
| F17 | Relative strength and sector context | P0 | 🟡 | 3M vs Nifty 50 (price index). Missing: sector index comparison (the data is already ingested) |
| F18 | Bull/bear debate and judge | P0 | ✅ | Claim IDs, validated challenges, bounded rounds; research manager in full mode |
| F19 | Hypothetical strategy planner | P0 | ✅ | Trader writes stance, conditions, invalidation and scenarios; no execution tools |
| F20 | Risk review + final manager | P0 | ✅ | Three risk debators (full), portfolio manager, code vetoes after synthesis |
| F21 | Evidence verification and coverage | P0 | ✅ | Citation and number checks; coverage carried into the report. Human semantic audit is part of F32 |
| F22 | Research memory and change detection | P0 archive | 🟡 | Report archive. Missing: compare-to-previous-report, reflection |

### Product and platform

| ID | Feature | Priority | Status | What exists / what is missing |
|---|---|---|---|---|
| F23 | Report workspace and live progress | P0 | 🟡 | CLI progress and Markdown reports. Missing: FastAPI + Next.js workspace (deferred until reports prove useful) |
| F24 | Free-only OpenRouter gateway | P0 | ✅ | Live-tested 2026-10-04: zero cost reported; the run cap held at 8 when a bad config produced empty answers; reasoning models get a bounded effort and output budget |
| F25 | Resume, cancel, retry, partial result | P0 | 🟡 | Resume after quota pause, retry, repair, partial reports. Missing: cancel |
| F26 | Evidence-grounded follow-up questions | P1 | ⬜ | |
| F27 | Markdown/JSON export; print view | P0 | ✅ | Markdown and JSON written for every run |
| F28 | Side-by-side comparison | P1 | ⬜ | |
| F29 | Deterministic stock screener | P1 | ⬜ | Groundwork done: bhavcopy already stores every NSE equity |
| F30 | Local watchlist event alerts | P1 | ⬜ | |
| F31 | Prospective paper journal | P1 | ⬜ | |
| F32 | Historical evaluation and ablations | P0 harness | ⬜ | Groundwork done: `--cutoff` and point-in-time filtering |
| F33 | Hypothetical portfolio risk | P1 | ⬜ | |
| F34 | Market depth / order flow | P2 cond. | ⏸ | Needs an entitled broker feed |
| F35 | F&O, option chains, OI, IV | P2 cond. | ⏸ | |
| F36 | Public / multi-user deployment | P2 cond. | ⏸ | Needs data rights and a SEBI review |
| F37 | Broker execution | Out of scope | ⏸ | Not planned |

**Tally (37 features):** 10 done, 11 partial, 11 not started, 5 deferred. Of the 25 first-release (P0) features, 10 are done, 11 partial and 4 not started (F05, F07, F12, F32).

### Delivery stages (docs/09)

| Stage | Status | Remaining to exit |
|---|---|---|
| 0 — Prove data access | 🟡 nearly done | Zero-cost inference ✅ (4 Oct). Remaining: pull data for all ten pilot companies, not just L&T |
| 1 — Data foundation | 🟡 mostly done | Balance sheet/cash flow; CSV import. The web company page is deferred |
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
- [ ] Baselines: single-model synthesis vs compact vs full.
- **Exit:** a measured answer to "is full mode worth 2× the calls?"

### M3 — Indian data depth (F04, F05, F07, F08, F09, F17)
- [ ] Balance sheet and cash flow from half-yearly XBRL; bank/NBFC line items.
- [ ] Order-award extraction from announcement PDFs: amount or range, status, customer, execution period, with page citations.
- [ ] Reported backlog totals from results presentations.
- [ ] Promoter pledges from shareholding filings.
- [ ] Segment revenue and results from XBRL dimensions.
- [ ] Sector index relative strength.
- **Exit:** the order-backlog section works for at least one EPC company.

### M4 — Macro and news (F11, F12)
- [ ] RBI (policy rate, inflation) and MoSPI release adapters with release dates.
- [ ] Macro analyst: one new agent file plus one line in `graph/setup.py`.
- [ ] Sector news and a fallback when GDELT rate-limits.

### M5 — Research workspace (F02, F22, F23, F25, F28)
- [ ] Watchlists, compare with the previous report, and run cancel.
- [ ] FastAPI backend and Next.js workspace, once reports are useful enough to read daily.

### M6 — Screening and forward testing (F29–F31, F33)
- [ ] Deterministic screener over the stored bhavcopy universe.
- [ ] Local alerts on new material disclosures.
- [ ] Prospective paper journal: freeze each assessment before its outcome; review after 60+ sessions.

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
- A full `ingest` takes 30–40 minutes the first time (about 7 s per trading day at a polite rate).
- In `--dry-run`, model-call records are kept in memory only, so a resumed dry run lists only the calls made after resuming.
- The issuer/listing split from docs/07 is collapsed onto the ISIN until BSE mapping arrives.
- There is no `cancel` command yet. On Windows, stopping the terminal does not always stop the Python process, which can keep running until its call cap (this happened once on 4 October: 8 wasted calls, cap held).
- `stealth/space-bunny-alpha` is zero-priced but not a `:free` route, so it needs `ATRADER_MODEL_ALLOWLIST`. Its provider is anonymous, and its data-retention terms could not be confirmed.
