import type { RunEvent } from "./types";

export const NODE_LABEL: Record<string, string> = {
  data_steward: "NSE data",
  market_analyst: "Market analyst",
  fundamentals_analyst: "Fundamentals analyst",
  news_analyst: "News analyst",
  bull_researcher: "Bull researcher",
  bear_researcher: "Bear researcher",
  aggressive_debator: "Aggressive reviewer",
  conservative_debator: "Conservative reviewer",
  neutral_debator: "Neutral reviewer",
  portfolio_manager: "Portfolio manager",
  finalize: "Scorecard",
};

/** What the data steward reports as it collects, in the words a reader expects. */
const PROGRESS_LABEL: Record<string, string> = {
  prices: "Reading price history",
  sector: "Mapping the sector index",
  "financial results": "Reading financial results",
  announcements: "Reading exchange announcements",
  shareholding: "Reading the shareholding pattern",
  news: "Collecting news headlines",
};

export const nodeLabel = (node: string): string => NODE_LABEL[node] ?? node.replaceAll("_", " ");

export function describeEvent(event: RunEvent): string | null {
  switch (event.type) {
    case "progress":
      return PROGRESS_LABEL[event.message] ?? event.message;
    case "node":
      if (event.node === "debate_round") return null; // an internal join, not work
      return event.phase === "start" ? `${nodeLabel(event.node)} started` : event.phase === "done" ? `${nodeLabel(event.node)} finished` : `${nodeLabel(event.node)} failed`;
    case "status":
      return event.status === "queued"
        ? "Waiting for a turn"
        : event.status === "running"
          ? "Run started"
          : event.status === "cancel_requested"
            ? "Cancel requested: finishing the call in progress"
            : null;
    case "end":
      return event.status === "completed" || event.status === "partial"
        ? "Report ready"
        : event.status === "paused_quota"
          ? "Paused: the daily allowance is used up"
          : event.status === "cancelled"
            ? "Cancelled"
            : "Run failed";
  }
}

export type NodeState = "pending" | "running" | "done" | "error";

/** A node's state from the events seen so far (the stage state from the API covers earlier history). */
export function nodeStates(events: RunEvent[]): Map<string, NodeState> {
  const states = new Map<string, NodeState>();
  for (const event of events) {
    if (event.type !== "node") continue;
    if (event.phase === "start") states.set(event.node, "running");
    else if (event.phase === "done") states.set(event.node, "done");
    else states.set(event.node, "error");
  }
  return states;
}
