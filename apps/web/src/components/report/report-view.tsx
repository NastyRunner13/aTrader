"use client";

import { ChevronDown, Download, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { dateOnly, MODE_LABEL, stamp } from "@/lib/format";
import { EXPERIMENTAL } from "@/lib/report";
import { STATUS_LABEL } from "@/lib/signal";
import type { Report, ReportSummary } from "@/lib/types";
import { Cited, EvidenceProvider } from "../evidence";
import { FollowButton } from "../follow-button";
import { PriceChart } from "../price-chart";
import { useShell } from "../shell";
import { Badge, EmptyState, PageTitle } from "../ui";
import { Analysis, Constraints, Coverage } from "./analysis";
import { HorizonDetail } from "./horizon-detail";
import { HorizonStrip } from "./horizon-strip";
import { Levels } from "./levels";
import { Pillars } from "./pillars";
import { ProsCons } from "./pros-cons";

function ExportMenu({ reportId }: { reportId: string }) {
  return (
    <details className="relative">
      <summary className="btn cursor-pointer list-none [&::-webkit-details-marker]:hidden">
        <Download size={15} aria-hidden /> Export{" "}
        <ChevronDown size={14} aria-hidden />
      </summary>
      <ul className="absolute right-0 z-20 mt-1.5 w-56 rounded-lg border border-line bg-bg p-1 shadow-pop">
        {(
          [
            ["card", "Signal card (Markdown)"],
            ["details", "Full analysis (Markdown)"],
            ["json", "Everything (JSON)"],
          ] as const
        ).map(([format, label]) => (
          <li key={format}>
            <a
              href={api.exportUrl(reportId, format)}
              className="block rounded-md px-3 py-2 no-underline hover:bg-wash-2"
            >
              {label}
            </a>
          </li>
        ))}
      </ul>
    </details>
  );
}

function HistoryPicker({
  current,
  history,
}: {
  current: string;
  history: ReportSummary[];
}) {
  const router = useRouter();
  if (history.length < 2) return null;
  return (
    <label className="flex items-center gap-2">
      <span className="meta">Report</span>
      <select
        className="field !w-auto !min-h-8 pr-7"
        value={current}
        onChange={(event) =>
          router.push(`/reports/${encodeURIComponent(event.target.value)}`)
        }
      >
        {history.map((item) => (
          <option key={item.report_id} value={item.report_id}>
            {stamp(item.generated_at)} · {MODE_LABEL[item.mode]}
            {item.dry_run ? " · dry run" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}

export function ReportView({
  report,
  dryRun = false,
  history = [],
}: {
  report: Report;
  dryRun?: boolean;
  history?: ReportSummary[];
}) {
  const { launchRun } = useShell();
  const [section, setSection] = useState("summary");
  const card = report.scorecard;
  const listing = report.pack?.listing;
  const symbol = listing?.symbol ?? report.request.symbol;
  const cutoff = report.pack?.cutoff ?? report.request.cutoff;
  const summary =
    report.final_synthesis?.status === "completed"
      ? report.final_synthesis.summary
      : "";

  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) setSection(entry.target.id);
      }
    }, { rootMargin: "-100px 0px -60% 0px" });
    document.querySelectorAll("[data-report-section]").forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [report.report_id]);

  return (
    <EvidenceProvider pack={report.pack}>
      <PageTitle
        title={listing?.name ?? symbol}
        aside={
          <>
            <HistoryPicker current={report.report_id} history={history} />
            <FollowButton symbol={symbol} />
            <button
              type="button"
              className="btn"
              onClick={() => launchRun(symbol)}
            >
              <RefreshCw size={15} aria-hidden /> Research again
            </button>
            <ExportMenu reportId={report.report_id} />
          </>
        }
      >
        <span className="badge" data-tone="accent">
          {symbol}
        </span>
        <span>Research as of {dateOnly(cutoff)}</span>
        <span className="text-ink-3">·</span>
        <span>{MODE_LABEL[report.request.mode]} run</span>
        {history.length < 2 && <span title={report.generated_at}>· {stamp(report.generated_at)}</span>}
        {card && !card.model_adjusted && <Badge>Code-only scorecard</Badge>}
        {dryRun && <Badge tone="bad">Dry run</Badge>}
        {report.status !== "completed" && (
          <Badge tone="warn">
            {STATUS_LABEL[report.status] ?? report.status}
          </Badge>
        )}
      </PageTitle>

      {!card ? (
        <div className="mt-8">
          <EmptyState title="No scorecard for this report">
            The company’s evidence could not be collected, so nothing was
            scored. The notes below say what was missing.
          </EmptyState>
          <div className="mt-8">
            <Coverage coverage={report.coverage} />
          </div>
        </div>
      ) : (
        <div className="report-workspace">
          <nav className="report-nav" aria-label="Report sections">
            <div className="report-nav-company"><strong>{symbol}</strong><span>{MODE_LABEL[report.request.mode]} · {dateOnly(cutoff)}</span></div>
            <div className="report-nav-links">
              {([["summary", "Summary"], ["scores", "Scores"], ["outlook", "Outlook"], ["drivers", "Risks & drivers"], ["sources", "Sources"], ["analysis", "Full analysis"]] as const).map(([id, label]) => (
                <a key={id} href={`#${id}`} onClick={() => setSection(id)} aria-current={section === id ? "location" : undefined}>{label}</a>
              ))}
            </div>
          </nav>
          <section id="summary" data-report-section className="report-overview" aria-label="Research summary">
            <div className="report-takeaway">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="section-title">Research takeaway</h2>
                <span className="meta">{card.model_adjusted ? "Evidence-led synthesis" : "From scoring rules"}</span>
              </div>
              {summary ? <p className="report-summary"><Cited text={summary} grouped /></p> : (
                <p className="report-summary">This report scores the available company data. Explore each area below to see which rules moved the signals and the evidence behind them.</p>
              )}
              <HorizonStrip card={card} />
              <p className="meta mt-4">{EXPERIMENTAL}</p>
            </div>
            <div className="report-price">
              <PriceChart
                symbol={symbol}
                levels={card.levels?.levels ?? []}
                close={card.levels?.close}
                levelsAsOf={card.levels?.as_of}
                initialSessions={126}
                height={300}
              />
            </div>
          </section>
          <div className="report-detail-grid">
            <div className="min-w-0 space-y-8">
              <div id="scores" data-report-section className="report-surface"><Pillars card={card} /></div>
              <div id="outlook" data-report-section className="report-surface"><HorizonDetail card={card} /></div>
            </div>
            <div className="report-surface min-w-0"><Levels card={card} /></div>
          </div>
          <div id="drivers" data-report-section className="report-surface space-y-8"><ProsCons report={report} /><Constraints vetoes={report.vetoes} /></div>
          <div id="sources" data-report-section className="report-surface"><Coverage coverage={report.coverage} /></div>
          <div id="analysis" data-report-section className="report-surface"><Analysis report={report} /></div>
        </div>
      )}
    </EvidenceProvider>
  );
}
