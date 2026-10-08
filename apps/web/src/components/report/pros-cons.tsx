import { Minus, Plus } from "lucide-react";
import { prosAndCons } from "@/lib/report";
import type { Reason, Report } from "@/lib/types";
import { Cited } from "../evidence";

function List({ title, reasons, kind }: { title: string; reasons: Reason[]; kind: "pro" | "con" }) {
  const Icon = kind === "pro" ? Plus : Minus;
  return (
    <div>
      <h3 className="font-semibold">{title}</h3>
      {reasons.length === 0 ? (
        <p className="meta mt-2">Nothing stood out.</p>
      ) : (
        <ul className="driver-list mt-2">
          {reasons.map((reason) => (
            <li key={reason.statement} className="flex gap-3 border-b border-line py-4 last:border-0">
              <span
                className={`mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full ${
                  kind === "pro" ? "bg-bull-wash text-bull-ink" : "bg-bear-wash text-bear-ink"
                }`}
                aria-hidden
              >
                <Icon size={11} strokeWidth={3} />
              </span>
              <p className="text-[0.9375rem] leading-relaxed text-ink-2">
                <span className="sr-only">{kind === "pro" ? "Pro: " : "Con: "}</span>
                <Cited text={reason.statement} ids={reason.evidence_ids ?? []} grouped />
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ProsCons({ report }: { report: Report }) {
  const { pros, cons, fromRules } = prosAndCons(report);
  if (!pros.length && !cons.length) return null;
  return (
    <section aria-labelledby="proscons-title">
      <h2 id="proscons-title" className="section-title">
        Risks and drivers
      </h2>
      {fromRules && <p className="meta mt-1">From the scoring rules that moved the scores most; no model wrote these.</p>}
      <div className="mt-4 grid gap-x-10 gap-y-6 sm:grid-cols-2">
        <List title="What supports the outlook" reasons={pros} kind="pro" />
        <List title="What needs caution" reasons={cons} kind="con" />
      </div>
    </section>
  );
}
