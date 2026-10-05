import type { Bars, Instrument, ReportSummary, Run, RunBody, Status, WatchlistItem } from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

/** The API runs beside the web app, on the same host name (localhost or 127.0.0.1). */
export function apiBase(): string {
  const fixed = process.env.NEXT_PUBLIC_API_URL;
  if (fixed) return fixed.replace(/\/$/, "");
  if (typeof window === "undefined") return "http://127.0.0.1:8000";
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

type Detail = { code?: string; message?: string; detail?: unknown };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase()}${path}`, {
      ...init,
      headers: { ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "offline", "The aTrader API is not reachable.");
  }
  if (response.status === 204) return undefined as T;
  const body = (await response.json().catch(() => null)) as (Detail & T) | null;
  if (!response.ok) {
    const fallback = typeof body?.detail === "string" ? body.detail : `Request failed (${response.status})`;
    throw new ApiError(response.status, body?.code ?? "error", body?.message ?? fallback);
  }
  return body as T;
}

export const fetcher = <T>(path: string) => request<T>(path);

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  startRun: (body: RunBody) => request<Run>("/v1/runs", json("POST", body)),
  cancelRun: (id: string) => request<Run>(`/v1/runs/${id}/cancel`, json("POST")),
  resumeRun: (id: string) => request<Run>(`/v1/runs/${id}/resume`, json("POST")),
  follow: (symbol: string) => request<WatchlistItem>(`/v1/watchlist/${encodeURIComponent(symbol)}`, json("PUT")),
  unfollow: (symbol: string) => request<void>(`/v1/watchlist/${encodeURIComponent(symbol)}`, json("DELETE")),
  search: (query: string) => request<Instrument[]>(`/v1/instruments?query=${encodeURIComponent(query)}&limit=8`),
  exportUrl: (reportId: string, format: "card" | "details" | "json") =>
    `${apiBase()}/v1/reports/${encodeURIComponent(reportId)}/export?format=${format}`,
};

export type { Bars, ReportSummary, Status };
