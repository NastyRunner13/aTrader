# Data and API contracts

Proposed contracts for implementation. These examples are specifications, not running endpoints. All times are stored as timezone-aware UTC instants, with Asia/Kolkata used for user-facing display and exchange-session interpretation.

## Core records

| Record | Required fields | Important invariant |
| --- | --- | --- |
| Issuer | issuer_id, legal_name, aliases, industry, source_ids | A company is distinct from a traded listing |
| Listing | listing_id, issuer_id, ISIN, exchange, symbol/code, currency, effective_from/to | Historical ticker mapping is effective-dated |
| ProviderPolicy | provider_id, dataset, permitted_use, terms_url, reviewed_at, retention, enabled | Unreviewed access paths are not silently enabled |
| SourceDocument | document_id, canonical_url, title, publisher, source_type, timestamps, content_hash, rights, revision_of | Preserve original publication time and version |
| EvidenceSpan | evidence_id, document_id, page/section/offset, excerpt, extraction_method, review_status | Cite an actual retrievable span; hash alone is insufficient |
| FinancialFact | fact_id, issuer_id, metric, value, currency, original_unit, period_start/end, basis, audit_status, evidence_ids | Null plus missing reason; never a fabricated zero |
| PriceBar | listing_id, interval, session, open/high/low/close, volume, provider, adjustment_basis, retrieved_at | Provider/basis is part of identity; reject impossible OHLC |
| CorporateAction | listing_id, action_type, announced_at, ex_date, terms, evidence_ids | Adjustments are versioned and date-aware |
| OrderAward | issuer_id, award_id, status, amount/range, currency, customer, scope, execution_window, evidence_ids | Provisional and binding awards are distinguishable |
| BacklogObservation | issuer_id, period_end, amount, unit, definition, scope, evidence_ids | Not conflated with individual awards or exchange depth |
| MarketDepthSnapshot | listing_id, exchange_time, received_at, bids, asks, levels, provider | Optional P2; does not share the backlog schema |
| Event | event_id, category, entity_ids, event_at, published_at, source_ids, cluster_id | Syndicated copies are one underlying event |
| Exposure | issuer_id, factor, magnitude/range, unit, period, evidence_ids, status | Unquantified exposure stays unquantified |
| DerivedMetric | metric_id, name, value, inputs, formula_version, as_of, quality_flags | Reproducible from stored inputs |
| Claim | claim_id, statement, kind, evidence_ids, metric_ids, assumptions, counterclaim_ids, status | Facts, calculations, interpretations, and scenarios are different kinds |
| AgentReport | agent_id, run_id, claims, stance, gaps, model_call_ids | Successful parsing is not proof of factual validity |
| DebateTurn | run_id, role, turn_index, claims, challenged_claims, unresolved | Bounded and ordered |
| ResearchRun | run_id, listing_id, horizon, cutoff, mode, plan_version, manifest_id, state, budget | Immutable inputs after execution starts |
| ModelCall | call_id, run_id, node, attempt, requested/served_model, provider, tokens, cost, status | Every dispatched attempt is recorded |
| ResearchReport | report_id, version, run_id, assessment, coverage, claims, risks, conditions | Complete, partial, and insufficient-evidence reports differ |
| Outcome | report_id, evaluation_window, observed_at, benchmark, costs, result | Never accessible before its observation date |

Price-series uniqueness includes listing, interval, timestamp, provider, and adjustment basis. Financial-fact uniqueness also includes period, reporting basis, metric, and source revision. Use Decimal-compatible values for monetary accounting and unit conversion; numerical-array arithmetic is acceptable for indicators with tested tolerances.

## Example analyst result

This is a synthetic schema illustration; it describes no actual company.

