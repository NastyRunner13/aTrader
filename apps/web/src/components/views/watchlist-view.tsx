"use client";

import {
  ArrowDownRight,
  ArrowUpRight,
  ArrowRight,
  ChartNoAxesCombined,
  Clock3,
  Plus,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSWRConfig } from "swr";
import { api } from "@/lib/api";
import { rupees, signedPct, dateOnly, stamp, MODE_LABEL } from "@/lib/format";
import { useAction, useApi } from "@/lib/hooks";
import { HORIZON_SHORT, HORIZONS } from "@/lib/signal";
import type { Bars, WatchlistItem, ReportSummary } from "@/lib/types";
import { SignalCells } from "../cells";
import { useShell } from "../shell";
import { PriceChart } from "../price-chart";
import { Badge, EmptyState, ErrorNotice, Skeleton } from "../ui";

function Change({ value }: { value: number | null | undefined }) {
  if (value == null) return null;
  return (
    <span
      className={`num ml-2 ${value > 0 ? "text-bull-ink" : value < 0 ? "text-bear-ink" : "text-ink-3"}`}
    >
      {signedPct(value, 2)}
    </span>
  );
}

function SignalHeads() {
  return (
    <>
      {HORIZONS.map((h) => (
        <th key={h} scope="col">
          {HORIZON_SHORT[h]}
        </th>
      ))}
    </>
  );
}

function WatchRow({ item }: { item: WatchlistItem }) {
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const remove = useAction(async () => {
    await api.unfollow(item.symbol);
    await mutate("/v1/watchlist");
  });
  const report = item.latest_report;
  const href = report
    ? `/reports/${encodeURIComponent(report.report_id)}`
    : `/c/${encodeURIComponent(item.symbol)}`;
  return (
    <tr data-link className="cursor-pointer" onClick={() => router.push(href)}>
      <td>
        <div className="flex items-center gap-3">
          <span className="company-avatar" aria-hidden>
            {item.symbol.slice(0, 2)}
          </span>
          <div>
            <Link
              href={href}
              className="font-semibold no-underline hover:underline"
              onClick={(event) => event.stopPropagation()}
            >
              {item.symbol}
            </Link>
            <p className="meta max-w-[12rem] truncate">{item.name}</p>
          </div>
        </div>
      </td>
      <td className="num whitespace-nowrap">
        {item.quote ? (
          <>
            {rupees(item.quote.close)}
            <Change value={item.quote.change_pct} />
          </>
        ) : (
          <span className="text-ink-3">No prices</span>
        )}
      </td>
      <SignalCells summary={report} />
      <td className="whitespace-nowrap text-ink-2">
        {report ? (
          <>
            {dateOnly(report.cutoff)}
            {report.dry_run && (
              <span className="ml-1.5">
                <Badge tone="bad">Dry run</Badge>
              </span>
            )}
          </>
        ) : (
          <span className="text-ink-3">Not researched</span>
        )}
      </td>
      <td className="r">
        <button
          type="button"
          className="btn btn-quiet btn-icon btn-sm"
          aria-label={`Remove ${item.symbol} from the watchlist`}
          disabled={remove.pending}
          onClick={(event) => {
            event.stopPropagation();
            void remove.run();
          }}
        >
          <X size={15} aria-hidden />
        </button>
      </td>
    </tr>
  );
}

