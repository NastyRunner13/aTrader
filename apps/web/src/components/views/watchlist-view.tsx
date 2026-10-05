"use client";

import { Plus, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSWRConfig } from "swr";
import { api } from "@/lib/api";
import { rupees, signedPct, stamp, dateOnly, MODE_LABEL } from "@/lib/format";
import { useAction, useApi } from "@/lib/hooks";
import { HORIZON_SHORT, HORIZONS } from "@/lib/signal";
import type { ReportSummary, WatchlistItem } from "@/lib/types";
import { SignalCells } from "../cells";
import { useShell } from "../shell";
import { Badge, EmptyState, ErrorNotice, PageTitle, Skeleton } from "../ui";

function Change({ value }: { value: number | null | undefined }) {
  if (value == null) return null;
  return (
    <span className={`num ml-2 ${value > 0 ? "text-bull-ink" : value < 0 ? "text-bear-ink" : "text-ink-3"}`}>{signedPct(value, 2)}</span>
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
  const href = report ? `/reports/${encodeURIComponent(report.report_id)}` : `/c/${encodeURIComponent(item.symbol)}`;
  return (
    <tr data-link className="cursor-pointer" onClick={() => router.push(href)}>
      <td>
        <Link href={href} className="font-semibold no-underline hover:underline" onClick={(event) => event.stopPropagation()}>
          {item.symbol}
        </Link>
        <p className="meta max-w-[18rem] truncate">{item.name}</p>
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
            {report.dry_run && <span className="ml-1.5"><Badge tone="bad">Dry run</Badge></span>}
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

function RecentRow({ report }: { report: ReportSummary }) {
  const router = useRouter();
  const href = `/reports/${encodeURIComponent(report.report_id)}`;
  return (
    <tr data-link className="cursor-pointer" onClick={() => router.push(href)}>
      <td>
        <Link href={href} className="font-semibold no-underline hover:underline" onClick={(event) => event.stopPropagation()}>
          {report.symbol}
        </Link>
        <p className="meta max-w-[18rem] truncate">{report.name}</p>
      </td>
      <SignalCells summary={report} />
      <td className="whitespace-nowrap text-ink-2">
        {MODE_LABEL[report.mode]}
        {report.dry_run && <span className="ml-1.5"><Badge tone="bad">Dry run</Badge></span>}
      </td>
      <td className="whitespace-nowrap text-ink-2">{stamp(report.generated_at)}</td>
    </tr>
  );
}

export function WatchlistView() {
  const { openSearch, launchRun } = useShell();
  const watch = useApi<WatchlistItem[]>("/v1/watchlist");
  const recent = useApi<ReportSummary[]>("/v1/reports?limit=8");

  return (
    <>
      <PageTitle
        title="Watchlist"
        aside={
          <>
            <button type="button" className="btn" onClick={openSearch}>
              <Plus size={15} aria-hidden /> Add company
            </button>
            <button type="button" className="btn btn-primary" onClick={() => launchRun()}>
              <Sparkles size={15} aria-hidden /> Research
            </button>
          </>
        }
      >
        Companies you follow, with the latest signal for each horizon.
      </PageTitle>

      <div className="mt-8 space-y-12">
        {watch.error ? (
          <ErrorNotice error={watch.error} what="the watchlist" />
        ) : !watch.data ? (
          <div className="space-y-2" aria-busy="true" aria-label="Loading the watchlist">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : watch.data.length === 0 ? (
          <EmptyState
            title="Nothing followed yet"
            action={
              <button type="button" className="btn btn-primary" onClick={openSearch}>
                Find a company
              </button>
            }
          >
            Search for an NSE company, open it, and choose Follow. Its latest signals will appear here, and loading this page never starts a research run.
          </EmptyState>
        ) : (
          <section aria-label="Followed companies">
            <div className="overflow-x-auto">
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
                  {watch.data.map((item) => (
                    <WatchRow key={item.symbol} item={item} />
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {recent.data && recent.data.length > 0 && (
          <section aria-labelledby="recent-title">
            <h2 id="recent-title" className="section-title">
              Recent research
            </h2>
            <div className="mt-2 overflow-x-auto">
              <table className="tbl min-w-[44rem]">
                <thead>
                  <tr>
                    <th scope="col">Company</th>
                    <SignalHeads />
                    <th scope="col">Depth</th>
                    <th scope="col">Generated</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.data.map((report) => (
                    <RecentRow key={report.report_id} report={report} />
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3">
              <Link href="/runs" className="text-accent underline-offset-2 hover:underline">
                All runs
              </Link>
            </p>
          </section>
        )}
      </div>
    </>
  );
}
