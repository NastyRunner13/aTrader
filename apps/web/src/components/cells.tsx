import { CircleCheck, CircleDashed, CircleMinus, CircleX, Loader } from "lucide-react";
import { HORIZONS } from "@/lib/signal";
import { STATUS_LABEL } from "@/lib/signal";
import type { ReportSummary, Run } from "@/lib/types";
import { SignalChip } from "./signal";
import { Badge } from "./ui";

/** The three horizon signals of a report as table cells, in horizon order. */
export function SignalCells({ summary }: { summary: ReportSummary | null | undefined }) {
  return (
    <>
      {HORIZONS.map((horizon) => {
        const view = summary?.horizons.find((h) => h.horizon === horizon);
        return (
          <td key={horizon}>
            {view ? (
              <span className="flex items-center gap-2">
                <SignalChip signal={view.signal} />
                {view.score != null && <span className="num text-ink-2">{view.score}</span>}
              </span>
            ) : (
              <span className="text-ink-3">—</span>
            )}
          </td>
        );
      })}
    </>
  );
}

export function RunStatusBadge({ status }: { status: Run["status"] }) {
  switch (status) {
    case "running":
      return (
        <span className="badge" data-tone="accent">
          <span className="pulse-dot !size-1.5" aria-hidden /> {STATUS_LABEL[status]}
        </span>
      );
    case "queued":
      return <Badge>{STATUS_LABEL[status]}</Badge>;
    case "completed":
      return <Badge>{STATUS_LABEL[status]}</Badge>;
    case "partial":
    case "paused_quota":
      return <Badge tone="warn">{STATUS_LABEL[status]}</Badge>;
    case "failed":
      return <Badge tone="bad">{STATUS_LABEL[status]}</Badge>;
    default:
      return <Badge>{STATUS_LABEL[status] ?? status}</Badge>;
  }
}

export function StageIcon({ state }: { state: string }) {
  const common = { size: 18, "aria-hidden": true } as const;
  switch (state) {
    case "done":
      return <CircleCheck {...common} className="text-accent" />;
    case "running":
    case "partial":
      return <Loader {...common} className="animate-spin text-accent [animation-duration:1.6s]" />;
    case "error":
      return <CircleX {...common} className="text-bad-ink" />;
    case "skipped":
      return <CircleMinus {...common} className="text-ink-3" />;
    default:
      return <CircleDashed {...common} className="text-ink-3" />;
  }
}
