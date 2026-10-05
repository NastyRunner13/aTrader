"use client";

import {
  ArrowUpRight,
  ChartNoAxesCombined,
  History,
  ListChecks,
  Search,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { api, ApiError } from "@/lib/api";
import { dateOnly } from "@/lib/format";
import { useAction, useApi } from "@/lib/hooks";
import type { Instrument, Mode, Status } from "@/lib/types";

type Shell = { openSearch: () => void; launchRun: (symbol?: string) => void };

const ShellContext = createContext<Shell>({
  openSearch: () => {},
  launchRun: () => {},
});
export const useShell = () => useContext(ShellContext);

export function AppShell({ children }: { children: ReactNode }) {
  const [searching, setSearching] = useState(false);
  const [launch, setLaunch] = useState<{ symbol?: string } | null>(null);
  const value = useMemo<Shell>(
    () => ({
      openSearch: () => setSearching(true),
      launchRun: (symbol) => setLaunch({ symbol }),
    }),
    [],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearching(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <ShellContext.Provider value={value}>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-bg focus:px-3 focus:py-2 focus:shadow-pop"
      >
        Skip to content
      </a>
      <div className="app-shell">
        <TopBar />
        <main id="main" className="app-main">
          {children}
        </main>
        <footer className="app-footer">
          <span>
            aTrader <span className="text-ink-3">/ Independent research</span>
          </span>
          <span>Experimental signals. Not investment advice.</span>
        </footer>
      </div>
      <CommandPalette open={searching} onClose={() => setSearching(false)} />
      <RunLauncher request={launch} onClose={() => setLaunch(null)} />
    </ShellContext.Provider>
  );
}

// --- navigation -----------------------------------------------------------------------------

function Wordmark() {
  return (
    <Link href="/" className="wordmark" aria-label="aTrader home">
      <span className="brand-mark" aria-hidden>
        <ChartNoAxesCombined size={22} strokeWidth={2.4} />
      </span>
      aTrader<span className="brand-period">.</span>
    </Link>
  );
}

function NavLinks() {
  const pathname = usePathname();
  const { data: status } = useApi<Status>("/v1/status", {
    refreshInterval: 15000,
  });
  const active = status?.active_runs ?? 0;
  return (
    <nav aria-label="Main" className="main-nav">
      <Link
        href="/"
        className="nav-item"
        aria-current={pathname === "/" ? "page" : undefined}
      >
        <ListChecks size={16} aria-hidden /> Overview
      </Link>
      <Link
        href="/runs"
        className="nav-item"
        aria-current={pathname.startsWith("/runs") ? "page" : undefined}
      >
        <History size={16} aria-hidden /> Research history
        {active > 0 && (
          <span className="ml-auto flex items-center gap-1.5 text-xs text-accent">
            <span className="pulse-dot" aria-hidden /> {active} active
          </span>
        )}
      </Link>
    </nav>
  );
}

function SearchButton({ className = "" }: { className?: string }) {
  const { openSearch } = useShell();
  return (
    <button
      type="button"
      onClick={openSearch}
      className={`search-button ${className}`}
      aria-label="Search companies"
    >
      <Search size={15} aria-hidden />
      <span className="flex-1 text-left">Search companies</span>
      <kbd className="kbd">Ctrl K</kbd>
    </button>
  );
}

function Allowance() {
  const { data, error } = useApi<Status>("/v1/status", {
    refreshInterval: 15000,
  });
  if (error) {
    return (
      <p className="flex items-center gap-2 text-xs text-bad-ink">
        <span className="size-2 rounded-full bg-bad-ink" aria-hidden /> API
        offline
      </p>
    );
  }
  if (!data) return <div className="skeleton h-9" aria-hidden />;
  const { usage } = data;
  const share = usage.usable ? Math.max(0, usage.remaining) / usage.usable : 0;
  return (
    <div className="allowance text-xs text-ink-2">
      <div title="Free-model requests, counted per UTC day">
        <p className="num">
          <span className="font-semibold text-ink">{usage.remaining}</span> of{" "}
          {usage.usable} model requests left today
        </p>
        <div
          className="allowance-track"
          role="img"
          aria-label={`${usage.remaining} of ${usage.usable} requests left`}
        >
          <div
            className="h-full rounded-full"
            style={{
              width: `${share * 100}%`,
              background:
                share < 0.2 ? "var(--color-bear-solid)" : "var(--color-ink-3)",
            }}
          />
        </div>
      </div>
      <p>
        {data.latest_session
          ? `Prices to ${dateOnly(data.latest_session)}`
          : "No price history yet"}
      </p>
    </div>
  );
}

function TopBar() {
  const { launchRun } = useShell();
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Wordmark />
        <NavLinks />
        <div className="topbar-actions">
          <SearchButton />
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => launchRun()}
          >
            New research <ArrowUpRight size={16} aria-hidden />
          </button>
        </div>
      </div>
      <div className="statusbar">
        <span className="flex items-center gap-2">
          <span className="status-dot" />
          NSE equity research
        </span>
        <Allowance />
      </div>
    </header>
  );
}

