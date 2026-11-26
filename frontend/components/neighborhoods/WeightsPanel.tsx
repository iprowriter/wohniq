"use client";

import type { NeighborhoodCatalog } from "@/lib/neighborhoods/types";
import { WEIGHT_LABELS } from "@/lib/neighborhoods/logic";
import { CategoryIcon } from "@/components/lifestyle/explorer/icons";

interface Props {
  catalog: NeighborhoodCatalog;
  draft: Record<string, number>;
  pending: number; // sliders changed since the last update
  updating: boolean;
  canUpdate: boolean;
  onChange: (id: string, value: number) => void;
  onUpdate: () => void;
  onReset: () => void;
}

/** "What matters to you": category weights for the overall score, applied on Update. */
export function WeightsPanel({ catalog, draft, pending, updating, canUpdate, onChange, onUpdate, onReset }: Props) {
  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-text">What matters to you?</h3>
        <button type="button" onClick={onReset} className="text-xs text-text-muted hover:text-accent">
          Reset
        </button>
      </div>
      <p className="mt-1 text-xs text-text-muted">{catalog.overall.description}</p>
      <ul className="mt-3 grid gap-x-5 gap-y-2.5 sm:grid-cols-2">
        {catalog.categories.map((c) => {
          const v = draft[c.id] ?? 0;
          return (
            <li key={c.id}>
              <label className="flex items-center justify-between text-xs text-text-body" htmlFor={`w-${c.id}`}>
                <span>
                  <CategoryIcon id={c.id} size={15} /> {c.label}
                </span>
                <span className={`tabular-nums ${v === 0 ? "text-text-muted" : "font-medium text-accent"}`}>
                  {WEIGHT_LABELS[v]}
                </span>
              </label>
              <input
                id={`w-${c.id}`}
                type="range"
                min={0}
                max={catalog.max_weight}
                step={1}
                value={v}
                onChange={(e) => onChange(c.id, Number(e.target.value))}
                className="lm-range mt-1 w-full"
                aria-valuetext={WEIGHT_LABELS[v]}
              />
            </li>
          );
        })}
      </ul>
      <div className="mt-3 flex items-center justify-between gap-3 border-t border-line pt-3">
        <p className="text-xs text-text-muted" aria-live="polite">
          {!canUpdate && pending > 0
            ? "Turn at least one slider up."
            : pending > 0
              ? `${pending} change${pending > 1 ? "s" : ""} not applied yet`
              : "Ranking is up to date"}
        </p>
        <button
          type="button"
          onClick={onUpdate}
          disabled={!canUpdate || pending === 0 || updating}
          className="rounded-full bg-accent px-4 py-1.5 text-xs font-semibold text-white transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:bg-line disabled:text-text-muted"
        >
          {updating ? "Updating…" : "Update ranking"}
        </button>
      </div>
    </div>
  );
}
