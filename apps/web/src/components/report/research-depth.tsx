import { dateOnly, metricValue, sentence } from "@/lib/format";
import type { Report } from "@/lib/types";
import { Cited, EvidenceChip } from "../evidence";
import { Badge } from "../ui";

export function ResearchDepth({ report }: { report: Report }) {
  const findings = report.analyst_reports.flatMap((a) => a.investigations ?? []);
  const terms = report.analyst_reports.flatMap((a) => a.disclosure_terms ?? []);
  const management = report.analyst_reports.flatMap((a) => a.management_delivery ?? []);
  const metrics = (report.pack?.metrics ?? []).filter((m) => ["capital", "resilience", "segment"].includes(m.category));
  const valuation = (report.pack?.metrics ?? []).filter((m) => m.category === "valuation" && /^(dcf_|reverse_dcf|historical_)/.test(m.name));
  const ownershipChanges = (report.pack?.metrics ?? []).filter((m) => m.name.startsWith("ownership_"));
  const ownership = report.pack?.ownership ?? [];
  const sectors = report.pack?.sector_flows ?? [];
  const documents = report.pack?.documents ?? [];
  return <div className="space-y-5">
    {findings.length > 0 && <details className="fold border-b border-line">
      <summary className="cursor-pointer py-3.5 font-semibold">Business and financial investigations <span className="meta ml-2">{findings.length} {findings.length === 1 ? "assessment" : "assessments"}</span></summary>
      <ul className="divide-y divide-line pb-5">{findings.map((f, i) => <li key={i} className="space-y-2 py-4">
        <h3 className="font-semibold">{sentence(f.topic)} <Badge tone={f.status === "cited" ? undefined : "warn"}>{sentence(f.status)}</Badge></h3>
        <p className="prose-body !text-sm"><Cited text={f.finding} ids={f.evidence_ids} /></p>
        {f.mechanism && <p className="text-ink-2">How it works: {f.mechanism}</p>}
        {f.direction !== "unknown" && <p className="meta">Direction: {f.direction}</p>}
        {f.threats.length > 0 && <p className="text-ink-2">Threats: {f.threats.join("; ")}</p>}
        {f.missing.length > 0 && <p className="meta">Still needed: {f.missing.join("; ")}</p>}
        {f.quotes.map((q, j) => <blockquote key={j} className="border-l border-line pl-3 text-ink-2"><Cited text={`“${q.quote}”`} ids={[q.evidence_id]} /></blockquote>)}
      </li>)}</ul>
    </details>}
    {metrics.length > 0 && <details className="fold border-b border-line">
      <summary className="cursor-pointer py-3.5 font-semibold">Cash conversion, capital and resilience</summary>
      <p className="meta pb-3">Ratios use comparable periods. Return measures are accounting proxies; stress results depend on stated assumptions.</p>
      <div className="overflow-x-auto pb-5"><table className="tbl"><thead><tr><th>Measure</th><th className="r">Value</th></tr></thead><tbody>{metrics.map((m) => <tr key={m.evidence_id}><td><Cited text={m.label} ids={[m.evidence_id]} /></td><td className="num r">{metricValue(m.value, m.unit)}</td></tr>)}</tbody></table></div>
    </details>}
    {valuation.length > 0 && <details className="fold border-b border-line">
      <summary className="cursor-pointer py-3.5 font-semibold">Valuation assumptions and room for error</summary>
      <p className="meta pb-3">Conditional outcomes, not forecasts. Open a source to inspect revenue, margins, reinvestment, discount rates and other assumptions.</p>
      <div className="overflow-x-auto pb-5"><table className="tbl"><thead><tr><th>Scenario</th><th className="r">Result</th></tr></thead><tbody>{valuation.map((m) => <tr key={m.evidence_id}><td><Cited text={m.label} ids={[m.evidence_id]} /></td><td className="num r">{m.value == null ? "Not established" : metricValue(m.value, m.unit)}</td></tr>)}</tbody></table></div>
    </details>}
    {ownershipChanges.length > 0 && <details className="fold border-b border-line"><summary className="cursor-pointer py-3.5 font-semibold">Changes in disclosed ownership</summary><p className="meta">Percentage changes can reflect dilution. Share comparisons account for known splits and bonuses; incomplete action history stays unknown.</p><ul className="space-y-3 pb-5">{ownershipChanges.map((m) => <li key={m.evidence_id}><Cited text={m.label} ids={[m.evidence_id]} />: {m.value == null ? "Not established" : metricValue(m.value, m.unit)}<p className="meta">{m.detail}</p></li>)}</ul></details>}
    {terms.length > 0 && <details className="fold border-b border-line">
      <summary className="cursor-pointer py-3.5 font-semibold">Disclosed commercial and funding terms</summary>
      <p className="meta">Missing terms remain unknown. Awards are not added to reported backlog.</p>
      <ul className="divide-y divide-line pb-5">{terms.map((t, i) => <li key={i} className="space-y-2 py-3"><p><strong>{sentence(t.name)}: </strong>{t.value} <EvidenceChip id={t.support.evidence_id} /></p><blockquote className="text-ink-2">“{t.support.quote}”</blockquote></li>)}</ul>
    </details>}
    {management.length > 0 && <details className="fold border-b border-line">
      <summary className="cursor-pointer py-3.5 font-semibold">Management promises and outcomes</summary>
      <p className="meta">Quoted passages and chronology are checked. Delivery assessments remain model judgements.</p>
      <ul className="divide-y divide-line pb-5">{management.map((m, i) => <li key={i} className="space-y-2 py-3"><p className="font-semibold">{m.decision} <Badge>{sentence(m.assessment)}</Badge></p><p>Promise ({dateOnly(documents.find((d) => d.evidence_id === m.promise.evidence_id)?.source.published_at?.slice(0, 10))}): <Cited text={m.promise.quote} ids={[m.promise.evidence_id]} /></p><p>Outcome ({dateOnly(documents.find((d) => d.evidence_id === m.outcome?.evidence_id)?.source.published_at?.slice(0, 10))}): {m.outcome ? <Cited text={m.outcome.quote} ids={[m.outcome.evidence_id]} /> : "Not verified"}</p></li>)}</ul>
    </details>}
    {ownership.length > 0 && <details className="fold border-b border-line">
      <summary className="cursor-pointer py-3.5 font-semibold">Institutional ownership disclosures <span className="meta ml-2">{ownership.length} {ownership.length === 1 ? "record" : "records"}</span></summary>
      <p className="meta">Categories and named holders overlap. Percentages can change through dilution; absent holders are not confirmed exits.</p>
      <div className="overflow-x-auto pb-5"><table className="tbl"><thead><tr><th>Holder / category</th><th>Date</th><th className="r">Shares</th><th className="r">Ownership</th></tr></thead><tbody>{ownership.map((h) => <tr key={h.evidence_id}><td><Cited text={h.holder} ids={[h.evidence_id]} /><span className="meta block">{h.level} · {h.category}</span></td><td>{dateOnly(h.period_end)}</td><td className="num r">{metricValue(h.shares, "shares")}</td><td className="num r">{metricValue(h.ownership_pct, "%")}</td></tr>)}</tbody></table></div>
    </details>}
    {sectors.length > 0 && <details className="fold border-b border-line">
      <summary className="cursor-pointer py-3.5 font-semibold">Sector FPI investment</summary>
      <p className="meta">Net investment and assets under custody are distinct. Classification follows the source.</p>
      <div className="overflow-x-auto pb-5"><table className="tbl"><thead><tr><th>Sector / period end</th><th className="r">Net equity investment</th><th className="r">Equity AUC</th></tr></thead><tbody>{sectors.map((s) => <tr key={s.evidence_id}><td><Cited text={`${s.sector} · ${dateOnly(s.period_end)}`} ids={[s.evidence_id]} /></td><td className="num r">{metricValue(s.net_equity_inr, "INR")}</td><td className="num r">{metricValue(s.equity_auc_inr, "INR")}</td></tr>)}</tbody></table></div>
    </details>}
    {documents.length > 0 && <details className="fold border-b border-line">
      <summary className="cursor-pointer py-3.5 font-semibold">Source document passages <span className="meta ml-2">{documents.length} {documents.length === 1 ? "excerpt" : "excerpts"}</span></summary>
      <ul className="space-y-2 pb-5">{documents.map((d) => <li key={d.evidence_id}><Cited text={`${d.title} · page ${d.page}`} ids={[d.evidence_id]} /><span className="meta block">{d.topics.map(sentence).join(" · ")}</span></li>)}</ul>
    </details>}
  </div>;
}
