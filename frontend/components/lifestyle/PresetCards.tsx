import type { PresetOut } from "@/lib/lifestyle/types";
import { euro } from "@/lib/lifestyle/logic";

const STYLE: Record<string, { emoji: string; tint: string }> = {
  student: { emoji: "🎓", tint: "from-sky-50 to-indigo-50" },
  young_professional: { emoji: "💼", tint: "from-violet-50 to-fuchsia-50" },
  family: { emoji: "👨‍👩‍👧", tint: "from-amber-50 to-orange-50" },
  remote_creative: { emoji: "🎨", tint: "from-pink-50 to-rose-50" },
  calm_green: { emoji: "🌳", tint: "from-emerald-50 to-teal-50" },
};

interface Props {
  presets: PresetOut[];
  selected: string | null;
  onPick: (preset: PresetOut) => void;
  onScratch: () => void;
}

export function PresetCards({ presets, selected, onPick, onScratch }: Props) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {presets.map((p, i) => {
        const style = STYLE[p.id] ?? { emoji: "✨", tint: "from-gray-50 to-gray-100" };
        const active = selected === p.id;
        return (
          <button
            key={p.id}
            type="button"
            onClick={() => onPick(p)}
            aria-pressed={active}
            style={{ animationDelay: `${i * 60}ms` }}
            className={`animate-fade-up group flex flex-col rounded-2xl border bg-gradient-to-br ${style.tint} p-5 text-left transition-all duration-200 hover:-translate-y-1 hover:shadow-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
              active ? "border-indigo-500 ring-2 ring-indigo-500" : "border-transparent"
            }`}
          >
            <span className="text-3xl transition-transform duration-200 group-hover:scale-110" aria-hidden="true">
              {style.emoji}
            </span>
            <span className="mt-3 font-semibold text-gray-900">{p.label}</span>
            <span className="mt-1 text-sm leading-relaxed text-gray-600">{p.blurb}</span>
            <span className="mt-3 text-xs text-gray-500">
              {euro(p.answers.budget_eur)} warm · {p.answers.size_m2} m²
            </span>
          </button>
        );
      })}
      <button
        type="button"
        onClick={onScratch}
        style={{ animationDelay: `${presets.length * 60}ms` }}
        className="animate-fade-up group flex flex-col rounded-2xl border-2 border-dashed border-gray-200 p-5 text-left transition-all duration-200 hover:-translate-y-1 hover:border-indigo-300 hover:bg-indigo-50/30 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
      >
        <span className="text-3xl transition-transform duration-200 group-hover:scale-110" aria-hidden="true">
          ✏️
        </span>
        <span className="mt-3 font-semibold text-gray-900">Start from scratch</span>
        <span className="mt-1 text-sm leading-relaxed text-gray-600">
          None of these? Answer every question your own way.
        </span>
        <span className="mt-3 text-xs font-medium text-indigo-600">
          Let&apos;s go <span className="inline-block transition-transform group-hover:translate-x-1">→</span>
        </span>
      </button>
    </div>
  );
}
