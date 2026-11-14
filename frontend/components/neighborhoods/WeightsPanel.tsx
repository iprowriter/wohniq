"use client";

import type { NeighborhoodCatalog } from "@/lib/neighborhoods/types";
import { WEIGHT_LABELS } from "@/lib/neighborhoods/logic";

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
    <div className="rounded-2xl border border-gray-200 bg-white p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-900">What matters to you?</h3>
        <button type="button" onClick={onReset} className="text-xs text-gray-500 hover:text-indigo-700">
          Reset
        </button>
      </div>
      <p className="mt-1 text-xs text-gray-500">{catalog.overall.description}</p>
      <ul className="mt-3 grid gap-x-5 gap-y-2.5 sm:grid-cols-2">
        {catalog.categories.map((c) => {
          const v = draft[c.id] ?? 0;
          return (
            <li key={c.id}>
              <label className="flex items-center justify-between text-xs text-gray-700" htmlFor={`w-${c.id}`}>
                <span>
                  <span aria-hidden="true">{c.emoji}</span> {c.label}
                </span>
                <span className={`tabular-nums ${v === 0 ? "text-gray-400" : "font-medium text-indigo-700"}`}>
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
      <div className="mt-3 flex items-center justify-between gap-3 border-t border-gray-100 pt-3">
        <p className="text-xs text-gray-500" aria-live="polite">
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
          className="rounded-full bg-indigo-600 px-4 py-1.5 text-xs font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-400"
        >
          {updating ? "Updating…" : "Update ranking"}
        </button>
      </div>
    </div>
  );
}
