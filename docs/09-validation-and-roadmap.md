# Validation and delivery roadmap

This roadmap prioritizes a complete vertical slice before broad data coverage. Stages are dependency-based, not time estimates. All acceptance gates below are proposed targets; none has yet been executed.

## Stage 0 — Prove data access and freeze the baseline

Feature IDs: F01, F03–F06, F08, F24.

- Select ten pilot companies across financials, IT/services, industrials/EPC, consumer, and commodities; include at least one backlog-reporting business. These are test subjects, not investment recommendations.
- Verify identities and obtain permitted daily bars plus at least two annual reporting periods, recent quarters, and selected disclosures where available.
- Attempt a personal price adapter; retain permitted CSV imports as the guaranteed application input path. Verify actual access, adjustments, session gaps, and retention/display rights.
- Review a sample annual report, results document, shareholding filing, and order-award notice. Record extraction failures and manual work required.
- Verify an OpenRouter free account, current quota, model metadata, and one validated structured response. No paid top-up is a prerequisite.
- Choose and record a TradingAgents commit and exact reusable files; review notices before code incorporation.

**Exit:** a source/access matrix based on actual retrieval, versioned permitted fixtures, and demonstrated zero-cost inference. If data cannot be obtained automatically, the pilot can proceed through documented imports; it cannot claim automated coverage.

## Stage 1 — Data foundation and first useful screen

Feature IDs: F01–F07, F09–F10 basic, F15, F17, F21, F23–F25, F27.

Implement contracts, source storage, normalization, calculation functions, job queue, persistent graph checkpoints, model gateway, and one Next.js company page. Display daily bars, financial figures, sources, and coverage before adding debate.

**Exit:** every displayed number is traceable and reproducible; unit/basis and corporate-action fixtures pass; failed providers produce visible missingness; refresh and restart preserve completed work; paid model routes are blocked by tests.

## Stage 2 — Compact research vertical slice

Feature IDs: F08 basic, F11–F12 basic, F16 simple, F18–F21, F23, F27.

Implement the six-call compact graph, claim registry, citation verification, report rendering, and report archive. News/macro coverage starts with a bounded set of permitted sources and uploaded documents. Backlog extraction has explicit review status.

**Exit:** a real pilot company completes from input to evidence-linked report within the hard request cap; insufficient-evidence cases abstain; a cancelled run stays cancelled; a resumed run uses its original inputs; exports retain coverage and citations.

## Stage 3 — Full research and stronger Indian coverage

Feature IDs: F07–F14 depth, F16 expansion, F18–F22, F26, F28.

Add full specialist/debate/risk roles, governance and backlog reconciliation, sector-specific metrics, report comparison, and grounded follow-ups. Implement Reddit only after access and processing permission are verified. Hindi/regional sources need evaluation before becoming decision-bearing evidence.

**Exit:** full mode adds measurable research value over compact mode on a blinded evaluation set. If it does not, keep compact as default and revise or remove weak roles. Social failure must not block the other research branches.

## Stage 4 — Screening, monitoring, and prospective paper evaluation

Feature IDs: F22 reflection, F29–F33.

Expand the deterministic universe scanner, add local material-event alerts, and freeze timestamped hypothetical decisions before observing outcomes. Add portfolio inputs only with local-first handling. Reflection begins as error categorization and suggested prompt improvements, not automatic self-modification.

**Exit:** maintain a prospective evaluation record for a chosen initial window, proposed as at least 60 trading sessions for operational learning. That sample is not enough by itself to establish a durable investment edge. Include failures, abstentions, and changing coverage in results.

## Stage 5 — Conditional extensions

Feature IDs: F34–F36.

