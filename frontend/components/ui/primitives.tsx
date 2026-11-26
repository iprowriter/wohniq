/**
 * Berlin Ink building blocks: chips, buttons, verdict cards, comparison bars, source labels.
 *
 * Verdicts are calm (design rule): two states plus neutral (teal "ok", amber "warn", grey),
 * never red, and always carry words, so colour is never the only signal. Everything clickable
 * is at least 44 px tall.
 */

import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

export type Tone = "ok" | "warn" | "neutral" | "accent" | "ink";

const CHIP_TONE: Record<Tone, string> = {
  ok: "bg-ok-bg text-ok",
  warn: "bg-warn-bg text-warn",
  neutral: "bg-chip text-text-body",
  accent: "bg-accent-tint text-accent",
  ink: "bg-ink text-text-on-ink",
};

export function Chip({
  tone = "neutral",
  children,
  className = "",
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-sm px-2 py-0.5 text-[13px] font-medium leading-5 ${CHIP_TONE[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export type ButtonVariant = "primary" | "dark" | "outline" | "ghost";

const BUTTON: Record<ButtonVariant, string> = {
  primary: "bg-accent text-white hover:bg-accent-hover",
  dark: "bg-ink text-white hover:bg-[#1c2436]",
  outline: "border border-line-strong bg-surface text-text hover:border-input hover:bg-ground",
  ghost: "text-accent hover:bg-accent-tint",
};

export function buttonClass(variant: ButtonVariant = "primary", extra = "") {
  return `inline-flex min-h-tap items-center justify-center gap-2 rounded-md px-4 text-[15px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${BUTTON[variant]} ${extra}`;
}

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ComponentProps<"button"> & { variant?: ButtonVariant }) {
  return <button type="button" className={buttonClass(variant, className)} {...props} />;
}

export function ButtonLink({
  variant = "primary",
  className = "",
  ...props
}: ComponentProps<typeof Link> & { variant?: ButtonVariant }) {
  return <Link className={buttonClass(variant, className)} {...props} />;
}

/** Small uppercase source tag shown next to every figure ("Every number has a source"). */
export function SourceLabel({ children }: { children: ReactNode }) {
  return (
    <span className="text-[11px] font-medium uppercase tracking-wide text-text-faint">
      {children}
    </span>
  );
}

/** One of the three verdicts (fit, rent check, scam risk) on a listing. */
export function VerdictCard({
  label,
  value,
  detail,
  tone = "neutral",
  children,
}: {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  tone?: "ok" | "warn" | "neutral" | "ink";
  children?: ReactNode;
}) {
  const styles = {
    ok: "border-transparent bg-ok-bg text-ok-strong",
    warn: "border-transparent bg-warn-bg text-warn",
    neutral: "border-line bg-surface text-text",
    ink: "border-transparent bg-ink text-text-on-ink",
  }[tone];
  const sub = tone === "ink" ? "text-text-on-ink-muted" : tone === "neutral" ? "text-text-muted" : "";
  return (
    <div className={`flex min-w-0 flex-col gap-1 rounded-lg border p-4 ${styles}`}>
      <span className={`text-[13px] ${sub || "opacity-90"}`}>{label}</span>
      <span className="text-[22px] font-semibold leading-tight tracking-tight">{value}</span>
      {detail && <span className={`text-[13px] ${sub || "opacity-90"}`}>{detail}</span>}
      {children}
    </div>
  );
}

/** Where a value sits among Berlin's areas: a thin bar from 0 to 100. */
export function MeasureBar({ position, label }: { position: number; label?: string }) {
  const pct = Math.max(0, Math.min(100, position));
  return (
    <div
      className="h-1.5 w-full overflow-hidden rounded-full bg-chip"
      role="img"
      aria-label={label ?? `Position ${Math.round(pct)} of 100`}
    >
      <div className="h-full rounded-full bg-accent/70" style={{ width: `${pct}%` }} />
    </div>
  );
}

/** Page section heading with an optional one-line lede. */
export function SectionHeading({
  title,
  lede,
  as: Tag = "h2",
  action,
}: {
  title: ReactNode;
  lede?: ReactNode;
  as?: "h1" | "h2" | "h3";
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <Tag className="text-[22px] font-semibold tracking-tight text-text">{title}</Tag>
        {lede && <p className="mt-1 text-[15px] text-text-muted">{lede}</p>}
      </div>
      {action}
    </div>
  );
}
