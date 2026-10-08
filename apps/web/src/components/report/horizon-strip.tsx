import { sentence } from "@/lib/format";
import { HORIZON_LABEL } from "@/lib/signal";
import type { Scorecard } from "@/lib/types";
import { ScoreTrack, SignalChip } from "../signal";

/** A compact comparison; ranges, weights and constraints remain in the outlook section. */
export function HorizonStrip({ card }: { card: Scorecard }) {
  return (
    <section aria-label="Signals by horizon" className="horizon-summary">
      {card.horizons.map((view) => (
        <div key={view.horizon} role="group" aria-label={HORIZON_LABEL[view.horizon]}>
          <h3 className="font-medium">{HORIZON_LABEL[view.horizon]}</h3>
          <p className="my-2 flex items-baseline gap-1 num"><strong className="text-[2rem] font-medium leading-none">{view.score ?? "—"}</strong><span className="meta">/ 100</span></p>
          <SignalChip signal={view.signal} />
          <div className="my-3"><ScoreTrack score={view.score} signal={view.signal} /></div>
          <p className="meta">{sentence(view.confidence)} confidence</p>
          {view.capped_by.length > 0 && <p className="meta mt-1 text-warn-ink">Signal capped · see Outlook</p>}
        </div>
      ))}
    </section>
  );
}
