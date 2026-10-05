import { sentence } from "@/lib/format";
import { HORIZON_LABEL, PILLAR_LABEL } from "@/lib/signal";
import { rangeText } from "@/lib/report";
import type { Scorecard } from "@/lib/types";
import { ScoreTrack, SignalChip } from "../signal";

/** Three horizons side by side: signal, score on its band track, range, and what drives it. */
export function HorizonStrip({ card }: { card: Scorecard }) {
  return (
    <section aria-label="Signals by horizon" className="grid divide-line overflow-hidden rounded-lg border border-line md:grid-cols-3 md:divide-x max-md:divide-y">
      {card.horizons.map((view) => {
        const range = rangeText(view.price_range);
        const headingId = `horizon-${view.horizon}`;
        return (
          <div key={view.horizon} className="px-5 pb-5 pt-4" role="group" aria-labelledby={headingId}>
            <div className="flex items-baseline justify-between gap-3">
              <h3 id={headingId} className="font-semibold">
                {HORIZON_LABEL[view.horizon]}
              </h3>
              <span className="meta">{sentence(view.confidence)} confidence</span>
            </div>

            <div className="mt-4 flex items-end justify-between gap-3">
              {view.score == null ? (
                <span className="display text-2xl text-ink-3">No signal</span>
              ) : (
                <span className="flex items-baseline gap-1.5">
                  <span className="score-figure">{view.score}</span>
                  <span className="meta">/ 100</span>
                </span>
              )}
              <SignalChip signal={view.signal} />
            </div>

            <div className="mt-4">
              <ScoreTrack score={view.score} signal={view.signal} ticks />
            </div>

            <dl className="mt-3 space-y-2.5 text-sm">
              {view.score == null && (
                <div>
                  <dt className="meta">Why there is no signal</dt>
                  <dd className="text-ink-2">
                    {view.weight_covered}% of this horizon’s weight had a score; at least 60% is needed, or a constraint blocked it.
                  </dd>
                </div>
              )}
              {range && (
                <div>
                  <dt className="meta">{range.caption}</dt>
                  <dd className="num font-medium">{range.headline}</dd>
                </div>
              )}
              {view.driven_by && (
                <div>
                  <dt className="meta">Driven by</dt>
                  <dd>{PILLAR_LABEL[view.driven_by]}</dd>
                </div>
              )}
              {view.capped_by.length > 0 && (
                <div>
                  <dt className="meta">Held at Neutral by</dt>
                  <dd className="text-warn-ink">{view.capped_by.join(", ").replaceAll("_", " ")}</dd>
                </div>
              )}
            </dl>
          </div>
        );
      })}
    </section>
  );
}
