---
name: aTrader
description: A quiet, light research workspace where every score opens to its evidence.
colors:
  surface: "oklch(1 0 0)"
  rail: "oklch(0.975 0.004 275)"
  wash: "oklch(0.962 0.005 275)"
  wash-deep: "oklch(0.945 0.006 275)"
  line: "oklch(0.915 0.006 275)"
  line-strong: "oklch(0.85 0.008 275)"
  ink: "oklch(0.2 0.015 275)"
  ink-secondary: "oklch(0.38 0.015 275)"
  ink-muted: "oklch(0.5 0.014 275)"
  accent: "oklch(0.42 0.17 280)"
  accent-hover: "oklch(0.36 0.17 280)"
  accent-wash: "oklch(0.962 0.022 280)"
  accent-line: "oklch(0.86 0.06 280)"
  bull-solid: "oklch(0.5 0.16 248)"
  bull-ink: "oklch(0.4 0.13 248)"
  bull-wash: "oklch(0.955 0.03 245)"
  bull-line: "oklch(0.86 0.065 245)"
  bear-solid: "oklch(0.78 0.15 75)"
  bear-ink: "oklch(0.42 0.1 62)"
  bear-wash: "oklch(0.965 0.045 85)"
  bear-line: "oklch(0.87 0.09 80)"
  warn-ink: "oklch(0.42 0.1 62)"
  warn-wash: "oklch(0.965 0.045 85)"
  bad-ink: "oklch(0.42 0.16 28)"
  bad-wash: "oklch(0.965 0.025 28)"
typography:
  display:
    fontFamily: "Newsreader Variable, ui-serif, Georgia, serif"
    fontSize: "2rem"
    fontWeight: 420
    lineHeight: 1.125
    letterSpacing: "-0.012em"
  score:
    fontFamily: "Newsreader Variable, ui-serif, Georgia, serif"
    fontSize: "3.25rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "-0.02em"
    fontFeature: "lnum, tnum"
  title:
    fontFamily: "Geist Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.55
  body:
    fontFamily: "Geist Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.25rem
  prose:
    fontFamily: "Geist Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Geist Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.125rem
rounded:
  sm: "4px"
  md: "6px"
  lg: "10px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "48px"
components:
  button:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    height: "32px"
    padding: "0 12px"
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
    height: "32px"
    padding: "0 12px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  signal-chip:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.pill}"
    padding: "3px 8px"
  evidence-chip:
    backgroundColor: "{colors.accent-wash}"
    textColor: "{colors.accent}"
    rounded: "{rounded.sm}"
    padding: "0 6px"
  field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    height: "36px"
    padding: "0 11px"
---

# Design System: aTrader

## 1. Overview

**Creative North Star: "The Research Note"**

aTrader reads like a well-set research note, not a trading terminal. The surface is pure white, the rail beside it is a second, barely-tinted neutral, and the work is done by type, hairlines and whitespace. Density is high where the reader scans (tables, factor lists) and generous where they decide (the three horizon scores). Newsreader gives company names and scores an editorial weight; Geist carries everything else, with tabular figures so numbers align.

The system takes its voice from PRODUCT.md: quiet, precise, candid. It rejects the brokerage look. Nothing suggests urgency: no flashing tickers, no order tickets, no celebratory motion. Uncertainty is stated on the surface (the experimental notice, ranges that say they are not forecasts, levels that say they are not targets) because candour is part of the premium feel.

**Key Characteristics:**
- Light only. Pure white content surface, one cool-tinted rail, hairline borders instead of shadows.
- Two families: Newsreader for names, scores and the summary; Geist for all interface text.
- Restrained colour: one deep indigo accent for action and selection; blue and amber appear only on signals.
- Every claim, score and level opens to its evidence, so evidence chips are a first-class element.
- Tables and rules over cards; a card-like frame appears only around the three-horizon strip.

## 2. Colors

A near-neutral field with one deep accent. Neutrals lean a few degrees toward the accent hue (275) so the page feels of one piece; the surface itself carries no tint.

### Primary
- **Deep Ink Indigo** (`oklch(0.42 0.17 280)`): primary buttons, links, the current tab underline, evidence chips, the run-in-progress marker. Hover darkens to `oklch(0.36 0.17 280)`. A paler `accent-wash` and `accent-line` back chips and selected options.

### Secondary
- **Signal Blue** (`oklch(0.5 0.16 248)`, ink `oklch(0.4 0.13 248)`): bullish signals only. Strong Bullish is a solid fill with white text; Bullish is a tinted chip.
- **Signal Amber** (`oklch(0.78 0.15 75)`, ink `oklch(0.42 0.1 62)`): bearish signals only. Strong Bearish is a solid amber fill with dark text; Bearish is a tinted chip.

### Neutral
- **Surface** (`oklch(1 0 0)`): the page and every panel. Exactly white.
- **Rail** (`oklch(0.975 0.004 275)`): the left rail and the phone header, the one second layer.
- **Wash / Wash Deep** (`oklch(0.962 0.005 275)` / `oklch(0.945 0.006 275)`): row hover, disabled fills, inactive score bands.
- **Line / Line Strong** (`oklch(0.915 0.006 275)` / `oklch(0.85 0.008 275)`): hairlines between rows; control borders.
- **Ink, Ink Secondary, Ink Muted** (`oklch(0.2 …)`, `oklch(0.38 …)`, `oklch(0.5 …)`): headings, body, metadata. Muted is the lightest text allowed (at least 5.1:1 on every surface).

