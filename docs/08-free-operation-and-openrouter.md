# Free operation and OpenRouter

Research date: 4 October 2026. The baseline requires no paid subscription or top-up. This is feasible for a small local research tool; it does not imply unlimited model calls, free data rights, or free always-on hosting.

## Verified constraints

[OpenRouter pricing](https://openrouter.ai/pricing) currently lists **50 requests/day** for the free plan. Its [limits documentation](https://openrouter.ai/docs/api_reference/limits) documents account usage inspection through `GET /api/v1/key`, provider-side throttling, and retry behavior. Some numerical values in the limits page did not render in this research tool, so no hard-coded RPM or purchased-credit tier is asserted here. Use current account metadata and actual errors during implementation.

[`openrouter/free`](https://openrouter.ai/openrouter/free) selects from available free models and filters for requested capabilities. The served model can change. For repeatable evaluation, prefer an explicit tested free model ID and record the actual served model/provider; use the free router only when its variability and privacy policy are acceptable.

[Structured output support](https://openrouter.ai/docs/guides/features/structured-outputs) varies by endpoint. Capability checks and local schema validation are still required. [OpenRouter privacy documentation](https://openrouter.ai/docs/guides/privacy/data-collection) distinguishes OpenRouter handling from provider handling; free availability must not be assumed to imply a particular retention guarantee.

## Zero-cost gateway policy

All calls go through one backend gateway. It must:

1. Obtain fresh model/capability/pricing metadata. Reject unknown or nonzero applicable pricing, including request or tool charges, not just token price.
2. Accept only explicitly approved free model IDs or the documented free router. Reject general auto routing and unrecognized model variants.
3. Disable paid web-search plugins, paid parsing, image generation, paid embeddings, and any charged fallback path.
4. Build fallback lists from the same eligible free set; provider errors must never upgrade the user to a paid model.
5. Reserve requests atomically across research, retries, follow-ups, and scheduled work. Track attempted calls, including ambiguous timeout outcomes.
6. Apply bounded context/output size, timeouts, pacing, and a hard per-run attempt cap. Unsupported settings are removed deliberately, not retried indefinitely.
7. Check observed usage/cost afterward. Any unexpected nonzero charge or unknown billing behavior disables that route pending investigation.
8. Fail closed when pricing or privacy compatibility cannot be established. Cached reports and deterministic views remain available.

These are application controls to implement and test. No OpenRouter account was connected during planning, and no specific free model has passed our quality tests yet. Metadata checks reduce risk but do not replace provider billing guarantees; verify with a real free-account smoke test before calling the design validated.

## Call budgets

These counts assume pre-fetched evidence and **one inference per listed turn**, with no LLM tool loops or per-document summarization. Large document corpora require staged indexing/extraction and may need a separate budget.

| Mode | Planned calls | Hard maximum including retries/repairs | Scope |
| --- | --- | --- | --- |
| Data-only | 0 | 0 | Charts, metrics, disclosures, source coverage; no AI conclusion |
| Compact | 6 | 8 | Three grouped analyst calls, bull, bear, final synthesis |
| Full | 16 | 20 | Six specialists, four debate turns, judge, strategy, three risk reviewers, final synthesis |

Compact grouped analysts are (1) company/orders/governance/valuation, (2) news/macro/geopolitics, and (3) technical/context, including bounded community excerpts only when permitted. Full specialists are company, orders/governance, news, macro/geopolitics, community, and technical. If community evidence is absent, skip its call and show the omission. Final rendering and numerical verification cost zero model calls.

Budget reserve policy: with an illustrative 50-call daily allowance, hold back 10 calls for provider ambiguity and interactive follow-ups. The remaining 40 allows at most **five compact runs at their 8-call caps**, or **two full runs at their 20-call caps**, or a mixed allocation. This is arithmetic capacity, not a daily throughput promise. Other apps sharing the account, unavailable models, and provider throttling can reduce it.

The scheduler checks remaining budget immediately before dispatch. When exhausted, checkpoint and show the provider reset time if known; otherwise show that resumption is waiting for quota. Do not repeatedly poll with billable inference calls. An account's quota day may differ from the user's IST calendar day; show both when known.

## Model selection procedure

- Discover current free candidates at setup; do not bake a temporary model name into architecture.
- Test entity fidelity, citation use, Indian units, statement basis, contradiction handling, structured-output validity, and prompt-injection resistance.
- Assign a reliable small model to extraction/interpretation only if it passes the task fixtures; assign the best evaluated eligible model to judge/synthesis.
- Keep explicit model and prompt versions per report. A new free-model route must pass the regression set before becoming default.
- Debate personas on one model are not independent experts. Evaluate whether adding another model improves results before increasing complexity.
- When no eligible model is available, use data-only mode or queue the run. Optional local inference is a later user-selected extension, not a hidden substitute for OpenRouter.

## Operating-cost map

| Component | Baseline | Tradeoff |
| --- | --- | --- |
| Python/LangGraph/FastAPI/Next.js | Local open-source stack | Audit/preserve dependency licenses |
| Database, files, search | Local SQLite/Parquet/full-text | User supplies storage, backups, and machine uptime |
| AI | Eligible OpenRouter free routes | Quotas, availability, variable quality |
| Filings/news | Permitted public sources and imports | Parsing effort, source limits, incomplete coverage |
| Prices | Imports/personal-use prototype adapter | No guaranteed realtime SLA or public redistribution |
| Reddit | Optional approved integration | Access can be unavailable; no substitute scraping promise |
| Broker depth/history | Conditional extension | Entitlement, data terms, and possible fees |
| Hosting | User's machine | No 24/7 service while asleep/offline |
| Scheduled alerts | Local scheduler | Only runs while service is available |

Do not rely on free trials, paid-credit eligibility, multiple accounts to evade quotas, or cloud free tiers that can silently accrue charges. Paid alternatives may be documented later but are outside the requested baseline.

## Caching without misleading reuse

Cache raw retrieval according to source terms. Cache derived metrics by data and formula versions. Cache analyst results by evidence hash, cutoff, horizon, prompt, and model. A changed company filing invalidates dependent results; a new timestamp on an unchanged download does not.

A cached report remains a historical report. Label it with its original date instead of presenting it as a newly researched conclusion. Shared macro context can reduce repeated work, but company-specific exposure interpretation still needs separate evidence.
