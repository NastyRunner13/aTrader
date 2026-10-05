import { ChevronRight } from "lucide-react";
import { sentence } from "@/lib/format";
import { mainReasons, weightLabel } from "@/lib/report";
import { PILLAR_LABEL } from "@/lib/signal";
import type { Factor, PillarScore, Scorecard } from "@/lib/types";
import { Cited, EvidenceChip } from "../evidence";

const MAX_POINTS = 15;

/** A contribution in points, with a small bar to the right (blue adds, amber subtracts). */
function PointsBar({ points }: { points: number }) {
  const width = `${Math.min(100, (Math.abs(points) / MAX_POINTS) * 100)}%`;
  return (
    <span className="flex items-center gap-2" aria-hidden>
      <span className="relative h-1.5 w-16 rounded-full bg-wash-2">
        <span
          className="absolute top-0 h-full rounded-full"
          style={{
            width: `calc(${width} / 2)`,
            left: points >= 0 ? "50%" : undefined,
            right: points < 0 ? "50%" : undefined,
            background: points >= 0 ? "var(--color-bull-solid)" : "var(--color-bear-solid)",
          }}
        />
        <span className="absolute left-1/2 top-[-2px] h-[10px] w-px bg-line-strong" />
      </span>
    </span>
  );
}

const signed = (points: number) => `${points > 0 ? "+" : points < 0 ? "−" : ""}${Math.abs(points).toFixed(0)}`;

function FactorRow({ factor }: { factor: Factor }) {
  const isCap = factor.kind === "cap";
  return (
    <li className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-0.5 border-b border-line py-2 last:border-0">
      <div className="min-w-0">
        <p className={isCap ? "text-ink-3 italic" : "text-ink"}>
          {factor.label}
          {(factor.evidence_ids ?? []).map((id) => (
            <EvidenceChip key={id} id={id} />
          ))}
        </p>
        {factor.group && <p className="meta capitalize">{factor.group}</p>}
      </div>
      <div className="flex items-center gap-3">
        <PointsBar points={factor.points} />
        <span className="num w-8 text-right font-medium">{signed(factor.points)}</span>
      </div>
    </li>
  );
}

function PillarRow({ pillar, card }: { pillar: PillarScore; card: Scorecard }) {
  const reasons = mainReasons(pillar);
  const scored = pillar.score != null;
  return (
    <details className="fold border-b border-line last:border-0">
      <summary className="grid cursor-pointer grid-cols-[1fr_auto] items-start gap-4 py-4 hover:bg-wash/60">
        <div className="flex min-w-0 gap-2">
          <ChevronRight size={16} className="chev mt-0.5 shrink-0 text-ink-3" aria-hidden />
          <div className="min-w-0">
            <p className="font-semibold">
              {PILLAR_LABEL[pillar.pillar]}
              {scored && <span className="meta ml-2 font-normal">{sentence(pillar.confidence)} confidence</span>}
            </p>
            <p className="meta mt-0.5">
              {scored ? (reasons.join(" · ") || "No rule moved the score") : `Not scored: ${pillar.note ?? "not enough data"}`}
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="display text-xl num leading-none">{scored ? pillar.score : "—"}</p>
          <p className="meta num mt-1">weight {weightLabel(card, pillar.pillar)}</p>
        </div>
      </summary>

      <div className="pb-5 pl-6">
        {pillar.adjustment !== 0 && (
          <p className="prose-body mb-3 !text-sm">
            Code score {pillar.base}, analyst adjustment {signed(pillar.adjustment)}
            {pillar.adjustment_reason && (
              <>
                : <Cited text={pillar.adjustment_reason} ids={pillar.adjustment_evidence ?? []} />
              </>
            )}
          </p>
        )}
        {pillar.factors.length > 0 ? (
          <ul>
            {pillar.factors.map((factor, index) => (
              <FactorRow key={`${factor.label}-${index}`} factor={factor} />
            ))}
          </ul>
        ) : (
          <p className="meta">No rules fired for this area.</p>
        )}
      </div>
    </details>
  );
}

/** The four areas behind the horizon scores. Each opens to the rules that moved it. */
export function Pillars({ card }: { card: Scorecard }) {
  return (
    <section aria-labelledby="pillars-title">
      <h2 id="pillars-title" className="section-title">
        Scores by area
      </h2>
      <p className="meta mt-1">Each area starts at 50. Open one to see the rules that moved it and the evidence they read.</p>
      <div className="mt-2 border-t border-line">
        {card.pillars.map((pillar) => (
          <PillarRow key={pillar.pillar} pillar={pillar} card={card} />
        ))}
      </div>
    </section>
  );
}
