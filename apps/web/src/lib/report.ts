import { fromClose, rupees, rupeesWhole } from "./format";
import { SIGNAL_LABEL } from "./signal";
import type { Factor, HorizonView, Level, PillarScore, PriceRange, Reason, Report, Scorecard, SignalFlip } from "./types";

export const EXPERIMENTAL =
  "Experimental: the scoring rules and weights have not yet been validated against history. Research, not investment advice.";
export const LEVELS_NOTE =
  "Levels are prices the stock turned from or traded heavily at before. They are not entry, stop or target prices.";
export const FLIP_NOTE =
  "The next session’s close at which a horizon’s signal would change, at average volume with every other input unchanged. Computed in code.";
export const NO_SUPPORT = "No support zone below the last close: no swing low of the past year sits under today’s price.";

export const KIND_LABEL: Record<Level["kind"], string> = {
  resistance: "Resistance",
  support: "Support",
  average: "Moving average",
  vwap: "Anchored VWAP",
  volume: "Heaviest-traded band",
  range: "Range",
};

/** A price range as a short headline and what it means. Neither is a forecast. */
export function rangeText(range: PriceRange | null | undefined): { headline: string; caption: string } | null {
  if (!range) return null;
  if (range.method === "scenario" && range.base != null) {
    return {
      headline: `${rupeesWhole(range.low)} · ${rupeesWhole(range.base)} · ${rupeesWhole(range.high)}`,
      caption: "Bear · base · bull scenario (EPS × P/E)",
    };
  }
  return {
    headline: `${rupeesWhole(range.low)} – ${rupeesWhole(range.high)}`,
    caption: "Typical move, ±1 standard deviation",
  };
}

export function flipText(flip: SignalFlip, close: number): string {
  const up = flip.direction === "up";
  if (flip.price == null || flip.signal == null) {
    return `No change ${up ? "up to +" : "down to −"}${flip.searched_pct.toFixed(0)}%`;
  }
  return `${SIGNAL_LABEL[flip.signal]} ${up ? "above" : "below"} ${rupees(flip.price)} (${fromClose(flip.price, close)})`;
}

/** The two rules that moved a pillar most, for the one-line reasons under its name. */
export function mainReasons(pillar: PillarScore): string[] {
  return [...pillar.factors]
    .filter((f) => f.kind === "rule" && f.points !== 0)
    .sort((a, b) => Math.abs(b.points) - Math.abs(a.points))
    .slice(0, 2)
    .map((f) => `${f.label} (${f.points > 0 ? "+" : "−"}${Math.abs(f.points).toFixed(0)})`);
}

/**
 * The portfolio manager’s pros and cons, or, without one (a data-only run, or a failed
 * synthesis), the rules that moved the scores most — the same fallback the saved card uses.
 */
export function prosAndCons(report: Report): { pros: Reason[]; cons: Reason[]; fromRules: boolean } {
  const synthesis = report.final_synthesis;
  if (synthesis && synthesis.status === "completed" && (synthesis.pros.length || synthesis.cons.length)) {
    return { pros: synthesis.pros, cons: synthesis.cons, fromRules: false };
  }
  const factors: Factor[] = (report.scorecard?.pillars ?? []).flatMap((p) => p.factors).filter((f) => f.kind === "rule" && f.points !== 0);
  const ranked = [...factors].sort((a, b) => Math.abs(b.points) - Math.abs(a.points));
  const pick = (positive: boolean): Reason[] =>
    ranked
      .filter((f) => f.points > 0 === positive)
      .slice(0, 3)
      .map((f) => ({ statement: f.label, evidence_ids: f.evidence_ids ?? [] }));
  return { pros: pick(true), cons: pick(false), fromRules: true };
}

export const horizonView = (card: Scorecard, horizon: HorizonView["horizon"]): HorizonView | undefined =>
  card.horizons.find((h) => h.horizon === horizon);

export const weightLabel = (card: Scorecard, pillar: PillarScore["pillar"]): string =>
  card.horizons.map((h) => h.weights[pillar] ?? 0).join(" / ");

/** Where a close sits among the levels, to place the "last close" row between them. */
export function withClose(levels: Level[], close: number): ({ close: true } | { close: false; level: Level })[] {
  const rows: ({ close: true } | { close: false; level: Level })[] = [];
  let placed = false;
  for (const level of levels) {
    if (!placed && level.price < close) {
      rows.push({ close: true });
      placed = true;
    }
    rows.push({ close: false, level });
  }
  if (!placed) rows.push({ close: true });
  return rows;
}
