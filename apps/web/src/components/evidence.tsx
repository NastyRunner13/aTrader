"use client";

import { ExternalLink, X } from "lucide-react";
import { createContext, type ReactNode, useContext, useEffect, useMemo, useRef, useState } from "react";
import { dateOnly, factValue, metricValue, safeUrl, stamp } from "@/lib/format";
import type { EvidencePack } from "@/lib/types";

type Found =
  | { kind: "fact"; item: EvidencePack["facts"][number] }
  | { kind: "metric"; item: EvidencePack["metrics"][number] }
  | { kind: "announcement"; item: EvidencePack["announcements"][number] }
  | { kind: "shareholding"; item: EvidencePack["shareholding"][number] }
  | { kind: "institutional"; item: EvidencePack["institutional_activity"][number] }
  | { kind: "document"; item: EvidencePack["documents"][number] }
  | { kind: "ownership"; item: EvidencePack["ownership"][number] }
  | { kind: "action"; item: EvidencePack["corporate_actions"][number] }
  | { kind: "sector"; item: EvidencePack["sector_flows"][number] }
  | { kind: "news"; item: EvidencePack["news"][number] };

type Context = { open: (id: string) => void; openSources: (ids: string[]) => void; has: (id: string) => boolean };

const EvidenceContext = createContext<Context>({ open: () => {}, openSources: () => {}, has: () => false });

const ID = /^[FMASNIDHTC]\d+$/;
const INLINE = /\[([FMASNIDHTC]\d+)\]/g;

function indexPack(pack: EvidencePack | null): Map<string, Found> {
  const index = new Map<string, Found>();
  if (!pack) return index;
  for (const item of pack.facts ?? []) index.set(item.evidence_id ?? "", { kind: "fact", item });
  for (const item of pack.metrics ?? []) index.set(item.evidence_id ?? "", { kind: "metric", item });
  for (const item of pack.announcements ?? []) index.set(item.evidence_id ?? "", { kind: "announcement", item });
  for (const item of pack.shareholding ?? []) index.set(item.evidence_id ?? "", { kind: "shareholding", item });
  for (const item of pack.news ?? []) index.set(item.evidence_id ?? "", { kind: "news", item });
  for (const item of pack.institutional_activity ?? []) index.set(item.evidence_id ?? "", { kind: "institutional", item });
  for (const item of pack.documents ?? []) index.set(item.evidence_id ?? "", { kind: "document", item });
  for (const item of pack.ownership ?? []) index.set(item.evidence_id ?? "", { kind: "ownership", item });
  for (const item of pack.corporate_actions ?? []) index.set(item.evidence_id ?? "", { kind: "action", item });
  for (const item of pack.sector_flows ?? []) index.set(item.evidence_id ?? "", { kind: "sector", item });
  return index;
}

