import type { Factor } from "@/lib/lifestyle/types";
import { percent } from "@/lib/lifestyle/results";

/** "Why this score": each factor's own score, its weight, and its share of the total. */
export function FactorBars({ factors }: { factors: Factor[] }) {
  return (
    <div>
      <div className="mb-2 grid grid-cols-[1fr_auto] text-[11px] uppercase tracking-wide text-gray-400">
        <span>Factor · your weight</span>
        <span>adds to score</span>
      </div>
      <ul className="space-y-2.5">
        {factors.map((f) => (
          <li key={f.attribute}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="text-gray-800">
                {f.label} <span className="text-xs text-gray-400">× {f.weight}</span>
              </span>
              <span className="text-xs font-semibold tabular-nums text-indigo-700">+{Math.round(f.contribution * 100)}</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-gray-100" title={`Scores ${percent(f.score)} on ${f.label.toLowerCase()}`}>
              <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500" style={{ width: percent(f.score) }} />
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs leading-relaxed text-gray-500">
        Each bar is how well the area does on that factor (fixed Berlin-wide scale). The total is the
        weighted average — your weights decide how much each factor counts.
      </p>
    </div>
  );
}
