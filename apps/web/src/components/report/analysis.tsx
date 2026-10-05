import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { count, dateOnly, elapsed, sentence } from "@/lib/format";
import { BANDS, SIGNAL_LABEL } from "@/lib/signal";
import type { AgentReport, Claim, CoverageEntry, DebateTurn, Report, RiskReview, Veto } from "@/lib/types";
import { Cited } from "../evidence";
import { Badge } from "../ui";

function Fold({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <details className="fold border-b border-line first:border-t">
      <summary className="flex cursor-pointer items-center gap-2 py-3.5 hover:bg-wash/60">
        <ChevronRight size={16} className="chev shrink-0 text-ink-3" aria-hidden />
        <span className="font-semibold">{title}</span>
        {hint && <span className="meta">{hint}</span>}
      </summary>
      <div className="space-y-5 pb-6 pl-6">{children}</div>
    </details>
  );
}

function ClaimList({ claims }: { claims: Claim[] }) {
  if (claims.length === 0) return null;
  return (
    <ul className="space-y-2.5">
      {claims.map((claim) => (
        <li key={claim.claim_id} className={claim.status === "unsupported" ? "text-ink-3" : "text-ink-2"}>
          <Cited text={claim.statement} ids={claim.evidence_ids ?? []} />
          <span className="ml-2 inline-flex gap-1 align-middle">
            <Badge tone={claim.status === "unsupported" ? "bad" : claim.status === "needs_review" ? "warn" : undefined}>{sentence(claim.status)}</Badge>
            <Badge>{sentence(claim.kind)}</Badge>
          </span>
          {(claim.issues ?? []).length > 0 && <p className="meta mt-0.5">{(claim.issues ?? []).join(" ")}</p>}
        </li>
      ))}
    </ul>
  );
}

function Analyst({ report }: { report: AgentReport }) {
  return (
    <div>
      <p className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{sentence(report.agent)}</span>
        {report.stance && <Badge>{sentence(report.stance)}</Badge>}
        {report.status !== "completed" && <Badge tone={report.status === "skipped" ? undefined : "warn"}>{sentence(report.status)}</Badge>}
      </p>
      {report.error && <p className="meta mt-1">{report.error}</p>}
      {report.summary && (
        <p className="prose-body mt-1.5 !text-sm">
          <Cited text={report.summary} />
        </p>
      )}
      <div className="mt-3">
        <ClaimList claims={report.claims} />
      </div>
      {report.gaps.length > 0 && (
        <p className="meta mt-3">Data it needed but did not have: {report.gaps.join("; ")}.</p>
      )}
    </div>
  );
}

function Turn({ turn }: { turn: DebateTurn }) {
  return (
    <div>
      <p className="flex flex-wrap items-center gap-2">
        <span className="font-semibold capitalize">
          {turn.side} · {turn.phase}
        </span>
        {turn.status !== "completed" && <Badge tone="warn">{sentence(turn.status)}</Badge>}
      </p>
      {turn.thesis && (
        <p className="prose-body mt-1.5 !text-sm">
          <Cited text={turn.thesis} />
        </p>
      )}
      <div className="mt-3">
        <ClaimList claims={turn.claims} />
      </div>
      {turn.challenges.length > 0 && (
        <div className="mt-3">
          <p className="meta">Challenges</p>
          <ul className="mt-1 space-y-1.5 text-ink-2">
            {turn.challenges.map((c) => (
              <li key={`${c.target_claim_id}-${c.argument}`}>
                <span className="meta">{c.target_claim_id} · {c.dispute}: </span>
                <Cited text={c.argument} ids={c.evidence_ids ?? []} />
              </li>
            ))}
          </ul>
        </div>
      )}
      {turn.falsifiers.length > 0 && <p className="meta mt-3">Would prove this side wrong: {turn.falsifiers.join("; ")}.</p>}
      {turn.unresolved_questions.length > 0 && <p className="meta mt-1">Unresolved: {turn.unresolved_questions.join("; ")}.</p>}
    </div>
  );
}

