"use client";

import type { ReactNode } from "react";
import type { RankedArea } from "@/lib/neighborhoods/types";
import { rankColor, rankTextColor, tierBadge } from "@/lib/neighborhoods/logic";

interface Props {
  area: RankedArea;
  total: number;
  bestLabel: string | null;
  worstLabel: string | null;
  selected: boolean;
  onSelect: (key: string) => void;
  onHover: (key: string | null) => void;
  children?: ReactNode; // the detail panel when selected
}

/** One ranked area in the list; expands into its detail when selected. */
export function AreaRow({ area: a, total, bestLabel, worstLabel, selected, onSelect, onHover, children }: Props) {
  const badge = tierBadge(a.tier, bestLabel, worstLabel);
  return (
    <li
      id={`area-${a.key}`}
      data-key={a.key}
      onMouseEnter={() => onHover(a.key)}
      onMouseLeave={() => onHover(null)}
      className={`scroll-mt-40 rounded-2xl border bg-white transition-shadow ${
        selected
          ? "border-accent/50 shadow-lg shadow-accent/10 ring-1 ring-accent/40"
          : "border-line hover:shadow-md"
      }`}
    >
      <button
        type="button"
        onClick={() => onSelect(a.key)}
        aria-expanded={selected}
        aria-label={`#${a.rank} ${a.name}, ${a.district}`}
        className="flex w-full items-start gap-3 rounded-2xl p-3.5 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <span
          className="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl text-sm font-bold tabular-nums"
          style={{
            background: rankColor(a.rank, total),
            color: rankTextColor(a.rank, total),
          }}
        >
          {a.rank}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-2">
            <span className="truncate font-semibold text-text">{a.name}</span>
            <span
              className="flex-shrink-0 text-sm font-semibold tabular-nums text-text"
              title="Score 0–100 (Berlin percentile)"
            >
              {Math.round(a.score)}
            </span>
          </span>
          <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-text-muted">
            <span className="truncate">
              {a.area_group} · {a.district}
            </span>
            {badge && (
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${badge.className}`}>
                {badge.text}
              </span>
            )}
          </span>
          {a.headline && (
            <span className="mt-1 block text-xs text-text-body">
              {a.headline.label}: <span className="font-medium tabular-nums text-text">{a.headline.text}</span>
            </span>
          )}
          <span className="mt-2 block h-1 overflow-hidden rounded-full bg-chip" aria-hidden="true">
            <span
              className="block h-full rounded-full"
              style={{
                width: `${a.score}%`,
                background: rankColor(a.rank, total),
              }}
            />
          </span>
        </span>
      </button>
      {selected && children && <div className="px-3.5 pb-3.5">{children}</div>}
    </li>
  );
}
