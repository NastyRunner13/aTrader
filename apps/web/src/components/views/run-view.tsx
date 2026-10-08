"use client";

import { ArrowRight, Play, Square } from "lucide-react";
import Link from "next/link";
import { elapsed, MODE_LABEL } from "@/lib/format";
import { useAction, useApi, useNow, useRunEvents } from "@/lib/hooks";
import { describeEvent, nodeLabel, nodeStates } from "@/lib/run";
import { isActive, isResumable } from "@/lib/signal";
import type { Run, Stage } from "@/lib/types";
import { api } from "@/lib/api";
import { RunStatusBadge, StageIcon } from "../cells";
import { Badge, EmptyState, ErrorNotice, PageTitle, Skeleton } from "../ui";

const clock = new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit", second: "2-digit", hour12: false });

function Outcome({ run, onResume, resuming }: { run: Run; onResume: () => void; resuming: boolean }) {
  const resume = (
    <button type="button" className="btn btn-primary mt-3" onClick={onResume} disabled={resuming}>
      <Play size={14} aria-hidden /> {resuming ? "Resuming…" : "Resume from where it stopped"}
    </button>
  );
  switch (run.status) {
    case "completed":
    case "partial":
      return run.report_id ? (
        <div className="rounded-lg border border-accent-line bg-accent-wash px-5 py-4">
          <p className="display text-lg">{run.status === "partial" ? "The report is ready, with some gaps." : "The report is ready."}</p>
          <Link href={`/reports/${encodeURIComponent(run.report_id)}`} className="btn btn-primary mt-3 no-underline">
            Open the report <ArrowRight size={14} aria-hidden />
          </Link>
        </div>
      ) : null;
    case "paused_quota":
      return (
        <div role="status" className="rounded-lg border border-line bg-warn-wash px-5 py-4">
          <p className="font-semibold text-warn-ink">Paused: today’s free-model allowance is used up</p>
          <p className="mt-1 text-ink-2">Everything finished so far is saved. Resume once the allowance resets (it counts per UTC day), and no step will be repeated.</p>
          {resume}
        </div>
      );
    case "failed":
      return (
        <div role="alert" className="rounded-lg border border-line bg-bad-wash px-5 py-4">
          <p className="font-semibold text-bad-ink">The run failed</p>
          {run.detail && <p className="mt-1 break-words text-ink-2">{run.detail}</p>}
          {resume}
        </div>
      );
    case "cancelled":
      return (
        <div role="status" className="rounded-lg border border-line bg-wash px-5 py-4">
          <p className="font-semibold">The run was cancelled</p>
          <p className="mt-1 text-ink-2">Steps that finished are saved. You can pick the run up where it stopped.</p>
          {resume}
        </div>
      );
    default:
      return null;
  }
}

