"use client";

import { useId, useState } from "react";
import { flipText, rangeText } from "@/lib/report";
import { HORIZON_LABEL, HORIZON_SHORT, PILLAR_LABEL } from "@/lib/signal";
import type { Horizon, Scorecard } from "@/lib/types";
import { SignalChip } from "../signal";

function Bullets({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h4 className="font-semibold">{title}</h4>
      <ul className="mt-1.5 list-disc space-y-1 pl-5 text-ink-2 marker:text-ink-3">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

/** One horizon at a time: what drives it, what would raise or lower it, and how it weighs the areas. */
export function HorizonDetail({ card }: { card: Scorecard }) {
  const [active, setActive] = useState<Horizon>(card.horizons[0]?.horizon ?? "1m");
  const base = useId();
  const view = card.horizons.find((h) => h.horizon === active) ?? card.horizons[0];
  if (!view) return null;
  const close = card.levels?.close;
  const flips = card.levels?.flips.filter((f) => f.horizon === view.horizon) ?? [];
  const range = rangeText(view.price_range);

  return (
    <section aria-labelledby={`${base}-title`}>
      <h2 id={`${base}-title`} className="section-title">
        By horizon
      </h2>
      <div role="tablist" aria-label="Horizon" className="mt-2 flex gap-6 border-b border-line">
        {card.horizons.map((h) => (
          <button
            key={h.horizon}
            id={`${base}-tab-${h.horizon}`}
            role="tab"
            type="button"
            className="tab"
            aria-selected={h.horizon === active}
            aria-controls={`${base}-panel`}
            tabIndex={h.horizon === active ? 0 : -1}
            onClick={() => setActive(h.horizon)}
            onKeyDown={(event) => {
              const order = card.horizons.map((x) => x.horizon);
              const at = order.indexOf(active);
              const next = event.key === "ArrowRight" ? order[(at + 1) % order.length] : event.key === "ArrowLeft" ? order[(at - 1 + order.length) % order.length] : undefined;
              if (next) {
                setActive(next);
                document.getElementById(`${base}-tab-${next}`)?.focus();
              }
            }}
          >
            {HORIZON_SHORT[h.horizon]}
          </button>
        ))}
      </div>

      <div id={`${base}-panel`} role="tabpanel" aria-labelledby={`${base}-tab-${view.horizon}`} className="mt-5 space-y-5">
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-semibold">{HORIZON_LABEL[view.horizon]}</span>
          <SignalChip signal={view.signal} />
          {view.score != null && <span className="num text-ink-2">{view.score} / 100</span>}
        </div>

        {view.drivers.length === 0 && view.up_if.length === 0 && view.down_if.length === 0 && (
          <p className="meta">No model notes for this horizon; the score above comes from the code rules alone.</p>
        )}
        <Bullets title="What drives it" items={view.drivers} />
        <div className="grid gap-5 sm:grid-cols-2">
          <Bullets title="Signal goes up if" items={view.up_if} />
          <Bullets title="Signal goes down if" items={view.down_if} />
        </div>

        {close != null && flips.length > 0 && (
          <div>
            <h4 className="font-semibold">Where the signal would change on price alone</h4>
            <ul className="mt-1.5 space-y-1 text-ink-2">
              {flips.map((flip) => (
                <li key={flip.direction}>{flipText(flip, close)}</li>
              ))}
            </ul>
          </div>
        )}

        {view.manager_adjustment !== 0 && (
          <p className="text-ink-2">
            The portfolio manager moved this score {view.manager_adjustment > 0 ? "+" : "−"}
            {Math.abs(view.manager_adjustment)}: {view.manager_reason ?? "no reason given"}.
          </p>
        )}
        {range && view.price_range && (
          <div>
            <h4 className="font-semibold">Price range</h4>
            <p className="num mt-1.5 font-medium">{range.headline}</p>
            <p className="meta mt-0.5">{view.price_range.detail}</p>
          </div>
        )}

        <div>
          <h4 className="font-semibold">How this horizon weighs the areas</h4>
          <ul className="mt-2 space-y-1.5">
            {(Object.entries(view.weights) as [keyof typeof PILLAR_LABEL, number][]).map(([pillar, weight]) => (
              <li key={pillar} className="grid grid-cols-[9rem_1fr_2.5rem] items-center gap-3">
                <span className="text-ink-2">{PILLAR_LABEL[pillar]}</span>
                <span className="h-1.5 rounded-full bg-wash-2">
                  <span className="block h-full rounded-full bg-ink-3" style={{ width: `${weight}%` }} />
                </span>
                <span className="num text-right text-ink-2">{weight}%</span>
              </li>
            ))}
          </ul>
          <p className="meta mt-2">
            {view.weight_covered}% of the weight had a score. A missing area is left out and its weight shared among the rest; it never counts as 50.
          </p>
        </div>
      </div>
    </section>
  );
}