function Review({ review }: { review: RiskReview }) {
  return (
    <div>
      <p className="flex flex-wrap items-center gap-2">
        <span className="font-semibold capitalize">{review.perspective} reviewer</span>
        <Badge>{review.verdict === "too_high" ? "Scores look too high" : review.verdict === "too_low" ? "Scores look too low" : "Scores look fair"}</Badge>
      </p>
      <p className="prose-body mt-1.5 !text-sm">
        <Cited text={review.rationale} ids={review.evidence_ids ?? []} />
      </p>
      {review.objections.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-2 marker:text-ink-3">
          {review.objections.map((o) => (
            <li key={o}>{o}</li>
          ))}
        </ul>
      )}
      {review.constraints.length > 0 && <p className="meta mt-2">Conditions before relying on the signal: {review.constraints.join("; ")}.</p>}
    </div>
  );
}

export function Constraints({ vetoes }: { vetoes: Veto[] }) {
  if (vetoes.length === 0) return null;
  return (
    <section aria-labelledby="constraints-title">
      <h2 id="constraints-title" className="section-title">
        Constraints applied by code
      </h2>
      <p className="meta mt-1">A persuasive narrative cannot lift these.</p>
      <ul className="mt-3 divide-y divide-line border-y border-line">
        {vetoes.map((veto) => (
          <li key={veto.code} className="flex gap-3 py-3">
            <span className="shrink-0">
              <Badge tone={veto.severity === "block" ? "bad" : veto.severity === "cap" ? "warn" : undefined}>
                {veto.severity === "block" ? "Withholds signal" : veto.severity === "cap" ? "Caps at Neutral" : "Note"}
              </Badge>
            </span>
            <p className="text-ink-2">{veto.message}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

const COVERAGE_TONE: Record<string, "warn" | "bad" | undefined> = {
  partial: "warn",
  stale: "warn",
  missing: "bad",
  access_blocked: "bad",
};

export function Coverage({ coverage }: { coverage: CoverageEntry[] }) {
  if (coverage.length === 0) return null;
  return (
    <section aria-labelledby="coverage-title">
      <h2 id="coverage-title" className="section-title">
        Source coverage
      </h2>
      <p className="meta mt-1">What each source delivered for this report. A missing source is never counted as neutral.</p>
      <div className="mt-3 overflow-x-auto">
      <table className="tbl">
        <thead>
          <tr>
            <th scope="col">Source</th>
            <th scope="col">Status</th>
            <th scope="col">Detail</th>
          </tr>
        </thead>
        <tbody>
          {coverage.map((entry) => (
            <tr key={entry.category}>
              <td className="font-medium">{sentence(entry.category)}</td>
              <td>
                <Badge tone={COVERAGE_TONE[entry.status]}>{sentence(entry.status)}</Badge>
              </td>
              <td className="text-ink-2 [overflow-wrap:anywhere]">
                {entry.detail}
                {entry.as_of && <span className="meta"> · as of {dateOnly(entry.as_of)}</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </section>
  );
}

/** The model's work, folded away: analysts, debate, risk review, manager notes, calls and limits. */
export function Analysis({ report }: { report: Report }) {
  const synthesis = report.final_synthesis;
  const calls = report.model_calls.filter((c) => c.status !== "blocked");
  const tokens = calls.reduce((sum, c) => sum + (c.prompt_tokens ?? 0) + (c.completion_tokens ?? 0), 0);
  const cost = calls.reduce((sum, c) => sum + (c.cost ?? 0), 0);

  return (
    <section aria-labelledby="analysis-title">
      <h2 id="analysis-title" className="section-title">
        Full analysis
      </h2>
      <p className="meta mt-1 mb-3">Everything the agents wrote. Claims whose citations did not check out are marked and were kept out of the debate.</p>

      {report.analyst_reports.length > 0 && (
        <Fold title="Analyst reports" hint={`${report.analyst_reports.length}`}>
          {report.analyst_reports.map((a) => (
            <Analyst key={a.agent} report={a} />
          ))}
        </Fold>
      )}
      {report.debate.length > 0 && (
        <Fold title="Bull and bear debate" hint={`${report.debate.length} turns`}>
          {report.debate.map((turn) => (
            <Turn key={turn.turn_index} turn={turn} />
          ))}
        </Fold>
      )}
      {report.risk_reviews.length > 0 && (
        <Fold title="Risk review" hint={`${report.risk_reviews.length} reviewers`}>
          {report.risk_reviews.map((r) => (
            <Review key={r.perspective} review={r} />
          ))}
        </Fold>
      )}
      {synthesis && synthesis.status === "completed" && (synthesis.unresolved.length > 0 || synthesis.dropped_reasons.length > 0) && (
        <Fold title="Portfolio manager notes">
          {synthesis.unresolved.length > 0 && (
            <div>
              <p className="font-semibold">Still unresolved</p>
              <ul className="mt-1.5 list-disc space-y-1 pl-5 text-ink-2 marker:text-ink-3">
                {synthesis.unresolved.map((u) => (
                  <li key={u}>{u}</li>
                ))}
              </ul>
            </div>
          )}
          {synthesis.dropped_reasons.length > 0 && (
            <div>
              <p className="font-semibold">Removed as unsupported</p>
              <ul className="mt-1.5 list-disc space-y-1 pl-5 text-ink-3 marker:text-ink-3">
                {synthesis.dropped_reasons.map((u) => (
                  <li key={u}>{u}</li>
                ))}
              </ul>
            </div>
          )}
        </Fold>
      )}
      {calls.length > 0 && (
        <Fold title="Model calls" hint={`${calls.length} · ${count(tokens)} tokens${cost === 0 ? " · no cost" : ""}`}>
          <div className="overflow-x-auto">
          <table className="tbl">
            <thead>
              <tr>
                <th scope="col">Agent</th>
                <th scope="col">Model</th>
                <th scope="col">Result</th>
                <th scope="col" className="r">Tokens</th>
                <th scope="col" className="r">Time</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((c) => (
                <tr key={c.call_id}>
                  <td>{sentence(c.node)}{c.attempt > 1 && <span className="meta"> · attempt {c.attempt}</span>}</td>
                  <td className="text-ink-2">{c.served_model ?? c.requested_model}</td>
                  <td><Badge tone={c.status === "ok" ? undefined : "warn"}>{sentence(c.status)}</Badge></td>
                  <td className="num r">{count((c.prompt_tokens ?? 0) + (c.completion_tokens ?? 0))}</td>
                  <td className="num r">{c.latency_ms == null ? "—" : elapsed(c.latency_ms / 1000)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </Fold>
      )}
      <Fold title="How the score works, and its limits">
        <p className="prose-body !text-sm">
          Each area starts at 50, meaning no lean either way. Code rules add or subtract points for what the metrics show, each citing its evidence. Technical rules come in capped groups, so one price move is not counted once per indicator that sees it. Valuation compares the P/E with the stock’s NSE sector index first and the Nifty 50 second. An analyst may move its own area by up to ±15 points with cited evidence; the news area comes from the news analyst’s rated events. Each horizon weights the areas differently, the portfolio manager may move a horizon by up to ±5, and code constraints can hold a horizon at Neutral or withhold the signal.
        </p>
        <ul className="grid gap-1.5 sm:grid-cols-2">
          {[...BANDS].reverse().map((band) => (
            <li key={band.signal} className="flex justify-between gap-3 border-b border-line py-1.5">
              <span>{SIGNAL_LABEL[band.signal]}</span>
              <span className="num text-ink-2">{band.from === 0 ? "below 30" : band.to === 100 ? "71 and above" : `${band.from}–${band.to}`}</span>
            </li>
          ))}
        </ul>
        {report.scorecard && <p className="meta">Scorecard version {report.scorecard.version}.</p>}
        {report.notes.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-ink-2 marker:text-ink-3">
            {report.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        )}
        <div>
          <p className="font-semibold">Limitations</p>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-ink-2 marker:text-ink-3">
            {report.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </div>
      </Fold>
    </section>
  );
}
