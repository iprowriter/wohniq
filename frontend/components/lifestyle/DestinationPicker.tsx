"use client";

import type { Answers, DestinationOut, QuestionOut } from "@/lib/lifestyle/types";
import { LIMITS, groupDestinations, setDestination } from "@/lib/lifestyle/logic";
import { OptionGroup } from "./OptionGroup";

interface Props {
  answers: Answers;
  destinations: DestinationOut[];
  frequency?: QuestionOut;
  labels: Record<string, string>;
  onChange: (next: Answers) => void;
}

function Pill({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-xl border px-3 py-2 text-left text-sm transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
        active
          ? "border-accent bg-accent text-white shadow-md shadow-accent/20"
          : "border-line bg-white text-text-body hover:-translate-y-0.5 hover:border-accent/50"
      }`}
    >
      {children}
    </button>
  );
}

export function DestinationPicker({ answers, destinations, frequency, labels, onChange }: Props) {
  const groups = groupDestinations(destinations);
  const c = LIMITS.commute;
  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <p className="text-base font-semibold text-text">Where do you go most?</p>
        <p className="-mt-1 text-xs text-text-muted">
          Pick from the list — we never ask for your address. Commute times come from the VBB timetable.
        </p>
        {[
          { title: "Universities & campuses", items: groups.university },
          { title: "City hubs", items: groups.hub },
        ].map((g) => (
          <div key={g.title}>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">{g.title}</p>
            <div className="flex flex-wrap gap-2">
              {g.items.map((d) => (
                <Pill
                  key={d.id}
                  active={answers.destination === d.id}
                  onClick={() => onChange(setDestination(answers, answers.destination === d.id ? null : d.id))}
                >
                  <span title={d.name}>{d.short}</span>
                </Pill>
              ))}
            </div>
          </div>
        ))}
        <Pill active={!answers.destination} onClick={() => onChange(setDestination(answers, null))}>
          No regular destination
        </Pill>
      </div>

      {answers.destination && (
        <div className="animate-fade-up space-y-6 rounded-2xl bg-accent-tint/50 p-4">
          {frequency && (
            <OptionGroup question={{ ...frequency, help: null }} answers={answers} labels={labels} onChange={onChange} />
          )}
          <div>
            <div className="flex items-end justify-between">
              <label htmlFor="commute" className="text-base font-semibold text-text">
                Longest commute you&apos;d accept
              </label>
              <span className="text-2xl font-bold tabular-nums text-text">
                {answers.max_commute_min}
                <span className="ml-1 text-base font-normal text-text-muted">min</span>
              </span>
            </div>
            <input
              id="commute"
              type="range"
              className="lm-range mt-3 w-full"
              min={c.min}
              max={c.sliderMax}
              step={c.step}
              value={Math.min(answers.max_commute_min, c.sliderMax)}
              onChange={(e) => onChange({ ...answers, max_commute_min: Number(e.target.value) })}
            />
            <p className="mt-1 text-xs text-text-muted">Areas beyond this are still shown, just ranked lower.</p>
          </div>
        </div>
      )}
    </div>
  );
}
