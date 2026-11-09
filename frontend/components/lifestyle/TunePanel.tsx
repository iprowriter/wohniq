"use client";

import type { AttributeOut, WeightOut } from "@/lib/lifestyle/types";

const LEVELS = ["Off", "A little", "Somewhat", "Important", "Very", "Essential"];

interface Props {
  attributes: AttributeOut[];
  base: WeightOut[]; // derived from the answers, with reasons
  draft: Record<string, number>;
  pending: number;
  canUpdate: boolean;
  updating: boolean;
  unscored: Record<string, string>;
  removed: { key: string; name: string }[];
  onChange: (attr: string, value: number) => void;
  onReset: () => void;
  onUpdate: () => void;
  onRestore: (key: string) => void;
}

export function TunePanel({
  attributes,
  base,
  draft,
  pending,
  canUpdate,
  updating,
  unscored,
  removed,
  onChange,
  onReset,
  onUpdate,
  onRestore,
}: Props) {
  const reasons = Object.fromEntries(base.map((w) => [w.attribute, w]));
  const groups = [
    { title: "Your basics", items: attributes.filter((a) => a.kind === "personal") },
    { title: "Neighbourhood", items: attributes.filter((a) => a.kind === "area") },
  ];

  return (
    <section aria-labelledby="tune-title" className="rounded-2xl border border-gray-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 id="tune-title" className="font-semibold text-gray-900">
          🎛️ Tune your match
        </h2>
        <button
          type="button"
          onClick={onReset}
          className="whitespace-nowrap text-xs text-gray-400 hover:text-indigo-600"
          title="Set every slider back to what your answers imply"
        >
          ↺ Reset
        </button>
      </div>
      <p className="mt-1 text-xs text-gray-500">How much should each thing count? 0 = not at all, 5 = essential.</p>

      <div className="mt-4 max-h-[26rem] space-y-5 overflow-y-auto pr-1">
        {groups.map((g) => (
          <div key={g.title}>
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-gray-400">{g.title}</p>
            <ul className="space-y-3">
              {g.items.map((a) => {
                const value = draft[a.id] ?? 0;
                const derived = reasons[a.id]?.value ?? 0;
                const changed = value !== derived;
                const why = reasons[a.id]?.reasons?.[0]?.split(" → ").pop();
                const id = `w-${a.id}`;
                return (
                  <li key={a.id}>
                    <div className="flex items-baseline justify-between gap-2">
                      <label htmlFor={id} className="text-sm font-medium text-gray-800" title={a.description}>
                        {a.label}
                      </label>
                      <span className={`text-xs tabular-nums ${value === 0 ? "text-gray-300" : "text-indigo-700"}`}>
                        {LEVELS[value]}
                      </span>
                    </div>
                    <input
                      id={id}
                      type="range"
                      min={0}
                      max={5}
                      step={1}
                      value={value}
                      onChange={(e) => onChange(a.id, Number(e.target.value))}
                      className="lm-range w-full"
                      aria-valuetext={`${a.label}: ${LEVELS[value]}`}
                    />
                    <p className="truncate text-[11px] text-gray-400" title={why}>
                      {changed ? (
                        <span className="font-medium text-violet-600">Set by you</span>
                      ) : why ? (
                        <>from your answer: {why}</>
                      ) : (
                        a.description
                      )}
                    </p>
                    {unscored[a.id] && value > 0 && <p className="text-[11px] text-amber-700">{unscored[a.id]}</p>}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>

      {removed.length > 0 && (
        <div className="mt-4 border-t border-gray-100 pt-3">
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-gray-400">Removed areas</p>
          <div className="flex flex-wrap gap-2">
            {removed.map((r) => (
              <button
                key={r.key}
                type="button"
                onClick={() => onRestore(r.key)}
                className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600 hover:bg-indigo-50 hover:text-indigo-700"
                title="Bring this area back"
              >
                {r.name} ↺
              </button>
            ))}
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={onUpdate}
        disabled={!canUpdate || updating}
        className="mt-4 w-full rounded-full bg-gradient-to-r from-indigo-600 to-violet-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-600/25 transition hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
      >
        {updating ? "Updating…" : pending > 0 ? `Update results (${pending} change${pending > 1 ? "s" : ""})` : "Results are up to date"}
      </button>
    </section>
  );
}