```json
{
  "agent_id": "company_analyst",
  "run_id": "example-run",
  "status": "partial",
  "assessment": "mixed",
  "claims": [
    {
      "claim_id": "c-001",
      "kind": "interpretation",
      "statement": "The disclosed award may improve revenue visibility, but execution timing is unclear.",
      "evidence_ids": ["example-award-page-2"],
      "metric_ids": [],
      "assumptions": ["The award proceeds under the disclosed terms."],
      "counterclaim_ids": [],
      "status": "needs_review"
    }
  ],
  "missing_data": [
    {"field": "execution_schedule", "reason": "not_disclosed"}
  ]
}
```

The verifier resolves every referenced ID within that run's authorized manifest. It rejects nonexistent citations, future-dated evidence, unsupported units, and claims crossing issuers. Every material numerical statement must point to a FinancialFact or DerivedMetric. Validate the final assembled report again after synthesis.

## HTTP API

| Method and route | Purpose | Contract behavior |
| --- | --- | --- |
| GET /v1/instruments?query= | Search listings | Returns exchange, ISIN, issuer, aliases, coverage |
| GET /v1/companies/{id} | Company snapshot | Includes provenance, reporting basis, freshness |
| GET /v1/listings/{id}/bars | Chart data | Interval/date/basis parameters; gaps and provider included |
| POST /v1/documents | Upload permitted research documents | Size/type validation; asynchronous extraction; no automatic trusted status |
| GET /v1/documents/{id} | Inspect document metadata/evidence | Access check; content served only when retention/display allowed |
| POST /v1/research-runs | Create a run | Accept listing_id, horizon, cutoff, mode, document_ids; returns 202 and run_id |
| GET /v1/research-runs/{id} | Inspect run | Stage states, usage, coverage, errors, and available result |
| GET /v1/research-runs/{id}/events | SSE progress | Monotonic event IDs; reconnect supports Last-Event-ID |
| POST /v1/research-runs/{id}/cancel | Request cancellation | Idempotent; stops scheduling new work |
| POST /v1/research-runs/{id}/resume | Resume eligible checkpoint | Rejects changed input/configuration and incompatible versions |
| GET /v1/reports/{id} | Read immutable report version | Typed sections and provenance |
| GET /v1/reports/{id}/export?format= | Markdown or JSON export | Same validation and rights rules as UI |
| POST /v1/watchlists | Create watchlist | Explicit listing IDs, no alias ambiguity |
| PATCH /v1/watchlists/{id} | Update watchlist | Version/concurrency check |
| POST /v1/reports/{id}/questions | P1 follow-up | Separate budgeted child run tied to frozen evidence |
| GET /v1/providers/status | Source health | Includes access, freshness, failures, entitlement unknowns |
| GET /v1/models/availability | Eligible models | Backend-filtered zero-cost and capability status |
| GET /v1/usage | Quota/attempt ledger | Shows conservative remaining estimate and source of estimate |

Creation supports an `Idempotency-Key`. Same key and payload returns the same job; same key with a different payload returns conflict. Validate instrument identity before quota reservation. Use request identifiers in errors, without leaking provider keys or document contents.

Run states: `queued`, `running`, `paused_quota`, `cancel_requested`, `cancelled`, `completed`, `partial`, `failed`. Evidence sufficiency is a report assessment, not a hidden run error. Authentication, invalid input, conflicts, and temporary quota failures have distinct responses; do not report all as HTTP 500.

## Frontend requirements

**Watchlist:** identity, latest data date, research date, coverage, and changes since last report. A screen load must not automatically trigger AI research.

**Stock workspace:** overview, company data, charts, catalysts, debate, and sources. Keep the assessment, cutoff, and coverage visible. Chart overlays correspond to versioned detector results, and each metric opens its calculation/source trail.

**Run view:** stage progress with completed, skipped, failed, and waiting states; elapsed time; request allowance used; cancel/resume controls. Display concise agent arguments and tool outcomes, not claims to expose hidden model reasoning.

**Settings:** OpenRouter connection, eligible model selection, source availability, privacy choices, local retention, and imports. Never label an unverified source as connected.

**Empty/error states:** distinguish “no relevant results” from “source request failed”; “not applicable” from “missing”; “quota exhausted” from “research finished”; and “market closed” from “no price data.”
