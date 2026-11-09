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
      className={`rounded-xl border px-3 py-2 text-left text-sm transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
        active
          ? "border-indigo-600 bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
          : "border-gray-200 bg-white text-gray-700 hover:-translate-y-0.5 hover:border-indigo-300"
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
        <p className="text-base font-semibold text-gray-900">Where do you go most?</p>
        <p className="-mt-1 text-xs text-gray-500">
          Pick from the list — we never ask for your address. Commute times come from the VBB timetable.
        </p>
        {[
          { title: "🎓 Universities & campuses", items: groups.university },
          { title: "📍 City hubs", items: groups.hub },
        ].map((g) => (
          <div key={g.title}>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">{g.title}</p>
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
        <div className="animate-fade-up space-y-6 rounded-2xl bg-indigo-50/50 p-4">
          {frequency && (
            <OptionGroup question={{ ...frequency, help: null }} answers={answers} labels={labels} onChange={onChange} />
          )}
          <div>
            <div className="flex items-end justify-between">
              <label htmlFor="commute" className="text-base font-semibold text-gray-900">
                Longest commute you'd accept
              </label>
              <span className="text-2xl font-bold tabular-nums text-gray-900">
                {answers.max_commute_min}
                <span className="ml-1 text-base font-normal text-gray-400">min</span>
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
            <p className="mt-1 text-xs text-gray-500">Areas beyond this are still shown, just ranked lower.</p>
          </div>
        </div>
      )}
    </div>
  );
}
