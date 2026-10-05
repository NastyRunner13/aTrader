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
  | { kind: "news"; item: EvidencePack["news"][number] };

type Context = { open: (id: string) => void; has: (id: string) => boolean };

const EvidenceContext = createContext<Context>({ open: () => {}, has: () => false });

const ID = /^[FMASN]\d+$/;
const INLINE = /\[([FMASN]\d+)\]/g;

function indexPack(pack: EvidencePack | null): Map<string, Found> {
  const index = new Map<string, Found>();
  if (!pack) return index;
  for (const item of pack.facts ?? []) index.set(item.evidence_id ?? "", { kind: "fact", item });
  for (const item of pack.metrics ?? []) index.set(item.evidence_id ?? "", { kind: "metric", item });
  for (const item of pack.announcements ?? []) index.set(item.evidence_id ?? "", { kind: "announcement", item });
  for (const item of pack.shareholding ?? []) index.set(item.evidence_id ?? "", { kind: "shareholding", item });
  for (const item of pack.news ?? []) index.set(item.evidence_id ?? "", { kind: "news", item });
  return index;
}

/** Holds a report's evidence and the drawer that shows one item of it. */
export function EvidenceProvider({ pack, children }: { pack: EvidencePack | null; children: ReactNode }) {
  const index = useMemo(() => indexPack(pack), [pack]);
  const [openId, setOpenId] = useState<string | null>(null);
  const value = useMemo<Context>(
    () => ({ open: setOpenId, has: (id) => index.has(id) }),
    [index],
  );
  return (
    <EvidenceContext.Provider value={value}>
      {children}
      <EvidenceDrawer found={openId ? (index.get(openId) ?? null) : null} id={openId} onClose={() => setOpenId(null)} />
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
export function Cited({ text, ids = [] }: { text: string; ids?: string[] }) {
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
  news: "News headline",
};

function EvidenceDrawer({ found, id, onClose }: { found: Found | null; id: string | null; onClose: () => void }) {
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
            <p className="meta">{found ? KIND_LABEL[found.kind] : "Evidence"}</p>
            <h2 id="evidence-title" className="mt-0.5 text-lg font-semibold">
              {id ?? ""}
            </h2>
          </div>
          <button type="button" className="btn btn-quiet btn-icon -mr-2" onClick={() => ref.current?.close()} aria-label="Close">
            <X size={16} aria-hidden />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-6 py-5">
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
    case "fact": {
      const f = found.item;
      return (
        <>
          <p className="display text-xl">{f.label}</p>
          <p className="score-figure mt-3 !text-2xl">{factValue(f.value, f.unit)}</p>
          {f.missing_reason && <p className="mt-2 text-warn-ink">Not reported: {f.missing_reason}</p>}
          <dl className="mt-5">
            <Row label="Period">
              {f.period_start ? `${dateOnly(f.period_start)} to ` : ""}
              {dateOnly(f.period_end)} ({f.duration.replace("_", " ")})
            </Row>
            <Row label="Basis">{f.basis}{f.audited == null ? "" : f.audited ? ", audited" : ", unaudited"}</Row>
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
          <p className="display text-xl">{m.label}</p>
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
          <p className="display text-xl">{a.category}</p>
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
          <p className="display text-xl">Shareholding at {dateOnly(s.period_end)}</p>
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
          <p className="display text-xl">{n.title}</p>
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