/** Holds a report's evidence and the drawer that shows one item of it. */
export function EvidenceProvider({ pack, children }: { pack: EvidencePack | null; children: ReactNode }) {
  const index = useMemo(() => indexPack(pack), [pack]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [sourceIds, setSourceIds] = useState<string[]>([]);
  const value = useMemo<Context>(
    () => ({
      open: (id) => { setSourceIds([]); setOpenId(id); },
      openSources: (ids) => { setSourceIds(ids); setOpenId(ids[0] ?? null); },
      has: (id) => index.has(id),
    }),
    [index],
  );
  return (
    <EvidenceContext.Provider value={value}>
      {children}
      <EvidenceDrawer found={openId ? (index.get(openId) ?? null) : null} id={openId} sources={sourceIds.map((id) => ({ id, title: evidenceTitle(index.get(id) ?? null) }))} onSelect={setOpenId} onClose={() => setOpenId(null)} />
    </EvidenceContext.Provider>
  );
}

export function EvidenceChip({ id }: { id: string }) {
  const { open, has } = useContext(EvidenceContext);
  const known = has(id);
  return (
    <button
      type="button"
      className="evidence"
      onClick={() => open(id)}
      disabled={!known}
      title={known ? `Show the evidence behind ${id}` : `${id} is not in this report`}
      aria-label={`Evidence ${id}`}
    >
      {id}
    </button>
  );
}

/** Text with `[F3]`-style citations turned into evidence chips, followed by any IDs not already inline. */
export function Cited({ text, ids = [], grouped = false }: { text: string; ids?: string[]; grouped?: boolean }) {
  const { openSources } = useContext(EvidenceContext);
  if (grouped) {
    const sources = [...new Set([...text.matchAll(INLINE)].map((match) => match[1]!).concat(ids))];
    return <>{text.replace(INLINE, "").replace(/\s+([.,;:])/g, "$1").trim()}{sources.length > 0 && <button type="button" className="source-count" onClick={() => openSources(sources)}>{sources.length} {sources.length === 1 ? "source" : "sources"}<ExternalLink size={12} aria-hidden /></button>}</>;
  }
  const parts: ReactNode[] = [];
  const inline = new Set<string>();
  let last = 0;
  for (const match of text.matchAll(INLINE)) {
    const id = match[1] ?? "";
    parts.push(text.slice(last, match.index));
    parts.push(<EvidenceChip key={`${match.index}-${id}`} id={id} />);
    inline.add(id);
    last = (match.index ?? 0) + match[0].length;
  }
  parts.push(text.slice(last));
  const extra = ids.filter((id) => !inline.has(id));
  return (
    <>
      {parts}
      {extra.length > 0 && (
        <span className="ml-1 whitespace-nowrap">
          {extra.map((id) => (
            <EvidenceChip key={id} id={id} />
          ))}
        </span>
      )}
    </>
  );
}

// --- the drawer ---------------------------------------------------------------------------

const KIND_LABEL: Record<Found["kind"], string> = {
  fact: "Reported figure",
  metric: "Calculated metric",
  announcement: "Exchange announcement",
  shareholding: "Shareholding pattern",
  institutional: "Institutional cash activity",
  document: "Filing passage",
  ownership: "Reported ownership",
  sector: "Sector FPI activity",
  action: "Corporate action",
  news: "News headline",
};

function evidenceTitle(found: Found | null): string {
  if (!found) return "Unavailable evidence";
  switch (found.kind) {
    case "fact": case "metric": return found.item.label;
    case "announcement": return found.item.category;
    case "shareholding": return `Shareholding at ${dateOnly(found.item.period_end)}`;
    case "institutional": return `${found.item.participant} cash activity · ${dateOnly(found.item.session)}`;
    case "document": return `${found.item.title} · page ${found.item.page}`;
    case "ownership": return found.item.holder;
    case "action": return found.item.description;
    case "sector": return `${found.item.sector} · ${dateOnly(found.item.period_end)}`;
    case "news": return found.item.title;
  }
}

function EvidenceDrawer({ found, id, sources, onSelect, onClose }: { found: Found | null; id: string | null; sources: { id: string; title: string }[]; onSelect: (id: string) => void; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (id && !dialog.open) dialog.showModal();
    if (!id && dialog.open) dialog.close();
  }, [id]);

  return (
    <dialog
      ref={ref}
      className="sheet"
      aria-labelledby="evidence-title"
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) ref.current?.close(); // a click on the backdrop
      }}
    >
      <div className="flex h-full flex-col">
        <header className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
          <div>
            <p className="meta">{found ? KIND_LABEL[found.kind] : "Evidence"} · {id}</p>
            <h2 id="evidence-title" className="mt-0.5 text-lg font-semibold">
              {evidenceTitle(found)}
            </h2>
          </div>
          <button type="button" className="btn btn-quiet btn-icon -mr-2" onClick={() => ref.current?.close()} aria-label="Close">
            <X size={16} aria-hidden />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {sources.length > 1 && <details className="evidence-sources mb-5" open>
            <summary className="cursor-pointer font-medium">{sources.length} sources behind this statement</summary>
            <div className="mt-3 space-y-1" role="group" aria-label="Statement sources">
              {sources.map((source) => <button type="button" key={source.id} aria-pressed={id === source.id} onClick={() => onSelect(source.id)} className="evidence-source"><span>{source.title}</span><span className="meta">{source.id}</span></button>)}
            </div>
          </details>}
          {id && !found && <p className="prose-body">This ID is not part of the report’s evidence pack.</p>}
          {found && <EvidenceBody found={found} />}
        </div>
      </div>
    </dialog>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[8.5rem_1fr] gap-4 border-b border-line py-3 last:border-0">
      <dt className="meta pt-0.5">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

