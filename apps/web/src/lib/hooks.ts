"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import useSWR, { type SWRConfiguration } from "swr";
import { type ApiError, apiBase, fetcher } from "./api";
import type { RunEvent } from "./types";

/** Read an API path. Pass null to wait (for example until an ID is known). */
export function useApi<T>(path: string | null, config?: SWRConfiguration<T, ApiError>) {
  return useSWR<T, ApiError>(path, (key: string) => fetcher<T>(key), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
    ...config,
  });
}

/**
 * Follow a run's server-sent events while it is active. Each event also calls
 * `onChange`, so the page can refresh the run's snapshot. The stream closes itself on
 * the `end` event; resuming a run (active again) opens a new one from the last event seen.
 */
export function useRunEvents(runId: string, active: boolean, onChange: () => void) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const lastId = useRef(0);
  const notify = useRef(onChange);
  notify.current = onChange;

  useEffect(() => {
    lastId.current = 0;
    setEvents([]);
  }, [runId]);

  useEffect(() => {
    if (!active) return;
    const source = new EventSource(`${apiBase()}/v1/runs/${runId}/events?after=${lastId.current}`);
    const handle = (message: MessageEvent<string>) => {
      const event = JSON.parse(message.data) as RunEvent;
      if (event.id <= lastId.current) return;
      lastId.current = event.id;
      setEvents((previous) => [...previous, event]);
      notify.current();
      if (event.type === "end") source.close();
    };
    for (const kind of ["status", "progress", "node", "end"]) source.addEventListener(kind, handle);
    return () => source.close();
  }, [runId, active]);

  return events;
}

/** The current time, re-read every `ms` while `enabled`. */
export function useNow(enabled: boolean, ms = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!enabled) return;
    const timer = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(timer);
  }, [enabled, ms]);
  return now;
}

/** Run an async action and track whether it is pending and what went wrong. */
export function useAction<A extends unknown[], R>(action: (...args: A) => Promise<R>) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const run = useCallback(
    async (...args: A): Promise<R | undefined> => {
      setPending(true);
      setError(null);
      try {
        return await action(...args);
      } catch (caught) {
        setError(caught instanceof Error ? caught : new Error(String(caught)));
        return undefined;
      } finally {
        setPending(false);
      }
    },
    [action],
  );
  return { run, pending, error };
}
