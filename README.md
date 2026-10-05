# aTrader — Indian equity research agents

Status (5 October 2026): **first working version, with a signal card.** A Python + LangGraph command-line app researches one NSE-listed company. It runs on official NSE data, uses agents structured like [TradingAgents](https://github.com/TauricResearch/TradingAgents), cites evidence for each claim and calls only free OpenRouter models. Each run ends in a one-screen **signal card**: a 0–100 score and signal for 1 month, 6 months and 2 years, scores by area, pros and cons, price ranges, **price levels** (support and resistance zones, moving averages, anchored VWAPs, the heaviest-traded band) and the **closes that would flip each signal**. FastAPI and Next.js come later (see [09](docs/09-validation-and-roadmap.md)).

The scores are experimental: the rules and weights are starting values that have not been validated against history yet. This is research, not investment advice.

## Quick start

```bash
uv sync
```

```bash
copy .env.example .env
```

Put your `OPENROUTER_API_KEY` in `.env`. Then:

```bash
uv run atrader ingest
```

```bash
uv run atrader research LT --dry-run
```

```bash
uv run atrader research LT --mode compact
```

- `ingest` downloads about 300 sessions of NSE bhavcopy and index files once, plus about 100 sessions of delivery-position files. That takes 30–40 minutes at a polite pace (about 7 s per trading day); later runs fetch only new days.
- `--dry-run` runs the whole graph on real data with placeholder model output, so it costs no requests.
- Each run prints the signal card and writes three files to `reports/`: the card (`<SYMBOL>-<date>-<mode>-<run>.md`), the full analysis (`…-details.md`) and everything as `.json`.
- `--mode data_only` makes no model calls and still gives a code-only scorecard (news is not scored).

| Command | What it does |
|---|---|
| `atrader research SYMBOL --mode data_only\|compact\|full` | Research one company (0 / 6 / 11 model calls) |
| `atrader resume RUN_ID` | Continue a run that paused when the daily quota ran out |
| `atrader search "larsen"` | Find NSE symbols and ISINs |
| `atrader models` | List free models the policy allows, and check the configured ones |
| `atrader usage` / `atrader runs` | Today's request count / recent runs |

## How it works

```text
data_steward          code: NSE data, metrics, base scores, vetoes
   ├─ market_analyst        ┐
   ├─ fundamentals_analyst  ├─ at the same time
   └─ news_analyst          ┘
   ├─ bull_researcher       ┐  at the same time, per round:
   └─ bear_researcher       ┘  one round (compact) or two (full)
   ├─ aggressive_debator    ┐
   ├─ conservative_debator  ├─ at the same time, full mode only
   └─ neutral_debator       ┘
portfolio_manager     pros, cons, horizon notes, up to ±5 per horizon
finalize              code: the scorecard, signals, price ranges, vetoes
```

- **Data steward (code):** pulls official NSE data: the equity master (ISIN), daily bhavcopy prices, delivery positions, Nifty 50 and the stock's sector index (from NSE's industry classification), XBRL quarterly results, corporate announcements (including order wins) and shareholding. It also pulls GDELT headlines. It computes indicators, volume and delivery flows, price levels, chart signals, growth, margins and P/E in Python, and freezes everything into an **evidence pack** where every item has an ID (`F3`, `M12`, `A2`, …).
- **Agents (LLM):** every claim must cite pack IDs. Code checks each claim. A claim citing an ID that doesn't exist, or a number with no backing fact or metric, is marked unsupported and never reaches later agents.
- **Scorecard (code, `analytics/scoring.py`):** each area (technical, growth & quality, valuation, news) starts at 50, and rules add or subtract points from the metrics, each citing its evidence. Technical rules come in five groups (trend ±10, momentum ±6, performance ±8, breakout ±6, flows ±10), and each group's total is capped, so one price move is not counted once per indicator. Valuation compares the P/E with the stock's NSE sector index first and the Nifty 50 second. An analyst may move its own area by up to ±15 with cited evidence; the news area comes from the news analyst's rated events. Each horizon weights the areas differently:

  | Area | 1 month | 6 months | 2 years |
  |---|---|---|---|
  | Technical | 45% | 20% | 5% |
  | Growth & quality | 15% | 35% | 45% |
  | Valuation | 10% | 25% | 35% |
  | News & catalysts | 30% | 20% | 15% |

  The portfolio manager may move a horizon by up to ±5. A missing area is left out and its weight shared among the rest (never counted as 50); below 60% coverage there is no signal. Signals: Strong Bearish 0–29, Bearish 30–44, Neutral 45–55, Bullish 56–70, Strong Bullish 71–100. Price ranges are code-computed: ±1 standard deviation of past volatility for 1 and 6 months, bear/base/bull EPS × P/E scenarios for 2 years. They are not forecasts. Price levels come from confirmed swing points, moving averages, anchored VWAPs and the heaviest-traded price band. Signal flips are found by re-scoring a hypothetical next close until a signal changes. Levels describe the past; they are not entries, stops or targets.
