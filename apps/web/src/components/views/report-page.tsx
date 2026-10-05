"use client";

import Link from "next/link";
import { useApi } from "@/lib/hooks";
import type { Report, ReportSummary } from "@/lib/types";
import { ReportView } from "../report/report-view";
import { EmptyState, ErrorNotice, Skeleton } from "../ui";

function ReportSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading the report" className="space-y-8">
      <Skeleton className="h-10 w-2/3" />
      <Skeleton className="h-56" />
      <div className="grid gap-12 xl:grid-cols-[minmax(0,1fr)_30rem]">
        <Skeleton className="h-96" />
        <Skeleton className="h-96" />
      </div>
    </div>
  );
}

export function ReportPage({ id }: { id: string }) {
  const report = useApi<Report>(`/v1/reports/${encodeURIComponent(id)}`);
  const symbol = report.data?.pack?.listing.symbol ?? report.data?.request.symbol;
  const history = useApi<ReportSummary[]>(symbol ? `/v1/reports?symbol=${encodeURIComponent(symbol)}&limit=30` : null);

  if (report.error) {
    if (report.error.status === 404) {
      return (
        <EmptyState title="Report not found" action={<Link href="/" className="btn">Back to the watchlist</Link>}>
          This report is not in the archive. It may have been moved or deleted from the reports folder.
        </EmptyState>
      );
    }
    return <ErrorNotice error={report.error} what="the report" />;
  }
  if (!report.data) return <ReportSkeleton />;

  const summaries = history.data ?? [];
  const dryRun = summaries.find((s) => s.report_id === id)?.dry_run ?? false;
  return <ReportView report={report.data} dryRun={dryRun} history={summaries} />;
}
