import { ChevronDown, ChevronUp, ChevronsDown, ChevronsUp, CircleDashed, Minus } from "lucide-react";
import { BANDS, SIGNAL_BAND_TINT, SIGNAL_LABEL } from "@/lib/signal";
import type { Signal } from "@/lib/types";

const ICON = {
  strong_bullish: ChevronsUp,
  bullish: ChevronUp,
  neutral: Minus,
  bearish: ChevronDown,
  strong_bearish: ChevronsDown,
  insufficient_data: CircleDashed,
} satisfies Record<Signal, unknown>;

/** The signal as a word and a direction mark. Colour is the third cue, never the only one. */
export function SignalChip({ signal }: { signal: Signal }) {
  const Icon = ICON[signal];
  return (
    <span className="signal" data-signal={signal}>
      <Icon size={13} strokeWidth={2.4} aria-hidden />
      {SIGNAL_LABEL[signal]}
    </span>
  );
}

/**
 * A 0–100 track in the five signal bands with a mark at the score. The band holding the
 * score is tinted with its signal colour; the others stay neutral.
 */
export function ScoreTrack({
  score,
  signal,
  ticks = false,
}: {
  score: number | null;
  signal: Signal;
  ticks?: boolean;
}) {
  const label = score == null ? "No score" : `Score ${score} of 100, ${SIGNAL_LABEL[signal]}`;
  return (
    <div role="img" aria-label={label} className="relative">
      <div className="flex h-1.5 overflow-hidden rounded-full">
        {BANDS.map((band) => {
          const active = score != null && score >= band.from && score <= band.to;
          return (
            <span
              key={band.signal}
              style={{
                flexGrow: band.to - band.from + 1,
                background: active ? SIGNAL_BAND_TINT[band.signal] : "var(--color-wash-2)",
                boxShadow: "inset -2px 0 0 var(--color-bg)",
              }}
            />
          );
        })}
      </div>
      {score != null && (
        <span
          className="absolute top-1/2 h-3.5 w-[3px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-ink ring-2 ring-bg"
          style={{ left: `${Math.min(100, Math.max(0, score))}%` }}
        />
      )}
      {ticks && (
        <div className="relative mt-1.5 h-4 text-2xs text-ink-3 num" aria-hidden>
          {[30, 45, 56, 71].map((tick) => (
            <span key={tick} className="absolute -translate-x-1/2" style={{ left: `${tick}%` }}>
              {tick}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
