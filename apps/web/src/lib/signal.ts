import type { Horizon, Pillar, Signal } from "./types";

export const HORIZONS: Horizon[] = ["1m", "6m", "2y"];

export const HORIZON_LABEL: Record<Horizon, string> = {
  "1m": "1 month",
  "6m": "6 months",
  "2y": "2 years",
};

export const HORIZON_SHORT: Record<Horizon, string> = { "1m": "1M", "6m": "6M", "2y": "2Y" };

export const PILLAR_LABEL: Record<Pillar, string> = {
  technical: "Technical",
  growth_quality: "Growth & quality",
  valuation: "Valuation",
  news: "News & catalysts",
};

export const SIGNAL_LABEL: Record<Signal, string> = {
  strong_bullish: "Strong Bullish",
  bullish: "Bullish",
  neutral: "Neutral",
  bearish: "Bearish",
  strong_bearish: "Strong Bearish",
  insufficient_data: "No signal",
};

/** Score bands, lowest first. Mirrors `SIGNAL_BANDS` in the backend's scoring rules. */
export const BANDS: { from: number; to: number; signal: Signal }[] = [
  { from: 0, to: 29, signal: "strong_bearish" },
  { from: 30, to: 44, signal: "bearish" },
  { from: 45, to: 55, signal: "neutral" },
  { from: 56, to: 70, signal: "bullish" },
  { from: 71, to: 100, signal: "strong_bullish" },
];

/** The band holding the score, tinted with its signal; stronger signals read stronger. */
export const SIGNAL_BAND_TINT: Record<Signal, string> = {
  strong_bullish: "var(--color-bull-solid)",
  bullish: "var(--color-bull-line)",
  neutral: "var(--color-line-strong)",
  bearish: "var(--color-bear-line)",
  strong_bearish: "var(--color-bear-solid)",
  insufficient_data: "var(--color-wash)",
};

export const STATUS_LABEL: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  partial: "Completed with gaps",
  paused_quota: "Paused: daily allowance",
  cancelled: "Cancelled",
  failed: "Failed",
};

export const isActive = (status: string): boolean => status === "queued" || status === "running";
export const isResumable = (status: string): boolean =>
  status === "failed" || status === "cancelled" || status === "paused_quota";
