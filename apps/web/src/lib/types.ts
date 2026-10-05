import type { components } from "./api-types";

type S = components["schemas"];

export type Status = S["StatusOut"];
export type Usage = S["Usage"];
export type Instrument = S["InstrumentOut"];
export type Run = S["RunOut"];
export type Stage = S["StageOut"];
export type RunBody = S["RunBody"];
export type ReportSummary = S["ReportSummary"];
export type WatchlistItem = S["WatchlistItem"];
export type Bars = S["BarsOut"];

export type Report = S["ResearchReport"];
export type Scorecard = S["Scorecard"];
export type HorizonView = S["HorizonView"];
export type PillarScore = S["PillarScore"];
export type Factor = S["Factor"];
export type Level = S["Level"];
export type PriceLevels = S["PriceLevels"];
export type PriceRange = S["PriceRange"];
export type SignalFlip = S["SignalFlip"];
export type Reason = S["Reason"];
export type Veto = S["Veto"];
export type Claim = S["Claim"];
export type AgentReport = S["AgentReport"];
export type DebateTurn = S["DebateTurn"];
export type RiskReview = S["RiskReview"];
export type ModelCall = S["ModelCall"];
export type EvidencePack = S["EvidencePack"];
export type CoverageEntry = S["CoverageEntry"];

export type Signal = S["Signal"];
export type Horizon = S["Horizon"];
export type Pillar = S["Pillar"];
export type Mode = S["Mode"];
export type RunStatus = S["RunStatus"];
export type Confidence = S["Confidence"];

/** One server-sent run event. `id` counts from 1 within a run; `at` is the server's UTC time. */
export type RunEvent = { id: number; at: string } & (
  | { type: "status"; status: string }
  | { type: "progress"; message: string }
  | { type: "node"; node: string; phase: "start" | "done" | "error" }
  | { type: "end"; status: RunStatus; detail?: string | null; report_id?: string | null }
);