// --- search palette ---------------------------------------------------------------------------

/** Debounced company search shared by the palette and the run dialog. */
function useCompanySearch(query: string) {
  const [results, setResults] = useState<Instrument[]>([]);
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">(
    "idle",
  );
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const text = query.trim();
    if (!text) {
      setResults([]);
      setState("idle");
      return;
    }
    let stale = false;
    setState("loading");
    const timer = setTimeout(async () => {
      try {
        const found = await api.search(text);
        if (!stale) {
          setResults(found);
          setState("done");
        }
      } catch (caught) {
        if (!stale) {
          setError(
            caught instanceof ApiError ? caught.message : "Search failed.",
          );
          setState("error");
        }
      }
    }, 160);
    return () => {
      stale = true;
      clearTimeout(timer);
    };
  }, [query]);
  return { results, state, error };
}

function ResultList({
  id,
  results,
  cursor,
  onPick,
  onHover,
}: {
  id: string;
  results: Instrument[];
  cursor: number;
  onPick: (item: Instrument) => void;
  onHover: (index: number) => void;
}) {
  return (
    <ul
      id={id}
      role="listbox"
      aria-label="Companies"
      className="max-h-72 overflow-y-auto p-1.5"
    >
      {results.map((item, index) => (
        <li
          key={item.isin}
          id={`${id}-${index}`}
          role="option"
          aria-selected={index === cursor}
          onMouseEnter={() => onHover(index)}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => onPick(item)}
          className={`flex cursor-pointer items-baseline gap-3 rounded-md px-3 py-2 ${index === cursor ? "bg-wash-2" : ""}`}
        >
          <span className="w-28 shrink-0 font-semibold">{item.symbol}</span>
          <span className="min-w-0 flex-1 truncate text-ink-2">
            {item.name}
          </span>
        </li>
      ))}
    </ul>
  );
}

function useDialog(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  const props = {
    ref,
    onClose,
    onClick: (event: React.MouseEvent<HTMLDialogElement>) => {
      if (event.target === ref.current) ref.current?.close(); // a click on the backdrop
    },
  };
  return props;
}

