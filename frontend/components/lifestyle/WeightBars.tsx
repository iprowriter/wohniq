import type { WeightOut } from "@/lib/lifestyle/types";

/** Read-only view of the weights derived from the answers (the results page makes them editable). */
export function WeightBars({ weights, max = 8 }: { weights: WeightOut[]; max?: number }) {
  const active = weights.filter((w) => w.value > 0).sort((a, b) => b.value - a.value).slice(0, max);
  if (active.length === 0) return null;
  return (
    <ul className="space-y-2.5">
      {active.map((w, i) => (
        <li key={w.attribute} className="animate-fade-up" style={{ animationDelay: `${i * 50}ms` }}>
          <div className="flex items-baseline justify-between text-sm">
            <span className="font-medium text-gray-800">{w.label}</span>
            <span className="text-xs tabular-nums text-gray-400">{w.value}/5</span>
          </div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-gray-100">
            <div
              className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-[width] duration-700 ease-out"
              style={{ width: `${(w.value / 5) * 100}%` }}
            />
          </div>
          {w.reasons.length > 0 && (
            <p className="mt-1 truncate text-xs text-gray-400" title={w.reasons.join(" · ")}>
              because: {w.reasons[0].split(" → ").pop()}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
