# Research source register

Reviewed **4 October 2026**. Prefer these primary sources over tutorials when implementation begins. Links to default branches and provider policies may change. Observations below describe the reviewed material; proposed aTrader features elsewhere are our design.

## Project references

| Ref | Source | Used for |
| --- | --- | --- |
| R01 | [TradingAgents repository](https://github.com/TauricResearch/TradingAgents) | Overall project baseline |
| R02 | [TradingAgents graph setup](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/graph/setup.py) | Analyst fan-out/join, role sequence, loop bounds |
| R03 | [TradingAgents configuration](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/default_config.py) | Vendor chains, limits, checkpoint option, benchmark mappings |
| R04 | [TradingAgents runtime](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/graph/trading_graph.py) | Identity context, reports, memory, streaming, checkpoint integration |
| R05 | [TradingAgents state](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/agents/state.py) | Shared report and debate state |
| R06 | [TradingAgents license](https://github.com/TauricResearch/TradingAgents/blob/main/LICENSE) | Apache-2.0 baseline and copying obligations |
| R07 | [AI Hedge Fund](https://github.com/virattt/ai-hedge-fund) | Paper ledger, mandates, backtesting, current data dependency |
| R08 | [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | Financial computation/provenance and research orchestration |
| R09 | [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | Domain modeling, sentiment, forecasting adaptation |
| R10 | [Qlib](https://github.com/microsoft/qlib) | Quantitative experiment and evaluation pipeline |
| R11 | [FinRL](https://github.com/AI4Finance-Foundation/FinRL) | RL/environment approach and why it is deferred |

## Model/runtime references

| Ref | Source | Used for |
| --- | --- | --- |
| R12 | [OpenRouter pricing](https://openrouter.ai/pricing) | Current free-plan daily allowance |
| R13 | [OpenRouter limits](https://openrouter.ai/docs/api_reference/limits) | Account quota inspection, throttling, error handling |
| R14 | [Free models router](https://openrouter.ai/openrouter/free) | Free routing behavior and model variability |
| R15 | [Structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs) | Endpoint capability constraints |
| R16 | [OpenRouter privacy](https://openrouter.ai/docs/guides/privacy/data-collection) | Prompt/provider handling distinction |
| R17 | [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | Checkpoints versus long-term stores |
| R18 | [FastAPI background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) | Backend task boundary |
| R19 | [Next.js App Router](https://nextjs.org/docs/app) | Frontend framework reference |
| R20 | [Lightweight Charts](https://tradingview.github.io/lightweight-charts/) and [license](https://github.com/tradingview/lightweight-charts/blob/master/LICENSE) | Chart renderer and dependency review |

## Indian data and news references

| Ref | Source | Used for |
| --- | --- | --- |
| R21 | [NSE data policy](https://www.nseindia.com/static/market-data/nse-data-policy) | Access versus redistribution distinction |
| R22 | [NSE announcements](https://www.nseindia.com/companies-listing/corporate-filings-announcements) | Corporate disclosure discovery |
| R23 | [SEBI corporate-filings directory](https://www.sebi.gov.in/curation/corporate_filings.html) | Exchange filing/shareholding source routes |
| R24 | [NSE historical data products](https://www.nse.in/static/market-data/eod-historical-data-subscription) | Paid order/trade historical data context |
| R25 | [yfinance](https://github.com/ranaroussi/yfinance) | Unofficial personal-use prototype data route |
| R26 | [Upstox V3 historical candles](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/) | Candidate historical adapter |
| R27 | [Upstox income statements](https://upstox.com/developer/api-documentation/get-income-statement/) | Candidate structured company-data adapter |
| R28 | [Kite pricing](https://zerodha.com/products/api/) | Free account features versus paid data tier |
| R29 | [Reddit developer access](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Reddit-Developer-Interfaces) and [API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki) | Access and policy dependency |
| R30 | [GDELT DOC API announcement](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/amp/) | Global news discovery candidate; historical documentation |
| R31 | [RBI Handbook/DBIE release](https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=58701) | Official macro-data source role |
| R32 | [MoSPI](https://www.mospi.gov.in/) and [PIB](https://www.pib.gov.in/) | Official release discovery candidates; not tested adapters |
| R33 | [SEBI RA master circular, February 2026](https://www.sebi.gov.in/legal/master-circulars/feb-2026/master-circular-for-research-analysts_99571.html) | Reference for future public-distribution review |

## Verification boundaries

- Selected TradingAgents source files were inspected through web access. A direct Git remote lookup failed because the execution environment could not connect; no local upstream checkout or exact commit was verified.
- Comparable-project findings are based on current repository documentation, not executing their applications or verifying their performance claims.
- No model call, authenticated broker request, Reddit access application, exchange adapter, or licensed data redistribution was tested.
- Public filing pages establish source locations, not a supported scraping contract. Some pages were partially rendered or inaccessible through the research tool.
- Upstox pricing/entitlement remains unresolved. The data plan deliberately makes it optional.
- Some numeric placeholders in the OpenRouter limits page were absent in rendered output. The 50/day planning figure comes from the separate official pricing page; actual account limits remain runtime inputs.
- Regulations, source terms, model availability, and quotas require rechecking before implementation or deployment. This pack does not establish legal permission for a future commercial product.

The immediate next research step is the hands-on access and extraction pilot in [09](09-validation-and-roadmap.md), not collecting more agent-framework names.
