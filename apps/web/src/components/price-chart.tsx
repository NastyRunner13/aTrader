"use client";

import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  createChart,
  HistogramSeries,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  LineSeries,
  LineStyle,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { count, dateOnly, rupees, signedPct } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Bars, Level } from "@/lib/types";
import { CopyCommand } from "./ui";

const RANGES = [
  { label: "3M", sessions: 63 },
  { label: "6M", sessions: 126 },
  { label: "1Y", sessions: 250 },
  { label: "2Y", sessions: 500 },
] as const;

/** A design token as rgb(): the chart library cannot read oklch(), the browser can. */
function token(name: string): string {
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 1;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return "#444";
  context.fillStyle = raw || "#444";
  context.fillRect(0, 0, 1, 1);
  const [r, g, b, a] = context.getImageData(0, 0, 1, 1).data;
  return `rgba(${r},${g},${b},${(a ?? 255) / 255})`;
}

type Series = {
  chart: IChartApi;
  candles: ISeriesApi<"Candlestick">;
  volume: ISeriesApi<"Histogram">;
  sma: Record<string, ISeriesApi<"Line">>;
  lines: IPriceLine[];
};

type Readout = {
  session: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  delivery?: number | null;
};

const AVERAGES = [
  { key: "sma20", label: "20", color: "--color-accent" },
  { key: "sma50", label: "50", color: "--color-ink-3" },
  { key: "sma200", label: "200", color: "--color-ink" },
] as const;