### Named Rules
**The Signal-Only Rule.** Blue and amber belong to signals and the score marks that sit beside them. They are never used for buttons, selection, links or decoration, so a selected tab can never be mistaken for a bullish call.

**The Word-Beside-Colour Rule.** A signal is always a word, a direction mark and a colour, in that order of importance. Colour is never the only cue.

## 3. Typography

**Display Font:** Newsreader Variable (with ui-serif, Georgia, serif)
**Body Font:** Geist Variable (with ui-sans-serif, system-ui, sans-serif)

**Character:** A bookish serif for what the reader remembers (names, scores, the summary) against a precise, neutral sans for everything they operate. Fonts are self-hosted variable files; only the Latin subsets load.

### Hierarchy
- **Display** (420, 2rem, 1.125): page titles, company names.
- **Score** (400, 3.25rem, 1, lining tabular figures): the three horizon scores; smaller (2.5rem) on the company page.
- **Title** (600, 1rem, 1.55): section headings and horizon names.
- **Prose** (400, 1rem, 1.55, max 68ch): the model's summary and long statements.
- **Body** (400, 0.875rem, 1.25rem): tables, lists, controls.
- **Label** (500, 0.8125rem, 1.125rem): metadata, captions, table headers. No all-caps eyebrows.

### Named Rules
**The Tabular Rule.** Any number a reader compares (prices, scores, percentages, points) uses tabular lining figures so columns align.

**The No-Display-In-Chrome Rule.** The serif never appears on buttons, labels, table cells or navigation.

## 4. Elevation

Flat by default. Depth comes from the one tonal step between surface and rail and from hairlines. A shadow appears only on something that floats above the page: the evidence drawer, the search palette, the export menu.

### Shadow Vocabulary
- **Pop** (`box-shadow: 0 1px 2px oklch(0.2 0.02 275 / 0.06), 0 12px 32px -8px oklch(0.2 0.02 275 / 0.2)`): drawers, dialogs and menus only.

### Named Rules
**The Flat-At-Rest Rule.** Panels, rows and chips have no shadow at rest or on hover; hover is a wash fill.

## 5. Components

### Buttons
- **Shape:** gently rounded (6px), 32px tall (44px on touch devices), 14px medium text.
- **Default:** white with a strong hairline; hover fills with Wash.
- **Primary:** Deep Ink Indigo fill, white text; reserved for the single action that starts or confirms something.
- **Quiet:** transparent, for toolbar and row actions. Disabled controls turn to Wash with muted text.

### Signal chips
- **Style:** a pill with a direction mark (chevrons up or down, a dash, a dashed circle for "no signal"), the signal word, and Signal Blue/Amber/neutral tinting. Strong signals are solid fills.
- **Score track:** a 0–100 bar in the five bands (30 / 45 / 56 / 71 boundaries); the band holding the score takes its signal tint and a dark pin marks the score.

### Evidence chips
- **Style:** a small indigo-tinted button holding an ID such as `F3` or `M12`; sits inline after the claim it supports. Activating it opens the evidence drawer.
- **State:** an ID not present in the report is disabled with an explanatory title.

### Tables and rows
- **Style:** 14px, hairline row dividers, a muted 13px header, wash on hover for rows that link. Wide tables scroll inside their own container; long strings wrap anywhere.

### Inputs / Fields
- **Style:** white, 1px strong hairline, 6px radius, 36px tall.
- **Focus:** a 2px indigo outline replaces the border colour. Placeholders meet 4.5:1.

### Navigation
- **Style:** a 240px left rail (Rail neutral) with wordmark, a Ctrl K search field, Watchlist and Runs, and the day's request allowance at the foot. The current page takes a Wash Deep fill. Under 1024px the rail becomes a top bar.

### Evidence drawer and search palette
- **Style:** native `<dialog>` elements: a right-side sheet (34rem) for evidence and a centred palette for search and starting a run, both on a 30% ink backdrop with the Pop shadow.

## 6. Do's and Don'ts

### Do:
- **Do** keep the page white (`oklch(1 0 0)`) and let the rail be the only second neutral.
- **Do** pair every signal colour with its word and direction mark, and keep blue/amber for signals alone.
- **Do** show the limits where the numbers are: "Experimental" under the horizon strip, "not forecasts" on ranges, "not targets" on levels.
- **Do** make anything that spends the model allowance an explicit, priced choice; loading a page never starts a run.
- **Do** use tabular figures for every number a reader compares, and Indian digit grouping with ₹.
- **Do** keep motion to state changes of 120–200 ms with ease-out curves, and honour reduced motion.

### Don't:
- **Don't** make it a brokerage or trading terminal: no order tickets, flashing tickers, urgency or celebratory motion.
- **Don't** use blue or amber for buttons, selection or links, or indigo for a signal.
- **Don't** colour a signal without its word, or rely on colour alone anywhere.
- **Don't** use the serif on buttons, table cells, labels or navigation.
- **Don't** add dark mode, gradients, glass blur, or coloured side-stripe borders on rows and callouts.
- **Don't** wrap content in nested cards; use rules and spacing for grouping.
- **Don't** set body text in a colour lighter than Ink Muted (`oklch(0.5 0.014 275)`).
