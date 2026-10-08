# aTrader — Ember

A dark research workspace inspired by [Tickr](https://ambiguous-room-988512.framer.app/)'s crisp market interface and [Trenox](https://trenox.framer.website/)'s warm orange lighting. The audience is an investor reviewing NSE companies at a desktop, often after the market closes. Charcoal surfaces make charts comfortable to read; warm light marks the research entry point.

## Color and materials

The source of truth is apps/web/src/app/globals.css. Colors use semantic OKLCH tokens.

| Role | Treatment |
| --- | --- |
| Canvas | Near-black, lightly cool charcoal |
| Panels | One step lighter, 1px boundary, 12px corners |
| Primary action | Apricot-to-orange gradient with dark text |
| Selection and evidence | Orange text on a dark warm tint |
| Positive prices and bullish signals | Mint, with direction or signal label |
| Negative prices and bearish signals | Coral, with direction or signal label |
| Neutral signals | Graphite and grey |
| Body and metadata | Off-white and readable cool greys |

Concentrate atmospheric gradients in the dashboard introduction and primary controls. Keep charts, reports and tables flat. No gradient text or decorative animation. Full-strength semantic fills use dark text; tinted chips use light text. Never communicate a signal through color alone.

## Typography

Geist Variable is self-hosted and used throughout. Page headings are 2rem, dashboard display text 2.5–3.5rem at explicit breakpoints, section titles 1rem, and normal interface text 0.875rem. Display tracking never goes below -0.04em. Prices and scores use tabular lining figures. Names may truncate in compact watchlist rows, but the full company name remains available on its page.

## Structure

- A horizontal header holds the wordmark, overview, history, company search and research launcher. A secondary bar describes the source, data date and model allowance.
- The overview pairs an introduction/search action with a real company chart. It chooses the first followed company or latest researched company; it never fabricates prices.
- Up to four followed companies are quick selectors for the chart. The complete, searchable watchlist is below, alongside the latest reports.
- The report pairs its takeaway and compact horizon scores with a price chart. A sticky section bar keeps the symbol, report date and links to scores, outlook, risks, sources and full analysis available while reading.
- Reading panels use a lighter charcoal surface without decorative borders. Report prose is 15–16px with comfortable line spacing; numbers keep tabular alignment.
- Summary and risk citations are grouped by statement. The evidence drawer lists readable source names, with evidence IDs retained as secondary labels and the original values, dates, formulas and filing links intact.
- The chart distinguishes the latest stored close from fixed report levels. Level values sit in a legend below the chart, away from the price axis. Moving averages, volume and level toggles live under Indicators.
- Run history filters the latest 50 runs by company, status and depth. Workflow segments represent server-reported stage states, not elapsed-time percentages. Missing historical stage logs are never reconstructed as completed work.
- The research form keeps its header and request allowance footer fixed while its contents scroll. Data-only research remains the default; model options explain request usage and unavailable options provide setup guidance.

## Responsive behavior and accessibility

The navigation wraps below the brand on tablets. The overview becomes one column below 900px; company selectors become two columns. Report columns collapse below 1000px and section links scroll horizontally within their bar. Dense tables scroll within their containers, without pushing the page wider than the viewport. Dialogs have a 90dvh maximum height; the research form scrolls only its body so its action buttons remain visible.

All actions have visible focus states. Search supports Ctrl/Cmd K and keyboard selection. Dialogs retain native focus management and Escape dismissal. Signal chips have text and icons; chart captions name the symbol and last close. Reduced motion disables loading and transition animations.

## Data honesty

Prices are stored daily NSE prices, not live quotes. Preserve source dates, dry-run labels, missing-data states, model-request costs and experimental-scoring explanations. Loading any screen must never launch research or spend the allowance.