function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const dialog = useDialog(open, onClose);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const { results, state, error } = useCompanySearch(query);

  useEffect(() => {
    if (open) {
      setQuery("");
      setCursor(0);
    }
  }, [open]);
  useEffect(() => setCursor(0), [results]);

  const go = useCallback(
    (item: Instrument | undefined) => {
      if (!item) return;
      dialog.ref.current?.close();
      router.push(`/c/${encodeURIComponent(item.symbol)}`);
    },
    [dialog.ref, router],
  );

  return (
    <dialog {...dialog} className="palette" aria-label="Search companies">
      <div className="flex items-center gap-3 border-b border-line px-4">
        <Search size={16} className="text-ink-3" aria-hidden />
        <input
          autoFocus
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Company name or NSE symbol"
          aria-label="Company name or NSE symbol"
          className="h-12 min-w-0 flex-1 bg-transparent outline-none placeholder:text-ink-3"
          role="combobox"
          aria-expanded={results.length > 0}
          aria-controls="palette-results"
          aria-activedescendant={
            results.length ? `palette-results-${cursor}` : undefined
          }
          aria-autocomplete="list"
          onKeyDown={(event) => {
            if (event.key === "ArrowDown" && results.length) {
              event.preventDefault();
              setCursor((c) => (c + 1) % results.length);
            } else if (event.key === "ArrowUp" && results.length) {
              event.preventDefault();
              setCursor((c) => (c - 1 + results.length) % results.length);
            } else if (event.key === "Enter") {
              event.preventDefault();
              go(results[cursor]);
            }
          }}
        />
        <kbd className="kbd">Esc</kbd>
      </div>
      {results.length > 0 ? (
        <ResultList
          id="palette-results"
          results={results}
          cursor={cursor}
          onPick={go}
          onHover={setCursor}
        />
      ) : (
        <p className="px-5 py-6 text-ink-3" role="status">
          {state === "loading"
            ? "Searching…"
            : state === "done"
              ? "No NSE company matches that."
              : state === "error"
                ? error
                : "Type a company name or symbol, for example “larsen” or LT."}
        </p>
      )}
    </dialog>
  );
}

// --- start a run -------------------------------------------------------------------------------

const MODES: { value: Mode; title: string; cap: number; text: string }[] = [
  {
    value: "data_only",
    title: "Data only",
    cap: 0,
    text: "A code-only scorecard from NSE data. No model is used, so news is not scored. Takes about a minute.",
  },
  {
    value: "compact",
    title: "Compact",
    cap: 8,
    text: "Three analysts, one bull and bear round, and the portfolio manager. 6 model requests, up to 8 with retries.",
  },
  {
    value: "full",
    title: "Full",
    cap: 14,
    text: "Two debate rounds and a three-way risk review. 11 model requests, up to 14 with retries.",
  },
];

