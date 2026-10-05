"use client";

import { ArrowRight, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { dateOnly, MODE_LABEL, stamp } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { HORIZON_LABEL, HORIZONS } from "@/lib/signal";
import type { Bars, Report, ReportSummary } from "@/lib/types";
import { SignalCells } from "../cells";
import { FollowButton } from "../follow-button";
import { PriceChart } from "../price-chart";
import { ScoreTrack, SignalChip } from "../signal";
import { useShell } from "../shell";
import { Badge, EmptyState, ErrorNotice, PageTitle, Skeleton } from "../ui";

/** The latest report's three signals, as a compact entry point to the full report. */
function Latest({ report }: { report: ReportSummary }) {
  return (
    <section aria-labelledby="latest-title">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="latest-title" className="section-title">
          Latest research
        </h2>
        <Link
          href={`/reports/${encodeURIComponent(report.report_id)}`}
          className="inline-flex items-center gap-1 font-medium text-accent underline-offset-2 hover:underline"
        >
          Open the full report <ArrowRight size={14} aria-hidden />
        </Link>
      </div>
      <p className="meta mt-1">
        As of {dateOnly(report.cutoff)} · {MODE_LABEL[report.mode]} run ·{" "}
        {stamp(report.generated_at)}
        {report.dry_run && (
          <span className="ml-2">
            <Badge tone="bad">Dry run</Badge>
          </span>
        )}
      </p>
      <div className="mt-4 grid divide-line overflow-hidden rounded-lg border border-line md:grid-cols-3 md:divide-x max-md:divide-y">
        {HORIZONS.map((horizon) => {
          const view = report.horizons.find((h) => h.horizon === horizon);
          return (
            <div key={horizon} className="px-5 py-4">
              <p className="font-semibold">{HORIZON_LABEL[horizon]}</p>
              {view ? (
                <>
                  <div className="mt-3 flex items-end justify-between gap-3">
                    <span className="score-figure !text-[2.5rem]">
                      {view.score ?? "—"}
                    </span>
                    <SignalChip signal={view.signal} />
                  </div>
                  <div className="mt-3">
                    <ScoreTrack score={view.score} signal={view.signal} />
                  </div>
                </>
              ) : (
                <p className="meta mt-3">No signal</p>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function CompanyView({ symbol }: { symbol: string }) {
  const router = useRouter();
  const { launchRun } = useShell();
  const reports = useApi<ReportSummary[]>(
    `/v1/reports?symbol=${encodeURIComponent(symbol)}&limit=30`,
  );
  const bars = useApi<Bars>(
    `/v1/instruments/${encodeURIComponent(symbol)}/bars?sessions=250`,
  );
  const latest = reports.data?.[0];
  const latestReport = useApi<Report>(
    latest ? `/v1/reports/${encodeURIComponent(latest.report_id)}` : null,
  );
  const name = bars.data?.name ?? latest?.name;

  if (reports.error && reports.error.code === "offline")
    return <ErrorNotice error={reports.error} what="this company" />;
  // An unknown symbol: the bars endpoint says so with unknown_symbol.
  if (bars.error?.code === "unknown_symbol") {
    return (
      <EmptyState
        title={`“${symbol}” is not an NSE symbol`}
        action={
          <Link href="/" className="btn">
            Back to the watchlist
          </Link>
        }
      >
        Check the spelling, or use search (Ctrl K) to find the company by name.
      </EmptyState>
    );
  }

  return (
    <>
      <PageTitle
        title={name ?? symbol}
        aside={
          <>
            <FollowButton symbol={symbol} />
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => launchRun(symbol)}
            >
              <Sparkles size={15} aria-hidden /> Research
            </button>
          </>
        }
      >
        <span className="badge" data-tone="accent">
          {symbol}
        </span>
        {bars.data && <span className="num text-ink-3">{bars.data.isin}</span>}
      </PageTitle>

      <div className="mt-8 space-y-12">
        {!reports.data ? (
          <Skeleton className="h-40" />
        ) : latest ? (
          <Latest report={latest} />
        ) : (
          <EmptyState
            title="No research for this company yet"
            action={
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => launchRun(symbol)}
              >
                <Sparkles size={15} aria-hidden /> Research {symbol}
              </button>
            }
          >
            A data-only run reads NSE data and gives a code-only scorecard
            without using any model requests.
          </EmptyState>
        )}

        <section aria-labelledby="chart-title" className="panel p-5">
          <h2 id="chart-title" className="section-title mb-2">
            Price
          </h2>
          <PriceChart
            symbol={symbol}
            levels={latestReport.data?.scorecard?.levels?.levels ?? []}
            close={latestReport.data?.scorecard?.levels?.close}
            height={380}
          />
        </section>

        {reports.data && reports.data.length > 0 && (
          <section aria-labelledby="history-title">
            <h2 id="history-title" className="section-title">
              Research history
            </h2>
            <div className="mt-2 overflow-x-auto">
              <table className="tbl min-w-[44rem]">
                <thead>
                  <tr>
                    <th scope="col">Generated</th>
                    <th scope="col">As of</th>
                    <th scope="col">Depth</th>
                    {HORIZONS.map((h) => (
                      <th key={h} scope="col">
                        {HORIZON_LABEL[h]}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {reports.data.map((report) => {
                    const href = `/reports/${encodeURIComponent(report.report_id)}`;
                    return (
                      <tr
                        key={report.report_id}
                        data-link
                        className="cursor-pointer"
                        onClick={() => router.push(href)}
                      >
                        <td className="whitespace-nowrap">
                          <Link
                            href={href}
                            className="font-medium no-underline hover:underline"
                            onClick={(event) => event.stopPropagation()}
                          >
                            {stamp(report.generated_at)}
                          </Link>
                        </td>
                        <td className="whitespace-nowrap text-ink-2">
                          {dateOnly(report.cutoff)}
                        </td>
                        <td className="whitespace-nowrap text-ink-2">
                          {MODE_LABEL[report.mode]}
                          {report.dry_run && (
                            <span className="ml-1.5">
                              <Badge tone="bad">Dry run</Badge>
                            </span>
                          )}
                        </td>
                        <SignalCells summary={report} />
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </>
  );
}
