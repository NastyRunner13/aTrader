# Research and reuse assessment

Reviewed 4 October 2026 using primary project repositories, selected TradingAgents source files, and official provider documentation. This is a source review, not an execution benchmark or complete security audit. Default branches are mutable; no commit-pinned checkout was obtained. Pin and recheck a commit before copying code.

## Comparable projects

| Project | Observed approach | Useful lesson for aTrader | Fit and limitation |
| --- | --- | --- | --- |
| [TradingAgents](https://github.com/TauricResearch/TradingAgents) | Specialist reports feed research debate, strategy, risk debate, and a final manager | Preserve explicit roles and staged deliberation | Closest conceptual starting point; still requires an India-specific data/product layer |
| [AI Hedge Fund](https://github.com/virattt/ai-hedge-fund) | Current README describes investor agents, fund mandates, paper sessions, backtesting, and a persistent ledger; Financial Datasets supplies data | Separate research decisions from paper accounting; retain decision history and benchmark comparisons | Its stated educational use and data dependency do not establish free Indian coverage; older tutorials may describe a different tree |
| [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | Current project spans AutoGen reference code, a web research app, and a PydanticAI desktop system; separates financial computation and narration | Give every valuation and financial figure a deterministic computation path and provenance | Good reference for rigorous company reports; using its framework wholesale would conflict with the chosen LangGraph core |
| [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | Financial language-model adaptation, sentiment tasks, and forecasting examples | Evaluate domain-specific sentiment and extraction on labeled Indian examples | A model/data research project, not the complete application; do not start with fine-tuning or assume US-trained results transfer |
| [Qlib](https://github.com/microsoft/qlib) | Data processing, model research, backtesting, risk, and portfolio workflows | Treat signal evaluation and experiment tracking as independent systems | Valuable quantitative reference; India data preparation remains our responsibility |
| [FinRL](https://github.com/AI4Finance-Foundation/FinRL) | Reinforcement-learning agents interact with market environments in a train/test/trade workflow | Explicit environments, costs, temporal splits, and baselines | Optional later experiments; RL is unnecessary to deliver an evidence-based research MVP |

The comparison is architectural. No project is ranked by claimed investment returns, star count, or marketing descriptions.

## What the current TradingAgents source actually establishes

The inspected [graph setup](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/graph/setup.py) defines four analyst roles: market, social sentiment, news, and fundamentals. They run in separate subgraphs and join before bull/bear deliberation. A research manager passes its conclusion to a trader; aggressive, conservative, and neutral risk participants precede the portfolio manager. Tool loops and debate routing are bounded. These are useful existing behaviors, not proposed inventions.

The inspected [configuration](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/default_config.py) includes quick/deep models, debate limits, optional checkpointing, explicit vendor chains, macro news settings, and `.NS`/`.BO` benchmark mappings. Fundamentals include SEC EDGAR/Yahoo, macro defaults include FRED, and there are prediction-market settings. Indian suffix support does not establish complete Indian filings, ownership, or company-backlog coverage.

The [graph runtime](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/graph/trading_graph.py) includes instrument context, report persistence, checkpoint integration, streaming, and a memory/reflection path. The [state definition](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/agents/state.py) holds reports and debate state. Preserve the separation between intermediate research and the final result while adding typed evidence contracts.

## What we should improve or specialize

These are requirements for our app. “Not established” means the reviewed files did not demonstrate the feature; it is not a claim that no upstream branch or extension implements it.

| Area | Review finding | aTrader decision |
| --- | --- | --- |
| Agent flow | Staged workflow already exists | Adapt role boundaries; measure whether each extra stage helps |
| Indian identity | Benchmark suffix mapping exists | Maintain issuer, ISIN, exchange listing, symbol history, and provider IDs |
| Corporate information | Full Indian filing coverage not established | Build NSE/BSE/issuer document adapters and a manual import route |
| Financial semantics | India-specific reconciliation not established | Store reporting basis, period type, original units, and restatements |
| Backlog | Dedicated contract reconciliation not established | Add award/backlog extraction with explicit estimate-versus-disclosure labels |
| Geopolitics | Global news configuration exists | Map event → sector → company exposure → mechanism → uncertainty |
| Social evidence | A sentiment role exists | Require actual retrieved posts; never fill missing Reddit with invented sentiment |
| Chart patterns | Market analysis is part of the workflow | Version rule detectors and test them on held-out data |
| Reliability | Checkpoint and bounded-loop facilities exist | Make persistent recovery, cancellation, quota accounting, and partial results product requirements |
| Research traceability | Reports/state exist | Add claim IDs, source spans, immutable input manifests, calculation references, and missingness |
| Cost | Configurable model/vendor choices exist | Enforce a zero-priced allowlist and forbid charged tools/fallbacks |
| Learning | Memory/reflection exists | Evaluate timestamped lessons; never let hindsight contaminate past reports |

## Reuse strategy

Use TradingAgents as a **reference and selective upstream code source**, not as the entire product backend. Create our own company/evidence contracts and provider adapters first. Keep adapted graph/prompt code behind those interfaces, with a recorded upstream commit and local changes.

Forking wholesale would accelerate an initial demo, but would also retain assumptions about data formats, output state, and provider configuration that the Indian product must change. A selective adaptation is the recommended tradeoff; it is an engineering judgment, not a benchmark result.

The reviewed TradingAgents [LICENSE](https://github.com/TauricResearch/TradingAgents/blob/main/LICENSE) is **Apache-2.0**. When distributing adapted files, preserve applicable notices, include the license, mark modifications, and handle any upstream NOTICE requirements. Do not assume another repository's license from a tutorial. Recheck each exact file/dependency at the chosen commit. A code license does not grant market-data rights.

## Deliberate exclusions from initial reuse

- No reinforcement learning or model fine-tuning before a labeled Indian evaluation set exists.
- No celebrity-investor personas merely to increase agent count; disagreements should come from different evidence or objectives.
- No recursive “research everything” loop without a source, time, and request budget.
- No claimed accuracy or profitability imported from upstream papers into our product claims.
- No direct use of US-only financial metrics or SEC filings as substitutes for Indian disclosures.
