import { fromClose, rupees, dateOnly } from "@/lib/format";
import { FLIP_NOTE, KIND_LABEL, LEVELS_NOTE, NO_SUPPORT, flipText, withClose } from "@/lib/report";
import { HORIZON_LABEL } from "@/lib/signal";
import type { Scorecard } from "@/lib/types";
import { EvidenceChip } from "../evidence";
import { SignalChip } from "../signal";

/** Price levels around the last close, and the closes that would flip each signal. */
export function Levels({ card }: { card: Scorecard }) {
  const levels = card.levels;
  if (!levels || levels.levels.length === 0) return null;
  const rows = withClose(levels.levels, levels.close);
  const hasSupport = levels.levels.some((l) => l.kind === "support");

  return (
    <div className="space-y-8">
      <section aria-labelledby="levels-title">
        <h2 id="levels-title" className="section-title">
          Price levels
        </h2>
        <p className="meta mt-1">
          Last close {rupees(levels.close)} on {dateOnly(levels.as_of)}. {LEVELS_NOTE}
        </p>
        <div className="mt-3 overflow-x-auto">
        <table className="tbl">
          <thead>
            <tr>
              <th scope="col">Level</th>
              <th scope="col" className="r">
                Price
              </th>
              <th scope="col" className="r">
                From close
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) =>
              row.close ? (
                <tr key="close" className="bg-accent-wash">
                  <td className="font-semibold text-accent">Last close</td>
                  <td className="num r font-semibold text-accent">{rupees(levels.close)}</td>
                  <td />
                </tr>
              ) : (
                <tr key={`${row.level.kind}-${row.level.label}-${row.level.price}`}>
                  <td>
                    <p className="font-medium">{row.level.label}</p>
                    <p className="meta">
                      {KIND_LABEL[row.level.kind]}
                      {row.level.detail ? ` · ${row.level.detail}` : ""}
                      <EvidenceChip id={row.level.evidence_id} />
                    </p>
                  </td>
                  <td className="num r">{rupees(row.level.price)}</td>
                  <td className="num r text-ink-2">{fromClose(row.level.price, levels.close)}</td>
                </tr>
              ),
            )}
          </tbody>
        </table>
        </div>
        <ul className="mt-3 space-y-1.5 text-ink-2">
          {levels.support_break && (
            <li>
              A close below {rupees(levels.support_break.price)} ({fromClose(levels.support_break.price, levels.close)}) breaks the nearest support:{" "}
              {levels.support_break.detail}
              <EvidenceChip id={levels.support_break.evidence_id} />
            </li>
          )}
          {!hasSupport && <li>{NO_SUPPORT}</li>}
        </ul>
      </section>

      {levels.flips.length > 0 && (
        <section aria-labelledby="flips-title">
          <h2 id="flips-title" className="section-title">
            What would flip each signal
          </h2>
          <p className="meta mt-1">{FLIP_NOTE}</p>
          <ul className="mt-3 divide-y divide-line border-y border-line">
            {card.horizons.map((view) => {
              const flips = levels.flips.filter((f) => f.horizon === view.horizon);
              if (flips.length === 0) return null;
              return (
                <li key={view.horizon} className="py-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium">{HORIZON_LABEL[view.horizon]}</span>
                    <SignalChip signal={view.signal} />
                  </div>
                  <ul className="mt-1.5 space-y-0.5 text-ink-2">
                    {flips.map((flip) => (
                      <li key={flip.direction}>{flipText(flip, levels.close)}</li>
                    ))}
                  </ul>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}
