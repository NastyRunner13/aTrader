"use client";

import { Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
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
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [depth, setDepth] = useState("all");
  const runs = useApi<Run[]>("/v1/runs?limit=50", {
    refreshInterval: (data) =>
      data?.some((run) => isActive(run.status)) ? 3000 : 0,
  });
  const filtered = runs.data?.filter((run) =>
    run.request.symbol.toLowerCase().includes(query.trim().toLowerCase()) &&
    (status === "all" || (status === "active" ? isActive(run.status) : run.status === status)) &&
    (depth === "all" || run.request.mode === depth),
  ) ?? [];

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
        Your latest 50 runs, newest first. Track progress and revisit the results.
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
          <>
          <div className="run-filters">
            <label><span className="meta">Company</span><input type="search" className="field" placeholder="Filter by symbol…" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
            <label><span className="meta">Status</span><select className="field" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="all">All statuses</option><option value="active">Active</option><option value="completed">Completed</option><option value="partial">Partial</option><option value="paused_quota">Paused</option><option value="failed">Failed</option><option value="cancelled">Cancelled</option>
            </select></label>
            <label><span className="meta">Depth</span><select className="field" value={depth} onChange={(event) => setDepth(event.target.value)}>
              <option value="all">All depths</option>{Object.entries(MODE_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select></label>
            <p className="meta py-2" role="status">{filtered.length} of {runs.data.length} runs</p>
            {(query || status !== "all" || depth !== "all") && <button type="button" className="btn btn-quiet" onClick={() => { setQuery(""); setStatus("all"); setDepth("all"); }}>Clear filters</button>}
          </div>
          {filtered.length === 0 ? <EmptyState title="No runs match these filters">Try another company, status or research depth.</EmptyState> : <div className="panel overflow-x-auto">
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
                {filtered.map((run) => {
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
                        {isActive(run.status) && <p className="meta mt-1">{run.stages.find((stage) => stage.state === "running")?.label ?? "Waiting to start"}</p>}
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
          </div>}
          </>
        )}
      </div>
    </>
  );
}
