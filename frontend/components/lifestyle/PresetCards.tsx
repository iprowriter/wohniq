import type { PresetOut } from "@/lib/lifestyle/types";
import { euro } from "@/lib/lifestyle/logic";
import { ProfileIcon } from "@/components/lifestyle/explorer/icons";


interface Props {
  presets: PresetOut[];
  selected: string | null;
  onPick: (preset: PresetOut) => void;
  onScratch: () => void;
}

export function PresetCards({ presets, selected, onPick, onScratch }: Props) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {presets.map((p) => {
        const active = selected === p.id;
        return (
          <button
            key={p.id}
            type="button"
            onClick={() => onPick(p)}
            aria-pressed={active}
            className={`group flex flex-col rounded-md border bg-surface p-5 text-left transition-colors hover:border-accent hover:bg-accent-tint/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
              active ? "border-accent ring-2 ring-accent" : "border-line"
            }`}
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-md bg-accent-tint text-accent">
              <ProfileIcon id={p.id} size={20} />
            </span>
            <span className="mt-3 font-semibold text-text">{p.label}</span>
            <span className="mt-1 text-sm leading-relaxed text-text-body">{p.blurb}</span>
            <span className="mt-3 text-xs text-text-muted">
              {euro(p.answers.budget_eur)} warm · {p.answers.size_m2} m²
            </span>
          </button>
        );
      })}
      <button
        type="button"
        onClick={onScratch}
        className="group flex flex-col rounded-md border-2 border-dashed border-line-strong p-5 text-left transition-colors hover:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-md bg-chip text-text-body">
          <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 20h4L19 9l-4-4L4 16v4z" /><path d="M13.5 6.5l4 4" /></svg>
        </span>
        <span className="mt-3 font-semibold text-text">Start from scratch</span>
        <span className="mt-1 text-sm leading-relaxed text-text-body">
          None of these? Answer every question your own way.
        </span>
        <span className="mt-3 text-xs font-medium text-accent">
          Let&apos;s go <span className="inline-block transition-transform group-hover:translate-x-1">→</span>
        </span>
      </button>
    </div>
  );
}