function Source({ url, label }: { url: string | null | undefined; label: string }) {
  const href = safeUrl(url);
  if (!href) return <span className="text-ink-3">No link</span>;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-accent underline-offset-2 hover:underline">
      {label}
      <ExternalLink size={13} aria-hidden />
    </a>
  );
}

function EvidenceBody({ found }: { found: Found }) {
  switch (found.kind) {
    case "action": {
      const a = found.item;
      return <dl><Row label="Ex date">{dateOnly(a.ex_date)}</Row><Row label="Share factor">{a.share_factor ?? "Not safely comparable"}</Row><Row label="Available">{stamp(a.available_at)}</Row><Row label="Source"><Source url={a.source.url} label="Open exchange listing" /></Row></dl>;
    }
    case "document": {
      const d = found.item;
      return <><p className="meta mt-3">Source text from page {d.page}; extracted text may lose table layout.</p><blockquote className="prose-body mt-4 whitespace-pre-wrap [overflow-wrap:anywhere]">{d.text}</blockquote><dl className="mt-5"><Row label="Published">{stamp(d.source.published_at)}</Row><Row label="Filing"><Source url={d.source.url ? `${d.source.url.split("#")[0]}#page=${d.page}` : null} label={`Open page ${d.page}`} /></Row></dl></>;
    }
    case "ownership": {
      const h = found.item;
      return <><p className="meta mt-3">Reported {h.level}. Categories overlap named holders; missing names are not confirmed exits.</p><dl className="mt-5"><Row label="Category">{h.category}</Row><Row label="Reporting date">{dateOnly(h.period_end)}</Row><Row label="Shares">{metricValue(h.shares, "shares")}</Row><Row label="Company ownership">{metricValue(h.ownership_pct, "%")}</Row><Row label="Pledged shares">{metricValue(h.pledged_shares, "shares")}</Row><Row label="All encumbered shares">{metricValue(h.encumbered_shares, "shares")}</Row><Row label="Available">{stamp(h.available_at)}</Row><Row label="Source"><Source url={h.source.url} label="Open disclosure" /></Row></dl></>;
    }
    case "sector": {
      const s = found.item;
      return <><p className="meta mt-3">Assets under custody change with prices and holdings. They are not net investment.</p><dl className="mt-5"><Row label="Period">{dateOnly(s.period_start)} – {dateOnly(s.period_end)}</Row><Row label="Classification">{s.taxonomy}</Row><Row label="Net equity investment">{metricValue(s.net_equity_inr, "INR")}</Row><Row label="Equity assets under custody">{metricValue(s.equity_auc_inr, "INR")}</Row><Row label="Observed">{stamp(s.available_at)}</Row><Row label="Source"><Source url={s.source.url} label="Open NSDL report" /></Row></dl></>;
    }
    case "institutional": {
      const row = found.item;
      return (
        <>
          <p className="prose-body mt-3">Market-wide cash activity. These figures do not identify buying or selling in this company. NSE-only and combined totals overlap.</p>
          <dl className="mt-5">
            <Row label="Participant">{row.participant}</Row>
            <Row label="Scope">{row.basis === "confirmed" ? "Custodian-confirmed equity" : row.scope === "nse" ? "NSE only" : "NSE, BSE and MSEI"}</Row>
            <Row label="Reporting basis">{row.basis}</Row>
            <Row label={row.date_basis === "reporting" ? "Reporting date" : "Session"}>{dateOnly(row.session)}</Row>
            <Row label="Investment route">{row.route === "primary_other" ? "Primary market and others" : "Stock exchange"}</Row>
            <Row label="Purchases">{metricValue(row.purchases_inr, "INR")}</Row>
            <Row label="Sales">{metricValue(row.sales_inr, "INR")}</Row>
            <Row label="Net activity">{metricValue(row.net_inr, "INR")}</Row>
            <Row label="Observed">{stamp(row.available_at)}</Row>
            <Row label="Published">{row.source.published_at ? stamp(row.source.published_at) : "Time not supplied by source"}</Row>
            <Row label="Source"><Source url={row.source.url} label="Open exchange data" /></Row>
          </dl>
        </>
      );
    }
    case "fact": {
      const f = found.item;
      return (
        <>
          <p className="score-figure mt-3 !text-2xl">{factValue(f.value, f.unit)}</p>
          {f.missing_reason && <p className="mt-2 text-warn-ink">Not reported: {f.missing_reason}</p>}
          <dl className="mt-5">
            <Row label="Period">
              {f.period_start ? `${dateOnly(f.period_start)} to ` : ""}
              {dateOnly(f.period_end)} ({f.duration.replace("_", " ")})
            </Row>
            <Row label="Basis">{f.basis}{f.audited == null ? "" : f.audited ? ", audited" : ", unaudited"}</Row>
            {(f.dimensions ?? []).length > 0 && <Row label="Segment context">{f.dimensions.map(([axis, member]) => `${axis}: ${member}`).join("; ")}</Row>}
            <Row label="Filed">{stamp(f.filed_at)}</Row>
            {f.revision_note && <Row label="Restatement">{f.revision_note}</Row>}
            <Row label="Source">
              {f.source.provider} · <Source url={f.source.url} label="Open the filing" />
            </Row>
          </dl>
        </>
      );
    }
    case "metric": {
      const m = found.item;
      return (
        <>
          <p className="score-figure mt-3 !text-2xl">{metricValue(m.value, m.unit)}</p>
          {m.detail && <p className="prose-body mt-2">{m.detail}</p>}
          <dl className="mt-5">
            <Row label="Formula">{m.formula} <span className="meta">(v{m.formula_version})</span></Row>
            <Row label="As of">{dateOnly(m.as_of)}</Row>
            <Row label="Inputs">
              {(m.inputs ?? []).length === 0 ? (
                <span className="text-ink-3">None recorded</span>
              ) : (
                <span className="flex flex-wrap items-center gap-1">
                  {(m.inputs ?? []).map((input) => (ID.test(input) ? <EvidenceChip key={input} id={input} /> : <span key={input}>{input}</span>))}
                </span>
              )}
            </Row>
            {(m.quality_flags ?? []).length > 0 && <Row label="Quality flags">{(m.quality_flags ?? []).join(", ")}</Row>}
          </dl>
        </>
      );
    }
    case "announcement": {
      const a = found.item;
      return (
        <>
          <p className="prose-body mt-3">{a.summary}</p>
          <dl className="mt-5">
            <Row label="Published">{stamp(a.published_at)}</Row>
            <Row label="Company">{a.symbol}</Row>
            <Row label="Attachment">
              <Source url={a.attachment_url} label="Open the filing" />
            </Row>
            <Row label="Source">{a.source.provider}</Row>
          </dl>
        </>
      );
    }
    case "shareholding": {
      const s = found.item;
      return (
        <>
          <dl className="mt-5">
            <Row label="Promoters">{s.promoter_pct == null ? "—" : `${s.promoter_pct}%`}</Row>
            <Row label="Public">{s.public_pct == null ? "—" : `${s.public_pct}%`}</Row>
            {s.employee_trust_pct != null && <Row label="Employee trusts">{s.employee_trust_pct}%</Row>}
            <Row label="Published">{stamp(s.published_at)}</Row>
            {s.remarks && <Row label="Remarks">{s.remarks}</Row>}
            <Row label="Source">{s.source.provider}</Row>
          </dl>
        </>
      );
    }
    case "news": {
      const n = found.item;
      return (
        <>
          <dl className="mt-5">
            <Row label="Publisher">{n.domain}</Row>
            <Row label="Published">{stamp(n.published_at)}</Row>
            <Row label="Article">
              <Source url={n.url} label="Open the article" />
            </Row>
            <Row label="Source">{n.source.provider}</Row>
          </dl>
        </>
      );
    }
  }
}
