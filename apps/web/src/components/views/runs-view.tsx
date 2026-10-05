"use client";

import { Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ago, MODE_LABEL } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { isActive } from "@/lib/signal";
import type { Run } from "@/lib/types";
import { RunStatusBadge } from "../cells";
import { useShell } from "../shell";
import { Badge, EmptyState, ErrorNotice, PageTitle, Skeleton } from "../ui";

export function RunsView() {
  const router = useRouter();
  const { launchRun } = useShell();
  const runs = useApi<Run[]>("/v1/runs?limit=50", {
    refreshInterval: (data) =>
      data?.some((run) => isActive(run.status)) ? 3000 : 0,
  });

  return (
    <>
      <PageTitle
        title="Run history"
        aside={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => launchRun()}
          >
            <Sparkles size={15} aria-hidden /> Research
          </button>
        }
      >
        Every research run, newest first. One runs at a time; the rest wait
        their turn.
      </PageTitle>

      <div className="mt-8">
        {runs.error ? (
          <ErrorNotice error={runs.error} what="the runs" />
        ) : !runs.data ? (
          <div className="space-y-2" aria-busy="true" aria-label="Loading runs">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-11" />
            ))}
          </div>
        ) : runs.data.length === 0 ? (
          <EmptyState
            title="No runs yet"
            action={
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => launchRun()}
              >
                Research a company
              </button>
            }
          >
            Research a company to see its run here, with live progress while it
            works.
          </EmptyState>
        ) : (
          <div className="panel overflow-x-auto">
            <table className="tbl min-w-[40rem]">
              <thead>
                <tr>
                  <th scope="col">Company</th>
                  <th scope="col">Depth</th>
                  <th scope="col">Status</th>
                  <th scope="col">Started</th>
                  <th scope="col" className="r">
                    Result
                  </th>
                </tr>
              </thead>
              <tbody>
                {runs.data.map((run) => {
                  const href = `/runs/${run.run_id}`;
                  return (
                    <tr
                      key={run.run_id}
                      data-link
                      className="cursor-pointer"
                      onClick={() => router.push(href)}
                    >
                      <td>
                        <Link
                          href={href}
                          className="font-semibold no-underline hover:underline"
                          onClick={(event) => event.stopPropagation()}
                        >
                          {run.request.symbol}
                        </Link>
                        {run.request.cutoff && (
                          <span className="meta ml-2">
                            cutoff {run.request.cutoff}
                          </span>
                        )}
                      </td>
                      <td className="whitespace-nowrap text-ink-2">
                        {MODE_LABEL[run.request.mode]}
                        {run.dry_run && (
                          <span className="ml-1.5">
                            <Badge tone="bad">Dry run</Badge>
                          </span>
                        )}
                      </td>
                      <td>
                        <RunStatusBadge status={run.status} />
                      </td>
                      <td className="whitespace-nowrap text-ink-2">
                        {ago(run.created_at)}
                      </td>
                      <td className="r whitespace-nowrap">
                        {run.report_id ? (
                          <Link
                            href={`/reports/${encodeURIComponent(run.report_id)}`}
                            className="font-medium text-accent underline-offset-2 hover:underline"
                            onClick={(event) => event.stopPropagation()}
                          >
                            Open report
                          </Link>
                        ) : (
                          <span className="text-ink-3">
                            {run.detail ? "See details" : "—"}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
