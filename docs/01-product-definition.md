# Product definition

Date: 4 October 2026. All requirements below are proposed aTrader behavior, not claims that the application already exists.

## Product promise

Help an individual research an Indian listed company and understand **what the evidence says, where analysts disagree, what is missing, and which events would invalidate the thesis**.

The application combines information retrieval, reproducible calculations, specialist interpretation, debate, and risk assessment. The output is a research record that can be revisited as new information arrives.

## Main user journey

1. Search a company by name, NSE symbol, BSE code, or ISIN. Confirm the exchange listing and company identity.
2. Choose a horizon: swing research, initially 5–20 trading sessions; investment research, initially 6–12 months. These are analysis settings, not return promises.
3. See available data, missing sources, data timestamps, and the maximum AI request allowance before running.
4. Select compact or full research. Optionally attach annual reports, presentations, financial statements, or permitted CSV exports.
5. Watch named research stages progress; inspect citations and calculations as they complete.
6. Read the thesis, bear case, risk constraints, technical context, evidence quality, and unresolved questions.
7. Save to a watchlist, compare with an earlier report, export the report, or ask a follow-up against its evidence.

## What the research covers

**Company:** business segments, revenue geography, customers where disclosed, competition, financial history, cash generation, leverage, valuation, management guidance, corporate actions, ownership, promoter pledging, governance concerns, and material announcements.

**Order backlog:** disclosed unexecuted contracts, order inflow, cancellations, execution horizon, customer concentration, and management's definitions. Applicable mainly to businesses that actually disclose meaningful backlog; missing backlog is not zero backlog.

**External environment:** company and sector news, regulation, RBI policy, inflation, currency, commodity inputs, trade restrictions, elections and budgets, conflicts, shipping disruptions, weather, and international demand. Each suggested impact needs a company exposure and a plausible transmission mechanism.

**Community:** Reddit and other explicitly permitted public sources. Discussion is an indication of attention or sentiment, not proof of company performance. Record when the source was unavailable or the sample too small.

**Charts:** daily OHLCV, volume, trend, momentum, volatility, relative strength, support/resistance candidates, and rule-defined patterns. Python detects signals; the agent explains them.

**Deliberation:** bull case, bear case, research judge, hypothetical strategy, aggressive/conservative/neutral risk perspectives, and final portfolio-aware synthesis. Full mode retains these separate roles; compact mode visibly combines some roles.

## Report structure

| Section | Required contents |
| --- | --- |
| Header | Company identity, exchange, horizon, knowledge cutoff, generated time, model/configuration version |
| Summary | Supportive / mixed / adverse / insufficient-evidence assessment; top reasons; no invented probability |
| Coverage | Available, stale, missing, blocked, and not-applicable source categories |
| Company | Metric tables, reporting basis, filing dates, source pages, business context |
| Catalysts | Confirmed events, possible events, dates, affected exposures, competing interpretations |
| Chart | Data provider, adjustment basis, signal dates, conditions, invalidation levels if justified |
| Debate | Claim-level challenges, responses, unresolved disagreements, evidence references |
| Risk | Concentration, liquidity, leverage, gaps, event uncertainty, downside scenarios |
| Decision conditions | What would strengthen, weaken, or invalidate the thesis |
| Appendix | Sources, calculation versions, source failures, usage, and limitations |

Show data quality separately from the stance. A strongly negative report can be well supported; a bullish report can have poor evidence. Confidence labels describe evidence adequacy until predictive probabilities have been calibrated.

## Scope boundaries

The first release is local and read-only. It does not place trades, require a broker account, forecast guaranteed returns, or offer unlimited whole-market deep research. Live order-book depth, options analytics, tick archives, public hosting, and multi-user distribution are later, conditional work.

Backtesting a historical prompt with a modern LLM can still leak knowledge from model training. Historical reports must disclose this limitation; prospective paper records are the stronger test for the LLM layer.

## Product success measures

- A user can inspect the source behind every material factual claim and financial figure.
- Contradictory disclosures remain visible rather than being averaged into a false certainty.
- A missing news, social, or model provider produces an honest partial result.
- A run never silently spends money or exceeds its application request budget.
- The full graph is measurably useful compared with simpler research baselines.
- A second report makes changes in evidence and thesis easy to understand.

Quality thresholds and pilot acceptance tests are defined in [09](09-validation-and-roadmap.md). They are release targets to measure, not achieved results.