function MarketFocus({ symbol }: { symbol: string }) {
  const { data } = useApi<Bars>(
    `/v1/instruments/${encodeURIComponent(symbol)}/bars?sessions=126`,
  );
  const last = data?.bars.at(-1);
  const previous = data?.bars.at(-2);
  const change =
    last && previous && previous.close !== 0
      ? (last.close / previous.close - 1) * 100
      : null;
  return (
    <section className="market-focus" aria-label={`${symbol} price overview`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="company-avatar large" aria-hidden>
            {symbol.slice(0, 2)}
          </span>
          <div>
            <Link
              href={`/c/${encodeURIComponent(symbol)}`}
              className="focus-symbol"
            >
              {symbol} <ArrowUpRight size={16} aria-hidden />
            </Link>
            <p className="meta mt-1">{data?.name ?? "NSE-listed equity"}</p>
          </div>
        </div>
        <Badge>Daily prices · NSE</Badge>
      </div>
      <div className="focus-quote">
        <span className="num">{last ? rupees(last.close) : "—"}</span>
        <span className="text-xs text-ink-3">INR</span>
        <Change value={change} />
      </div>
      <PriceChart
        key={symbol}
        symbol={symbol}
        initialSessions={126}
        height={245}
        compact
      />
      <div className="focus-foot">
        <span>Stored NSE prices</span>
        <span>
          {last
            ? `Last session ${dateOnly(last.session)}`
            : "Waiting for price history"}
        </span>
      </div>
    </section>
  );
}

export function WatchlistView() {
  const { openSearch, launchRun } = useShell();
  const watch = useApi<WatchlistItem[]>("/v1/watchlist");
  const recent = useApi<ReportSummary[]>("/v1/reports?limit=8");
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const featured =
    selected ?? watch.data?.[0]?.symbol ?? recent.data?.[0]?.symbol;
  const filtered = watch.data?.filter((item) =>
    `${item.symbol} ${item.name}`.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <>
      <div className="overview-heading">
        <span>Your research workspace</span>
        <span className="meta">Indian equities. A clearer perspective.</span>
      </div>
      <div className="overview-hero">
        <section className="research-intro">
          <span className="research-label">
            <ShieldCheck size={14} aria-hidden /> Evidence behind every signal
          </span>
          <h1>
            Find the signal.
            <br />
            <span>Know the why.</span>
          </h1>
          <p>
            Your companies, their signals, and the evidence that connects them.
            Research Indian equities with a longer view.
          </p>
          <button type="button" className="hero-search" onClick={openSearch}>
            <Search size={18} aria-hidden />
            <span>Find an NSE company</span>
            <span className="search-arrow">
              <ArrowRight size={18} aria-hidden />
            </span>
          </button>
          <div className="intro-foot">
            <span>1 month</span>
            <i />
            <span>6 months</span>
            <i />
            <span>2 years</span>
          </div>
        </section>
        {featured ? (
          <MarketFocus symbol={featured} />
        ) : watch.error ? (
          <div className="market-focus flex items-center">
            <ErrorNotice error={watch.error} what="market data" />
          </div>
        ) : !watch.data ? (
          <Skeleton className="min-h-80" />
        ) : (
          <section className="market-focus focus-empty">
            <ChartNoAxesCombined size={38} aria-hidden />
            <h2 className="section-title">Your next idea starts here.</h2>
            <p className="meta max-w-80">
              Find a company to explore its price history, then start a research
              run to uncover its signals.
            </p>
            <button className="btn btn-primary" onClick={openSearch}>
              Explore companies <ArrowUpRight size={16} aria-hidden />
            </button>
          </section>
        )}
      </div>
      {Boolean(watch.data?.length) && (
        <section className="quote-strip" aria-label="Quick company selection">
          {watch.data!.slice(0, 4).map((item) => (
            <button
              type="button"
              key={item.symbol}
              className="quote-item"
              aria-pressed={featured === item.symbol}
              onClick={() => setSelected(item.symbol)}
            >
              <span className="quote-company">
                {item.symbol}
                <span className="meta truncate">{item.name}</span>
              </span>
              <span className="quote-price num">
                {item.quote ? rupees(item.quote.close) : "No prices"}
                <span
                  className={`quote-change ${item.quote?.change_pct != null && item.quote.change_pct < 0 ? "text-bear-ink" : "text-bull-ink"}`}
                >
                  {item.quote?.change_pct != null ? (
                    <>
                      {item.quote.change_pct < 0 ? (
                        <ArrowDownRight size={13} aria-hidden />
                      ) : (
                        <ArrowUpRight size={13} aria-hidden />
                      )}
                      {signedPct(item.quote.change_pct, 2)}
                    </>
                  ) : (
                    "—"
                  )}
                </span>
              </span>
            </button>
          ))}
        </section>
      )}
      <div className="overview-bottom">
        <section
          className="panel watchlist-panel"
          aria-labelledby="watchlist-title"
        >
          <div className="panel-heading">
            <div>
              <h2 id="watchlist-title" className="section-title">
                Your watchlist{" "}
                <span className="count-badge">{watch.data?.length ?? "—"}</span>
              </h2>
              <p className="meta mt-1">
                A longer view of the companies you follow.
              </p>
            </div>
            <button type="button" className="btn btn-sm" onClick={openSearch}>
              <Plus size={14} aria-hidden /> Add company
            </button>
          </div>
          {Boolean(watch.data?.length) && (
            <div className="watchlist-toolbar">
              <label className="filter-field">
                <Search size={15} aria-hidden />
                <input
                  aria-label="Filter watchlist"
                  value={filter}
                  onChange={(event) => setFilter(event.target.value)}
                  placeholder="Filter companies…"
                />
              </label>
              <span className="meta">Signals by horizon</span>
            </div>
          )}
          {watch.error ? (
            <ErrorNotice error={watch.error} what="the watchlist" />
          ) : !watch.data ? (
            <div
              className="space-y-2"
              aria-busy="true"
              aria-label="Loading the watchlist"
            >
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-12" />
              ))}
            </div>
          ) : watch.data.length === 0 ? (
            <EmptyState
              title="Nothing followed yet"
              action={
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={openSearch}
                >
                  Find a company
                </button>
              }
            >
              Search for an NSE company, open it, and choose Follow. Its latest
              signals will appear here, and loading this page never starts a
              research run.
            </EmptyState>
          ) : (
            <div aria-label="Followed companies">
              {/* relative: so the hidden "Remove" column label is clipped with the table */}
              <div className="relative overflow-x-auto">
                <table className="tbl min-w-[44rem]">
                  <thead>
                    <tr>
                      <th scope="col">Company</th>
                      <th scope="col">Last close</th>
                      <SignalHeads />
                      <th scope="col">Researched</th>
                      <th scope="col">
                        <span className="sr-only">Remove</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered?.map((item) => (
                      <WatchRow key={item.symbol} item={item} />
                    ))}
                  </tbody>
                </table>
              </div>
              {filtered?.length === 0 && (
                <p role="status" className="px-6 py-10 text-center text-ink-3">
                  No companies match “{filter}”.
                </p>
              )}
            </div>
          )}
          <div className="panel-foot">
            <ShieldCheck size={13} aria-hidden />
            <span>
              Experimental scores · Open a company to see the evidence.
            </span>
          </div>
        </section>
        <section className="panel recent-panel" aria-labelledby="recent-title">
          <div className="panel-heading">
            <h2 id="recent-title" className="section-title">
              Recent research
            </h2>
            <Clock3 size={17} className="text-ink-3" aria-hidden />
          </div>
          {recent.error ? (
            <ErrorNotice error={recent.error} what="recent research" />
          ) : !recent.data ? (
            <Skeleton className="m-5 h-36" />
          ) : recent.data.length ? (
            <div className="research-list">
              {recent.data.slice(0, 5).map((report) => (
                <Link
                  key={report.report_id}
                  href={`/reports/${encodeURIComponent(report.report_id)}`}
                  className="research-item"
                >
                  <span className="research-item-icon">
                    <ChartNoAxesCombined size={17} aria-hidden />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2 font-semibold">
                      {report.symbol}
                      {report.dry_run && <Badge tone="bad">Dry run</Badge>}
                    </span>
                    <span className="meta mt-1 block">
                      {MODE_LABEL[report.mode]} · {stamp(report.generated_at)}
                    </span>
                  </span>
                  <ArrowUpRight size={16} aria-hidden className="text-ink-3" />
                </Link>
              ))}
            </div>
          ) : (
            <div className="p-5">
              <p className="text-ink-2">Build your research library.</p>
              <p className="meta mt-2">
                Start with a data-only run. No model requests needed.
              </p>
              <button
                type="button"
                className="btn mt-4"
                onClick={() => launchRun()}
              >
                Start research <ArrowRight size={14} aria-hidden />
              </button>
            </div>
          )}
          <Link
            href="/runs"
            className="panel-foot justify-between hover:text-accent"
          >
            View research history <ArrowRight size={14} aria-hidden />
          </Link>
        </section>
      </div>
    </>
  );
}