export function PriceChart({
  symbol,
  levels = [],
  close,
  levelsAsOf,
  height = 360,
  initialSessions = 250,
  compact = false,
}: {
  symbol: string;
  levels?: Level[];
  close?: number;
  levelsAsOf?: string;
  height?: number;
  initialSessions?: number;
  compact?: boolean;
}) {
  const [sessions, setSessions] = useState(initialSessions);
  const [show, setShow] = useState({
    levels: !compact,
    volume: !compact,
    sma20: false,
    sma50: !compact,
    sma200: !compact,
  });
  const [hover, setHover] = useState<Readout | null>(null);
  const container = useRef<HTMLDivElement>(null);
  const series = useRef<Series | null>(null);
  const { data, error, isLoading } = useApi<Bars>(
    `/v1/instruments/${encodeURIComponent(symbol)}/bars?sessions=${sessions}`,
    {
      keepPreviousData: true, // changing the range updates the series; it does not rebuild the chart
    },
  );

  const byDate = useMemo(
    () => new Map((data?.bars ?? []).map((bar) => [bar.session, bar])),
    [data],
  );
  const byDateRef = useRef(byDate);
  byDateRef.current = byDate;
  const last = data?.bars.at(-1);
  const previous = data?.bars.at(-2);
  const change = last && previous && previous.close > 0 ? (last.close / previous.close - 1) * 100 : null;
  const drawn = useMemo(() => {
    const reference = close ?? last?.close ?? 0;
    return (["resistance", "support"] as const).flatMap((kind) => levels
      .filter((level) => level.kind === kind)
      .sort((a, b) => Math.abs(a.price - reference) - Math.abs(b.price - reference))
      .slice(0, 2));
  }, [levels, close, last?.close]);

  // Create the chart once the container exists.
  useEffect(() => {
    const element = container.current;
    if (!element || !data) return;
    const ink = token("--color-wash-2");
    const chart = createChart(element, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: token("--color-bg") },
        textColor: token("--color-ink-3"),
        fontFamily: "Geist Variable, ui-sans-serif, system-ui, sans-serif",
        fontSize: 12,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: token("--color-line") },
      },
      rightPriceScale: {
        borderVisible: false,
        alignLabels: true,
        scaleMargins: { top: 0.06, bottom: 0.2 },
      },
      timeScale: { borderVisible: false, rightOffset: 4, timeVisible: false },
      crosshair: {
        mode: CrosshairMode.Magnet,
        vertLine: {
          color: token("--color-line-strong"),
          labelBackgroundColor: ink,
        },
        horzLine: {
          color: token("--color-line-strong"),
          labelBackgroundColor: ink,
        },
      },
      localization: {
        priceFormatter: (price: number) =>
          price.toLocaleString("en-IN", { maximumFractionDigits: 2 }),
      },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: token("--color-bull-solid"),
      borderUpColor: token("--color-bull-solid"),
      wickUpColor: token("--color-bull-solid"),
      downColor: token("--color-bear-solid"),
      borderDownColor: token("--color-bear-solid"),
      wickDownColor: token("--color-bear-solid"),
      priceLineVisible: false,
    });
    const volume = chart.addSeries(HistogramSeries, {
      priceScaleId: "volume",
      priceFormat: { type: "volume" },
      lastValueVisible: false,
      priceLineVisible: false,
    });
    chart
      .priceScale("volume")
      .applyOptions({ scaleMargins: { top: 0.84, bottom: 0 } });
    const sma: Record<string, ISeriesApi<"Line">> = {};
    for (const { key, color } of AVERAGES) {
      sma[key] = chart.addSeries(LineSeries, {
        color: token(color),
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
    }
    chart.subscribeCrosshairMove((param) => {
      const bar = param.time
        ? byDateRef.current.get(String(param.time))
        : undefined;
      setHover(
        bar
          ? {
              session: bar.session,
              open: bar.open,
              high: bar.high,
              low: bar.low,
              close: bar.close,
              volume: bar.volume,
              delivery: bar.delivery_pct,
            }
          : null,
      );
    });
    series.current = { chart, candles, volume, sma, lines: [] };
    return () => {
      chart.remove();
      series.current = null;
    };
    // Rebuilt only when data first arrives or the symbol changes; later updates go
    // through the effects below.
  }, [symbol, data === undefined]);

  // Data.
  useEffect(() => {
    const s = series.current;
    if (!s || !data) return;
    s.candles.setData(
      data.bars.map((b) => ({
        time: b.session,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      })),
    );
    const up = token("--color-line-strong");
    const down = token("--color-ink-3");
    s.volume.setData(
      data.bars.map((b) => ({
        time: b.session,
        value: b.volume,
        color: b.close >= b.open ? up : down,
      })),
    );
    for (const { key } of AVERAGES) {
      const values = data.averages[key] ?? [];
      s.sma[key]?.setData(
        data.bars.flatMap((b, i) =>
          values[i] == null
            ? []
            : [{ time: b.session, value: values[i] as number }],
        ),
      );
    }
    s.chart.timeScale().fitContent();
  }, [data]);

  // Toggles.
  useEffect(() => {
    const s = series.current;
    if (!s) return;
    s.volume.applyOptions({ visible: show.volume });
    for (const { key } of AVERAGES)
      s.sma[key]?.applyOptions({ visible: show[key] });
  }, [show, data]);

  // Level lines: the two nearest resistances above and supports below the last close. The
  // rest (VWAPs, the heaviest-traded band) stay in the levels table: more lines only crowd
  // the price axis.
  useEffect(() => {
    const s = series.current;
    if (!s) return;
    for (const line of s.lines) s.candles.removePriceLine(line);
    s.lines = [];
    if (!show.levels) return;
    s.lines = drawn.map((level) =>
      s.candles.createPriceLine({
        price: level.price,
        color: token("--color-ink-3"),
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: false,
      }),
    );
  }, [drawn, show.levels, data]);

  if (error) {
    return error.code === "no_prices" ? (
      <div className="rounded-lg border border-dashed border-line-strong p-6">
        <p className="font-medium">No price history stored for {symbol} yet.</p>
        <p className="meta mt-1">
          Download NSE prices once, then reload this page.
        </p>
        <CopyCommand command="uv run atrader ingest" />
      </div>
    ) : (
      <div className="rounded-lg border border-line p-6" role="alert">
        <p className="font-medium">The chart could not load.</p>
        <p className="meta mt-1">
          {error instanceof ApiError ? error.message : "Unknown error."}
        </p>
      </div>
    );
  }

  const shown =
    hover ??
    (last
      ? {
          session: last.session,
          open: last.open,
          high: last.high,
          low: last.low,
          close: last.close,
          volume: last.volume,
          delivery: last.delivery_pct,
        }
      : null);

  return (
    <figure className="price-chart">
      {!compact && <div className="chart-quote">
        <div><p className="meta">Latest stored close · {last ? dateOnly(last.session) : "Loading prices…"}</p><div className="mt-1 flex flex-wrap items-baseline gap-3"><strong className="num text-[1.75rem] font-medium">{rupees(last?.close)}</strong>{change != null && <span className={`num font-medium ${change >= 0 ? "text-bull-ink" : "text-bear-ink"}`}>{signedPct(change, 2)} <span className="meta font-normal">vs prior session</span></span>}</div></div>
        <span className="badge">Daily · NSE</span>
      </div>}
      <figcaption className="chart-toolbar">
        <div
          className={compact ? "hidden" : "chart-readout num text-xs text-ink-2"}
          aria-live="off"
        >
          {shown ? (
            <>
              <span className="font-medium text-ink">
                {hover ? "Selected " : "Latest "}
                {dateOnly(shown.session)}
              </span>
              <span className="ml-3">O {rupees(shown.open)}</span>
              <span className="ml-2">H {rupees(shown.high)}</span>
              <span className="ml-2">L {rupees(shown.low)}</span>
              <span className="ml-2">C {rupees(shown.close)}</span>
              {shown.volume != null && (
                <span className="ml-3 text-ink-3">
                  Vol {count(shown.volume)}
                </span>
              )}
              {shown.delivery != null && (
                <span className="ml-2 text-ink-3">
                  Deliv. {shown.delivery}%
                </span>
              )}
            </>
          ) : (
            <span className="text-ink-3">&nbsp;</span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <div
            role="group"
            aria-label="Chart range"
            className="flex rounded-md border border-line p-0.5"
          >
            {RANGES.map((range) => (
              <button
                key={range.label}
                type="button"
                className="btn btn-quiet btn-sm !min-h-6 !px-2"
                aria-pressed={sessions === range.sessions}
                data-active={sessions === range.sessions}
                style={
                  sessions === range.sessions
                    ? {
                        background: "var(--color-wash-2)",
                        color: "var(--color-ink)",
                      }
                    : undefined
                }
                onClick={() => setSessions(range.sessions)}
              >
                {range.label}
              </button>
            ))}
          </div>
          {!compact && <details className="chart-indicators">
            <summary className="btn btn-sm cursor-pointer">Indicators <span className="text-ink-3">{Object.values(show).filter(Boolean).length}</span></summary>
            <div role="group" aria-label="Chart layers" className="chart-layer-options">
            <Toggle
              on={show.levels}
              onChange={(on) => setShow((s) => ({ ...s, levels: on }))}
            >
              Levels
            </Toggle>
            <Toggle
              on={show.volume}
              onChange={(on) => setShow((s) => ({ ...s, volume: on }))}
            >
              Volume
            </Toggle>
            {AVERAGES.map(({ key, label, color }) => (
              <Toggle
                key={key}
                on={show[key]}
                onChange={(on) => setShow((s) => ({ ...s, [key]: on }))}
                swatch={`var(${color})`}
              >
                SMA {label}
              </Toggle>
            ))}
            </div>
          </details>}
        </div>
      </figcaption>

      <div className="relative mt-1" style={{ height }}>
        {isLoading && <div className="skeleton absolute inset-0" aria-hidden />}
        <div
          ref={container}
          className="absolute inset-0"
          role="img"
          aria-label={`Candlestick chart of ${symbol} daily prices${last ? `, last close ${rupees(last.close)}` : ""}`}
        />
      </div>
      {!compact && show.levels && drawn.length > 0 && <div className="chart-level-legend">
        <p className="meta">Report levels{levelsAsOf ? ` · ${dateOnly(levelsAsOf)}` : ""}</p>
        <ul>{drawn.map((level) => <li key={`${level.kind}-${level.price}`}><span className="chart-level-dash" aria-hidden /><span>{level.kind === "support" ? "Support" : "Resistance"}</span><strong className="num font-medium text-ink-2">{rupees(level.price)}</strong></li>)}</ul>
        {levelsAsOf && last && levelsAsOf !== last.session && <p className="meta mt-2">The chart includes newer prices. Report levels stay fixed to {dateOnly(levelsAsOf)}.</p>}
      </div>}
      {data?.adjusted && (
        <p className="meta mt-2">
          Prices before {dateOnly(data.adjustments.at(-1)?.session)} are
          adjusted for a split or bonus.
        </p>
      )}
    </figure>
  );
}

function Toggle({
  on,
  onChange,
  swatch,
  children,
}: {
  on: boolean;
  onChange: (on: boolean) => void;
  swatch?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      className="btn btn-sm"
      aria-pressed={on}
      onClick={() => onChange(!on)}
      style={
        on
          ? { background: "var(--color-wash-2)" }
          : { color: "var(--color-ink-3)" }
      }
    >
      {swatch && (
        <span
          className="inline-block h-0.5 w-3 rounded-full"
          style={{ background: swatch, opacity: on ? 1 : 0.35 }}
          aria-hidden
        />
      )}
      {children}
    </button>
  );
}