function RunLauncher({
  request,
  onClose,
}: {
  request: { symbol?: string } | null;
  onClose: () => void;
}) {
  const router = useRouter();
  const open = request !== null;
  const dialog = useDialog(open, onClose);
  const { data: status } = useApi<Status>(open ? "/v1/status" : null);
  const [symbol, setSymbol] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<Mode>("data_only");
  const [cutoff, setCutoff] = useState("");
  const [dryRun, setDryRun] = useState(false);
  const { results, state } = useCompanySearch(symbol ? "" : query);
  const start = useAction(api.startRun);

  useEffect(() => {
    if (!request) return;
    setSymbol(request.symbol ?? null);
    setQuery("");
    setCutoff("");
    setDryRun(false);
    setMode("data_only");
  }, [request]);

  const blocked = (cap: number): string | null => {
    if (cap === 0 || dryRun || !status) return null;
    if (!status.model.api_key_set) return "Needs OPENROUTER_API_KEY in .env.";
    if (status.usage.remaining < cap)
      return `Needs ${cap} requests; ${status.usage.remaining} left today.`;
    return null;
  };

  // Data only is the default: nothing spends the allowance unless it is chosen. If the chosen
  // depth stops being available (no key, or too few requests left), fall back to it.
  const modeBlocked = blocked(MODES.find((m) => m.value === mode)?.cap ?? 0);
  useEffect(() => {
    if (modeBlocked) setMode("data_only");
  }, [modeBlocked]);

  const today = new Date().toISOString().slice(0, 10);
  const submit = async () => {
    if (!symbol) return;
    const run = await start.run({
      symbol,
      mode,
      cutoff: cutoff || null,
      dry_run: dryRun,
    });
    if (run) {
      dialog.ref.current?.close();
      router.push(`/runs/${run.run_id}`);
    }
  };

  return (
    <dialog {...dialog} className="palette" aria-labelledby="launch-title">
      <form
        method="dialog"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <div className="px-6 pb-2 pt-5">
          <h2 id="launch-title" className="display text-xl">
            Research a company
          </h2>
          <p className="meta mt-1">
            Starting a run never happens on its own. Choose how much of today’s
            model allowance it may use.
          </p>
        </div>

        <div className="space-y-5 px-6 py-4">
          <div>
            <label htmlFor="launch-company" className="font-medium">
              Company
            </label>
            {symbol ? (
              <div className="mt-1.5 flex items-center justify-between rounded-md border border-line bg-wash px-3 py-2">
                <span className="font-semibold">{symbol}</span>
                <button
                  type="button"
                  className="btn btn-quiet btn-sm"
                  onClick={() => setSymbol(null)}
                >
                  Change
                </button>
              </div>
            ) : (
              <div className="mt-1.5">
                <input
                  id="launch-company"
                  className="field"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Name or NSE symbol"
                  autoComplete="off"
                />
                {results.length > 0 ? (
                  <ul className="mt-1 max-h-44 overflow-y-auto rounded-md border border-line p-1">
                    {results.map((item) => (
                      <li key={item.isin}>
                        <button
                          type="button"
                          className="flex w-full items-baseline gap-3 rounded px-2.5 py-1.5 text-left hover:bg-wash-2"
                          onClick={() => setSymbol(item.symbol)}
                        >
                          <span className="w-24 shrink-0 font-semibold">
                            {item.symbol}
                          </span>
                          <span className="min-w-0 truncate text-ink-2">
                            {item.name}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  query.trim() && (
                    <p className="meta mt-1.5">
                      {state === "loading"
                        ? "Searching…"
                        : "No NSE company matches that."}
                    </p>
                  )
                )}
              </div>
            )}
          </div>

          <fieldset>
            <legend className="font-medium">Depth</legend>
            <div className="mt-1.5 space-y-2">
              {MODES.map((m) => {
                const reason = blocked(m.cap);
                return (
                  <label
                    key={m.value}
                    className={`flex gap-3 rounded-md border px-3.5 py-3 ${reason ? "cursor-not-allowed border-line bg-wash text-ink-3" : "cursor-pointer"} ${
                      mode === m.value && !reason
                        ? "border-accent bg-accent-wash"
                        : reason
                          ? ""
                          : "border-line-strong hover:bg-wash"
                    }`}
                  >
                    <input
                      type="radio"
                      name="mode"
                      value={m.value}
                      checked={mode === m.value}
                      disabled={Boolean(reason)}
                      onChange={() => setMode(m.value)}
                      className="mt-1 accent-[var(--color-accent)]"
                    />
                    <span>
                      <span className="block font-semibold">{m.title}</span>
                      <span className="block text-ink-2">{m.text}</span>
                      {reason && (
                        <span className="mt-0.5 block text-warn-ink">
                          {reason}
                        </span>
                      )}
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          <details className="fold">
            <summary className="meta cursor-pointer hover:text-ink">
              Advanced
            </summary>
            <div className="mt-3 space-y-4">
              <div>
                <label htmlFor="launch-cutoff" className="font-medium">
                  Knowledge cutoff
                </label>
                <input
                  id="launch-cutoff"
                  type="date"
                  max={today}
                  value={cutoff}
                  onChange={(e) => setCutoff(e.target.value)}
                  className="field mt-1.5 !w-auto"
                />
                <p className="meta mt-1.5">
                  Use only data public on or before this date. A past-date
                  report is not a clean backtest: a model may remember what came
                  later.
                </p>
              </div>
              <label className="flex items-start gap-2.5">
                <input
                  type="checkbox"
                  checked={dryRun}
                  onChange={(e) => setDryRun(e.target.checked)}
                  className="mt-1 accent-[var(--color-accent)]"
                />
                <span>
                  <span className="block font-medium">Dry run</span>
                  <span className="meta">
                    Placeholder model text and no requests. The report is
                    labelled as a dry run.
                  </span>
                </span>
              </label>
            </div>
          </details>

          {start.error && (
            <p
              role="alert"
              className="rounded-md bg-bad-wash px-3 py-2 text-bad-ink"
            >
              {start.error.message}
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-line px-6 py-4">
          <button
            type="button"
            className="btn"
            onClick={() => dialog.ref.current?.close()}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!symbol || start.pending}
          >
            {start.pending ? "Starting…" : "Start research"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