Consider live depth, derivatives, public hosting, or multi-user access only after data rights, operating costs, and product requirements are clear. Public investment-research distribution needs a current review of the applicable regulatory framework; the [SEBI Research Analysts master circular](https://www.sebi.gov.in/legal/master-circulars/feb-2026/master-circular-for-research-analysts_99571.html) is a starting reference, not a conclusion that a particular deployment is exempt or compliant. Broker execution remains a separate scope decision.

## Evaluation design

### Research-quality set

Create an initial 30-case set across sectors and conditions: clean financial statements; losses; bank metrics; missing cash flow; standalone/consolidated conflict; lakhs versus crores; revised filings; renamed symbols; splits; short price history; provisional order awards; duplicated stories; stale news; unverified rumors; geopolitical exposure with and without company evidence; and malicious instructions inside documents.

Use synthetic fixtures for exact invariants and permitted real documents for extraction/research assessment. Human-review the gold labels and source spans. Separate prompt-development cases from the final held-out set, and keep all variants of the same event/company filing in one split to reduce leakage.

| Test | Proposed gate |
| --- | --- |
| Currency/unit/reporting-basis and identity fixtures | 100% pass on deterministic cases |
| Published material claim IDs and metric references | 100% resolve to allowed run evidence |
| Human-reviewed support for material claims | At least 95% on held-out sampled claims; report denominator and uncertainty |
| Fabricated sources or material unsupported numerical claims | Zero in release acceptance set |
| Invalid/missing inputs | Correct partial/abstain behavior on every critical fixture |
| Zero-cost enforcement | Every paid/unknown route blocked in policy fixtures; confirm live smoke-test observed cost |
| Recovery and isolation | Restart/retry tests preserve inputs and separate concurrent run/company state |
| Injection resistance | Test documents cannot alter retrieval policy, model routing, secrets, or output schema |

These are quality gates for software and research integrity, not promised real-world prediction accuracy.

### Chart and strategy evaluation

Start with deterministic rules, including moving-average trend, confirmed breakouts, and volume anomalies. Record the earliest time a pattern could be known. Pivot-based patterns often require future bars to confirm; their signal timestamp must be confirmation time, not the earlier pivot date.

Use chronological train/development/held-out windows with a gap appropriate to the outcome horizon. Avoid overlapping outcome leakage, hindsight-based parameter selection, and survivorship bias. If only today's constituents are available, label that limitation rather than describing the result as a historical whole-market test.

Signals after market close execute hypothetically at the next eligible session under an explicit fill assumption. Include slippage, spreads where available, brokerage, relevant taxes/levies, and rejected/unfillable orders. Fee schedules are effective-dated inputs to verify when implementing, not constants invented in this plan. Daily bars cannot prove an intraday stop/target execution order; use conservative conventions and report ambiguity.

Compare with buy-and-hold, an appropriate Indian benchmark, a simple technical rule, one-model synthesis, compact debate, and full debate. Align return basis, sessions, cash treatment, and risk exposure. A price index is not interchangeable with a total-return index.

Measure drawdown, volatility, turnover, exposure, net returns, event hit rates where well-defined, and coverage/abstention. Report sampling uncertainty and multiple-testing risk. If displaying predictive probabilities later, measure calibration/Brier score rather than relabeling an LLM's self-confidence as probability.

### LLM leakage and model drift

Restrict tools and memory to historically available evidence, but acknowledge pretrained models may remember later events. Label retrospective LLM replay as potentially contaminated. Forward paper records freeze prompt/model/evidence before outcomes and are therefore central to evaluation.

Re-run research-quality regression cases when changing the model, extraction pipeline, prompts, or metric formulas. A free-model replacement is a product change, even if its API schema stays the same.

## Decision log

| Decision | Initial choice | Revisit when |
| --- | --- | --- |
| Fork or adapt | New app with selective upstream reuse | A pinned upstream implementation demonstrably fits our contracts |
| Trading horizon | Daily data; 5–20 sessions and 6–12 months | Intraday rights and data quality are proven |
| Usage scope | Personal/local | User requests external access |
| Universe | Ten diverse pilot companies | Source coverage and validation pass |
| Data path | Imports + permitted adapters | Account-specific broker entitlements are verified |
| Database | Local SQLite with one worker | Concurrent workload or multi-user access requires PostgreSQL |
| AI defaults | Compact; tested free OpenRouter routes | Full mode shows useful quality gains within quotas |
| Community | Optional/disabled until approved | Actual Reddit access and permitted processing confirmed |
| Portfolio | Optional later; local calculations | User wants portfolio-aware research |

Implementation can begin with these assumptions without another architecture decision. The first unresolved facts to establish are provider access, free-model quality, and document extraction reliability.