function StageRow({ stage, live, progress }: { stage: Stage; live: Map<string, string>; progress: string | null }) {
  const manyNodes = stage.nodes.length > 1;
  const showNodes = manyNodes && stage.state !== "pending" && stage.state !== "skipped";
  return (
    <li data-state={stage.state} className="grid grid-cols-[1.5rem_1fr] gap-3 border-b border-line py-4 last:border-0">
      <span className="pt-0.5">
        <StageIcon state={stage.state} />
      </span>
      <div className="min-w-0">
        <p className={`font-medium ${stage.state === "pending" ? "text-ink-3" : ""}`}>
          {stage.label}
          {stage.state === "skipped" && <span className="meta ml-2 font-normal">Not needed for this run</span>}
        </p>
        {stage.key === "evidence" && stage.state === "running" && progress && <p className="meta mt-0.5">{progress}…</p>}
        {showNodes && (
          <ul className="mt-2 space-y-1">
            {stage.nodes.map((node) => {
              const state = live.get(node) ?? (stage.state === "done" ? "done" : "unknown");
              return (
                <li key={node} className="flex items-center gap-2 text-ink-2">
                  <span className={`size-1.5 rounded-full ${state === "done" ? "bg-accent" : state === "running" ? "pulse-dot !size-1.5" : state === "error" ? "bg-bad-ink" : "bg-line-strong"}`} aria-hidden />
                  {nodeLabel(node)}
                  <span className="meta">{state === "done" ? "finished" : state === "running" ? "working" : state === "error" ? "failed" : "no update recorded"}</span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </li>
  );
}

export function RunView({ id }: { id: string }) {
  const run = useApi<Run>(`/v1/runs/${id}`, { refreshInterval: (data) => (data && isActive(data.status) ? 5000 : 0) });
  const active = run.data ? isActive(run.data.status) : false;
  const events = useRunEvents(id, active, () => void run.mutate());
  const now = useNow(active);
  const cancel = useAction(api.cancelRun);
  const resume = useAction(api.resumeRun);

  if (run.error) {
    return run.error.status === 404 ? (
      <EmptyState title="Run not found" action={<Link href="/runs" className="btn">All runs</Link>}>
        This run is not in the history.
      </EmptyState>
    ) : (
      <ErrorNotice error={run.error} what="the run" />
    );
  }
  if (!run.data) return <Skeleton className="h-64" />;

  const data = run.data;
  const started = new Date(data.created_at).getTime();
  const finished = new Date(data.updated_at).getTime();
  const seconds = ((active ? now : finished) - started) / 1000;
  const live = nodeStates(events);
  const lastProgress = [...events].reverse().find((e) => e.type === "progress");
  const log = events.filter((e) => describeEvent(e) !== null);
  const stages = data.stages.filter((stage) => stage.state !== "skipped");
  const done = stages.filter((stage) => stage.state === "done").length;
  const working = stages.find((stage) => stage.state === "running");

  return (
    <>
      <PageTitle
        title={data.request.symbol}
        aside={
          active && (
            <button
              type="button"
              className="btn"
              disabled={data.cancel_requested || cancel.pending}
              onClick={async () => {
                const updated = await cancel.run(id);
                if (updated) await run.mutate(updated, { revalidate: false });
              }}
            >
              <Square size={13} aria-hidden fill="currentColor" /> {data.cancel_requested ? "Cancelling…" : "Cancel run"}
            </button>
          )
        }
      >
        <RunStatusBadge status={data.status} />
        <span>{MODE_LABEL[data.request.mode]}</span>
        {data.request.cutoff && <span className="text-ink-3">cutoff {data.request.cutoff}</span>}
        {data.dry_run && <Badge tone="bad">Dry run</Badge>}
        {Number.isFinite(seconds) && <span className="num text-ink-3">{elapsed(seconds)} elapsed</span>}
        <Link href={`/c/${encodeURIComponent(data.request.symbol)}`} className="text-accent underline-offset-2 hover:underline">
          View company
        </Link>
      </PageTitle>
      {data.cancel_requested && <p className="meta mt-3">Cancelling stops new steps from starting. A model call already in flight still finishes.</p>}

      <div className="mt-8 grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-6">
          {(cancel.error || resume.error) && (
            <p role="alert" className="rounded-md bg-bad-wash px-3 py-2 text-bad-ink">
              {(cancel.error ?? resume.error)?.message}
            </p>
          )}
          <Outcome
            run={data}
            resuming={resume.pending}
            onResume={async () => {
              const updated = await resume.run(id);
              if (updated) await run.mutate(updated, { revalidate: false });
            }}
          />
          {data.stages.length > 0 ? (
            <section aria-labelledby="stages-title" className="report-surface">
              <div className="run-stage-summary"><h2 id="stages-title" className="section-title">Research workflow</h2><span className="meta num">{done} of {stages.length} stages complete</span></div>
              {working && <p className="text-accent" role="status">Now: {working.label}</p>}
              <div className="run-progress-track" aria-hidden>{stages.map((stage) => <span key={stage.key} data-state={stage.state} />)}</div>
              <p className="meta mt-2">Each segment is a stage; stages can take different amounts of time.</p>
              <ol className="run-stage-list mt-5" aria-live="polite">
                {data.stages.map((stage) => (
                  <StageRow
                    key={stage.key}
                    stage={stage}
                    live={live}
                    progress={lastProgress && lastProgress.type === "progress" ? (describeEvent(lastProgress) ?? null) : null}
                  />
                ))}
              </ol>
            </section>
          ) : (
            !isResumable(data.status) && data.status !== "completed" && <p className="meta">Waiting for the first update…</p>
          )}
        </div>

        <aside aria-labelledby="log-title" className="report-surface self-start">
          <h2 id="log-title" className="section-title">
            Activity
          </h2>
          {log.length === 0 ? (
            <p className="meta mt-2">{active ? "Waiting for activity…" : "The live log is kept only while the server is running."}</p>
          ) : (
            <ol className="mt-2 max-h-[28rem] space-y-2 overflow-y-auto border-t border-line pt-3">
              {[...log].reverse().map((event) => (
                <li key={event.id} className="grid grid-cols-[4.5rem_1fr] gap-2 text-ink-2">
                  <time className="num meta" dateTime={event.at}>
                    {clock.format(new Date(event.at))}
                  </time>
                  <span>{describeEvent(event)}</span>
                </li>
              ))}
            </ol>
          )}
        </aside>
      </div>
    </>
  );
}