- **Vetoes (code):** stale prices, short price history, old results and low liquidity hold every horizon at Neutral or below. Missing core data withholds the signal.
- **Gateway:** only zero-priced `:free` routes are used. Up to 4 calls run at once. Each run has a hard call cap (8 compact, 14 full), and a daily allowance is enforced locally. Each invalid answer gets one repair attempt. When the quota runs out, the run is checkpointed so it can be resumed.

## Code layout

The agents follow TradingAgents' layout: one file per agent, each with a `create_<agent>(llm)` factory that returns a graph node.

```text
src/atrader/
  agents/
    analysts/      market_analyst.py  fundamentals_analyst.py  news_analyst.py
    researchers/   bull_researcher.py  bear_researcher.py
    managers/      portfolio_manager.py
    risk_mgmt/     aggressive_debator.py  conservative_debator.py  neutral_debator.py
    state.py       AgentState
    context.py     evidence pack -> prompt text
    utils.py       shared rules, one structured call, claim verification glue
  graph/
    setup.py       GraphSetup.setup_graph(mode)   -- wires the agents together
    conditional_logic.py
    research_graph.py   ResearchGraph(...).run("LT")  -- the entry point
  data/            NSE + GDELT adapters, XBRL parser, SQLite store, evidence builder
  analytics/       indicators, chart signals, fundamentals, vetoes, scoring, price ranges
  llm/             free-only OpenRouter gateway, policy, usage ledger, fake gateway
  verification/    claim, citation, score-adjustment and event checks
  report/          signal card, full-analysis Markdown and JSON
```

Run the tests with `uv run pytest` and lint with `uv run ruff check src tests`. Tests are offline and use synthetic data.

## Plan documents

**[ROADMAP.md](ROADMAP.md)** tracks what is done, what is partial, and the next milestones.

| Document | What it answers |
| --- | --- |
| [01 — Product definition](docs/01-product-definition.md) | What are we building, for whom, and what does the first release do? |
| [02 — Research and reuse](docs/02-research-and-reuse.md) | How do TradingAgents and comparable projects work? What should we reuse? |
| [03 — Feature map](docs/03-feature-map.md) | Which features ship first, later, or only if data access permits? |
| [04 — Agent system](docs/04-agent-system.md) | Every analyst, debater, manager, graph stage, and stopping rule |
| [05 — Indian data strategy](docs/05-indian-data-strategy.md) | Sources, access limits, freshness, provenance, and both kinds of order book |
| [06 — Technical architecture](docs/06-technical-architecture.md) | Backend, frontend, storage, workers, reliability, and security |
| [07 — Data and API contracts](docs/07-data-and-api-contracts.md) | Core entities, structured outputs, endpoints, and UI behavior |
| [08 — Free operation and OpenRouter](docs/08-free-operation-and-openrouter.md) | What can be free, request budgets, model selection, and failure handling |
| [09 — Validation and delivery roadmap](docs/09-validation-and-roadmap.md) | Build sequence, acceptance gates, evaluation, and unresolved decisions |
| [10 — Research source register](docs/10-source-register.md) | Primary references and verification limits |

## Limits worth knowing

- This is research, not advice. It places no orders.
- NSE filings, announcements and shareholding come from NSE website endpoints. They are used for personal research at a polite request rate; they are not a licensed feed and can change without notice.
- Prices are end-of-day only. Order-backlog amounts sit inside announcement PDFs and are not extracted yet.
- Macro (RBI, MoSPI) and Reddit sources are not built yet; reports list them as not requested.
- A report on a past date is not a clean backtest: models may remember events after the cutoff.
