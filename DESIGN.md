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
- Company and report screens share the same type and control styles. Horizon scores remain together; report sections and the chart use clearly bounded reading surfaces.
- The evidence drawer, native dialogs, disclosures, exports, horizon tabs and chart controls retain their existing behavior.

## Responsive behavior and accessibility

The navigation wraps below the brand on tablets. The overview becomes one column below 900px; company selectors become two columns. Research history and report columns collapse as space narrows. Dense tables scroll within their containers, without pushing the page wider than the viewport. Dialogs have a 90dvh maximum height and scroll internally.

All actions have visible focus states. Search supports Ctrl/Cmd K and keyboard selection. Dialogs retain native focus management and Escape dismissal. Signal chips have text and icons; chart captions name the symbol and last close. Reduced motion disables loading and transition animations.

## Data honesty

Prices are stored daily NSE prices, not live quotes. Preserve source dates, dry-run labels, missing-data states, model-request costs and experimental-scoring explanations. Loading any screen must never launch research or spend the allowance.
