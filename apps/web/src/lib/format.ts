const inrNumber = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const inrWhole = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const plain = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

export const rupees = (value: number | null | undefined): string =>
  value == null ? "—" : `₹${inrNumber.format(value)}`;

/** A rupee price with whole-number grouping for ranges, e.g. ₹3,420. */
export const rupeesWhole = (value: number): string => `₹${inrWhole.format(value)}`;

/** A reported amount in base INR, shown in crore (1 crore = 10,000,000). */
export function crore(value: number): string {
  if (Math.abs(value) >= 1e7) return `₹${inrWhole.format(value / 1e7)} Cr`;
  return `₹${inrWhole.format(value)}`;
}

export const signedPct = (value: number | null | undefined, digits = 1): string =>
  value == null ? "—" : `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toFixed(digits)}%`;

export const fromClose = (price: number, close: number): string => signedPct((price / close - 1) * 100);

const day = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const dayTime = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

/** A date-only string (YYYY-MM-DD) as "5 Oct 2026". */
export const dateOnly = (iso: string | null | undefined): string => (iso ? day.format(new Date(`${iso}T00:00:00Z`)) : "—");

/** A timestamp in Indian time, e.g. "5 Oct, 4:45 pm". */
export const stamp = (iso: string | null | undefined): string => {
  if (!iso) return "—";
  const date = new Date(iso.endsWith("Z") || /[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
  return dayTime.format(date).replace(/\b(am|pm)\b/i, (m) => m.toLowerCase());
};

export function ago(iso: string, now = Date.now()): string {
  const then = new Date(iso.endsWith("Z") || /[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`).getTime();
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return stamp(iso);
}

export const elapsed = (seconds: number): string => {
  const s = Math.max(0, Math.floor(seconds));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
};

export const sentence = (text: string): string => {
  const spaced = text.replaceAll("_", " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
};

export const count = (value: number): string => plain.format(value);

/** Metric values by unit, as the evidence pack names them. */
export function metricValue(value: number | null, unit: string): string {
  if (value == null) return "—";
  switch (unit) {
    case "%":
      return `${plain.format(value)}%`;
    case "INR":
    case "INR/share":
      return Math.abs(value) >= 1e7 ? crore(value) : rupees(value);
    case "x":
    case "ratio":
      return `${plain.format(value)}×`;
    default:
      return `${plain.format(value)}${unit && unit !== "signal" ? ` ${unit}` : ""}`;
  }
}

/** A filed amount, which the API sends as a decimal string, in its own unit. */
export function factValue(value: string | null, unit: string): string {
  if (value == null) return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  if (unit === "INR") return crore(n);
  if (unit === "INR/share") return rupees(n);
  return `${plain.format(n)}${unit && unit !== "pure" ? ` ${unit}` : ""}`;
}

export const MODE_LABEL = { data_only: "Data only", compact: "Compact", full: "Full" } as const;

export const safeUrl = (url: string | null | undefined): string | null => {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.toString() : null;
  } catch {
    return null;
  }
};
