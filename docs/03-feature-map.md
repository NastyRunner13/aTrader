# Feature map

All rows are planned. **P0** = first usable release; **P1** = broader research release; **P2** = later/conditional. “Conditional” means an access or data gate remains, regardless of priority. IDs map to delivery work in [09](09-validation-and-roadmap.md).

## Research capabilities

| ID | Capability | Priority | Dependencies | Acceptance criterion |
| --- | --- | --- | --- | --- |
| F01 | Company and listing search | P0 | Verified instrument master | Resolve NSE/BSE aliases to the correct issuer and ISIN; show ambiguity |
| F02 | Watchlists and saved reports | P0 | Local database | Reopen a prior report with its original cutoff and sources |
| F03 | Daily price/volume history | P0 | Permitted adapter or CSV | Expose provider, missing sessions, adjustment basis, and last complete bar |
| F04 | Financial statements and key ratios | P0 | Filing/import pipeline | Reproduce supported metrics from cited values; distinguish standalone/consolidated |
| F05 | Annual reports and presentations | P0 | Text/table extraction | Open a cited page/span; mark extraction needing review |
| F06 | Company announcements and catalysts | P0 | Exchange/issuer source or upload | Deduplicate cross-posted announcements and retain publication timestamps |
| F07 | Business segments and exposures | P0 basic; P1 depth | Disclosures | Cite geography, customers, inputs, or revenue exposures; unknowns stay unknown |
| F08 | Company order backlog | P0 basic; P1 reconciliation | Disclosed contracts/reports | Separate stock of backlog, period order inflow, and provisional awards |
| F09 | Ownership and governance | P0 basic; P1 history | Shareholding and disclosures | Cite promoter holdings/pledges; flag comparability or coverage gaps |
| F10 | Sector-aware valuation | P0 simple; P1 scenarios | Normalized metrics/peer set | Ratios use comparable periods; non-comparable sectors are excluded |
| F11 | Company/sector news | P0 | Permitted feeds/documents | Group duplicate stories; separate reported fact from commentary |
| F12 | Macro and geopolitics | P0 basic; P1 exposure graph | News + macro + F07 | Show the exposure and mechanism behind each material impact claim |
| F13 | Reddit/community research | P1 conditional | Approved access and permitted use | Show sources, sample size, coverage, time window, and source failures |
| F14 | Hindi/regional-language research | P1 | Extraction/evaluation corpus | Retain original excerpt; evaluate translation and entity matching |
| F15 | Trend, momentum, volume, volatility | P0 | Clean daily bars | Deterministic indicators agree with independent fixtures |
| F16 | Chart-pattern detection | P0 simple; P1 advanced | Versioned detectors | Report definition, confirmation time, failure level, and sample evidence |
| F17 | Relative strength and sector context | P0 | Permitted benchmarks | Align sessions and distinguish price-return from total-return comparisons |
| F18 | Bull/bear debate and judge | P0 | Validated analyst packets | Both sides cite claims and address contradictions; rounds terminate |
| F19 | Hypothetical strategy planner | P0 | F18 + horizon | Conditions and invalidation are tied to evidence; no broker order created |
| F20 | Risk review + final manager | P0 combined; P1 separate perspectives | F19 + deterministic risk checks | Risk vetoes cannot be overruled by a persuasive narrative |
| F21 | Evidence verification and coverage | P0 | Source/claim registry | Unsupported material claims are removed or labeled before publication |
| F22 | Research memory and change detection | P0 archive; P1 reflection | Timestamped reports/outcomes | Past-as-of runs cannot retrieve future lessons |

## Product and platform capabilities

| ID | Capability | Priority | Dependencies | Acceptance criterion |
| --- | --- | --- | --- | --- |
| F23 | Report workspace and live progress | P0 | API + persistent run events | Reload/reconnect without restarting or losing completed stages |
| F24 | Free-only OpenRouter gateway | P0 | Model catalog/account access | Block paid models, unknown pricing, charged plugins, and paid fallbacks |
| F25 | Resume, cancel, retry, partial result | P0 | Durable worker/checkpoints | A stopped process resumes without duplicating completed logical work |
| F26 | Evidence-grounded follow-up questions | P1 | Saved evidence + quota | Cite existing report evidence; disclose when fresh research is needed |
| F27 | Markdown/JSON export; print view | P0 | Report schema | Export preserves sources, timestamps, gaps, and model identity |
| F28 | Side-by-side company/report comparison | P1 | Normalized basis | Clearly flag different periods, sectors, and data coverage |
| F29 | Deterministic stock screener | P1 | Broader authorized daily data | Filter universe without one LLM call per ticker |
| F30 | Local watchlist event alerts | P1 | Scheduler + event dedupe | Only new material changes trigger an alert; quota is shared |
| F31 | Prospective paper journal | P1 | Immutable decisions + later bars | Freeze signal before outcome; include rejected/abstained cases |
| F32 | Historical evaluation and ablations | P0 harness; P1 expansion | Point-in-time fixtures | Compare with deterministic and single-model baselines |
| F33 | Hypothetical portfolio risk | P1 | User inputs + correlation/liquidity | Compute limits locally; explain assumptions and missing positions |
| F34 | Market depth/order-flow analysis | P2 conditional | Entitled live broker feed | Show snapshot age and depth level; never infer depth from candles |
| F35 | F&O, option chains, OI, IV | P2 conditional | Historical/live rights and quality | Version contract specs and expiries; separate inferred from reported fields |
| F36 | Public/multi-user deployment | P2 conditional | Data rights, auth, capacity review | Demonstrate isolation, licensing, operational budget, and current regulatory review |
| F37 | Broker execution | Outside initial roadmap | Separate user decision and design | Requires a dedicated execution/risk project; not implied by analysis |

## Priority details

**F08 backlog:** the first version extracts disclosed totals and new awards with page references. A later version reconciles opening backlog, inflow, execution, cancellations, and FX/scope adjustments. It never manufactures the unknown reconciliation terms.

**F10 valuation:** begin with supported peer multiples and transparent scenarios. Add DCF only where cash-flow and capital assumptions are defensible. Banks/NBFCs need specialized metrics; industrial leverage rules should not be reused blindly.

**F12 geopolitics:** use structured scenarios. For example, a shipping disruption may affect a company with documented export routes; its effect depends on contract terms and cost pass-through. This is a design example, not a current market assertion.

**F16 charts:** start with moving-average trend, confirmed range breakout, and unusual volume. Double tops/bottoms and more subjective geometries need explicit tolerances, confirmation rules, and prospective validation before display as signals.

**F20 full versus compact:** full mode exposes separate risk agents; compact mode uses one combined risk/synthesis call. The UI must state which mode ran and which roles were combined or skipped.

## What makes the app better

The differentiator is the quality of Indian evidence and the ability to inspect it: reconciled company data, meaningful backlog tracking, falsifiable geopolitical scenarios, tested chart rules, preserved disagreement, honest missingness, and measurable cost/quality tradeoffs. More agent names alone do not improve a report.
