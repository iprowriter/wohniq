"use client";

import type { Answers, CityFigure } from "@/lib/lifestyle/types";
import { LIMITS, budgetReferences, clampNumber, euro } from "@/lib/lifestyle/logic";

interface Props {
  answers: Answers;
  city: Record<string, CityFigure>;
  onChange: (next: Answers) => void;
}

function Stepper({
  value,
  onChange,
  min,
  max,
  step,
  label,
}: {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
  label: string;
}) {
  const btn =
    "flex h-9 w-9 items-center justify-center rounded-full border border-gray-200 text-lg text-gray-700 transition hover:border-indigo-300 hover:text-indigo-600 disabled:opacity-30";
  return (
    <div className="flex items-center gap-3" role="group" aria-label={label}>
      <button type="button" className={btn} onClick={() => onChange(clampNumber(value - step, min, max, step))} disabled={value <= min} aria-label={`Fewer ${label}`}>
        −
      </button>
      <span className="w-10 text-center text-lg font-semibold tabular-nums" aria-live="polite">
        {value}
      </span>
      <button type="button" className={btn} onClick={() => onChange(clampNumber(value + step, min, max, step))} disabled={value >= max} aria-label={`More ${label}`}>
        +
      </button>
    </div>
  );
}

export function BudgetFields({ answers, city, onChange }: Props) {
  const b = LIMITS.budget;
  const s = LIMITS.size;
  const refs = budgetReferences(city, answers.size_m2);
  return (
    <div className="space-y-7">
      <div>
        <div className="flex items-end justify-between">
          <label htmlFor="budget" className="text-base font-semibold text-gray-900">
            Monthly budget <span className="font-normal text-gray-500">(warm, all-in)</span>
          </label>
          <div className="flex items-baseline gap-1">
            <span className="text-gray-400">€</span>
            <input
              type="number"
              inputMode="numeric"
              aria-label="Budget in euros"
              min={b.min}
              max={b.max}
              step={b.step}
              value={answers.budget_eur}
              onChange={(e) => onChange({ ...answers, budget_eur: Number(e.target.value) })}
              onBlur={() => onChange({ ...answers, budget_eur: clampNumber(answers.budget_eur, b.min, b.max, b.step) })}
              className="w-24 rounded-lg border border-transparent bg-transparent text-right text-2xl font-bold tabular-nums text-gray-900 outline-none focus:border-indigo-300 focus:bg-indigo-50/40"
            />
          </div>
        </div>
        <input
          id="budget"
          type="range"
          className="lm-range mt-3 w-full"
          min={b.sliderMin}
          max={b.sliderMax}
          step={b.step}
          value={Math.min(Math.max(answers.budget_eur, b.sliderMin), b.sliderMax)}
          onChange={(e) => onChange({ ...answers, budget_eur: Number(e.target.value) })}
        />
        {refs.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {refs.map((r) => (
              <button
                key={r.label}
                type="button"
                onClick={() => onChange({ ...answers, budget_eur: clampNumber(r.value, b.min, b.max, b.step) })}
                className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600 transition hover:bg-indigo-50 hover:text-indigo-700"
                title="Use this as my budget"
              >
                {r.label}: <span className="font-semibold">{euro(r.value)}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="grid gap-7 sm:grid-cols-2">
        <div>
          <div className="flex items-end justify-between">
            <label htmlFor="size" className="text-base font-semibold text-gray-900">
              Flat size
            </label>
            <span className="text-2xl font-bold tabular-nums text-gray-900">
              {answers.size_m2}
              <span className="ml-1 text-base font-normal text-gray-400">m²</span>
            </span>
          </div>
          <input
            id="size"
            type="range"
            className="lm-range mt-3 w-full"
            min={s.sliderMin}
            max={s.sliderMax}
            step={s.step}
            value={Math.min(Math.max(answers.size_m2, s.sliderMin), s.sliderMax)}
            onChange={(e) => onChange({ ...answers, size_m2: Number(e.target.value) })}
          />
          <p className="mt-1 text-xs text-gray-400">Used to estimate typical rents in each area.</p>
        </div>
        <div>
          <p className="mb-2 text-base font-semibold text-gray-900">Rooms</p>
          <Stepper
            label="rooms"
            value={answers.rooms}
            min={LIMITS.rooms.min}
            max={LIMITS.rooms.max}
            step={LIMITS.rooms.step}
            onChange={(rooms) => onChange({ ...answers, rooms })}
          />
        </div>
      </div>
    </div>
  );
}
