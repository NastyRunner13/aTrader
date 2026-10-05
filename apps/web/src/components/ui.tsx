"use client";

import { Check, Copy } from "lucide-react";
import { type ReactNode, useState } from "react";
import { ApiError } from "@/lib/api";

/** A shell command the user can copy. */
export function CopyCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="mt-3 flex max-w-full items-center gap-2 rounded-md border border-line bg-wash px-3 py-2">
      <code className="num min-w-0 flex-1 overflow-x-auto whitespace-nowrap font-mono text-xs text-ink">{command}</code>
      <button
        type="button"
        className="btn btn-quiet btn-icon btn-sm shrink-0"
        aria-label={copied ? "Copied" : "Copy command"}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(command);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          } catch {
            /* clipboard blocked: the command stays selectable */
          }
        }}
      >
        {copied ? <Check size={14} aria-hidden /> : <Copy size={14} aria-hidden />}
      </button>
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line-strong px-6 py-10 text-center">
      <p className="display text-xl">{title}</p>
      {children && <div className="prose-body mx-auto mt-2 !text-sm">{children}</div>}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}

export function Skeleton({ className = "", style }: { className?: string; style?: React.CSSProperties }) {
  return <div className={`skeleton ${className}`} style={style} aria-hidden />;
}

/** An error from the API. A connection failure gets the one fix that applies. */
export function ErrorNotice({ error, what }: { error: unknown; what: string }) {
  const offline = error instanceof ApiError && error.code === "offline";
  return (
    <div role="alert" className="rounded-lg border border-line bg-bad-wash px-5 py-4">
      <p className="font-semibold text-bad-ink">{offline ? "The aTrader API is not running" : `Could not load ${what}`}</p>
      <p className="mt-1 text-ink-2">
        {offline ? "Start it in a terminal, then reload this page." : error instanceof Error ? error.message : "Something went wrong."}
      </p>
      {offline && <CopyCommand command="uv run atrader serve" />}
    </div>
  );
}

export function Badge({ children, tone }: { children: ReactNode; tone?: "warn" | "bad" | "accent" }) {
  return (
    <span className="badge" data-tone={tone}>
      {children}
    </span>
  );
}

export function PageTitle({ title, children, aside }: { title: ReactNode; children?: ReactNode; aside?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <h1 className="display text-2xl">{title}</h1>
        {children && <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-ink-2">{children}</div>}
      </div>
      {aside && <div className="flex flex-wrap items-center gap-2">{aside}</div>}
    </header>
  );
}
