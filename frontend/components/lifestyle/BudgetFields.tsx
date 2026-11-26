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
    "flex h-9 w-9 items-center justify-center rounded-full border border-line text-lg text-text-body transition hover:border-accent/50 hover:text-accent disabled:opacity-30";
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
          <label htmlFor="budget" className="text-base font-semibold text-text">
            Monthly budget <span className="font-normal text-text-muted">(warm, all-in)</span>
          </label>
          <div className="flex items-baseline gap-1">
            <span className="text-text-muted">€</span>
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
              className="w-24 rounded-lg border border-transparent bg-transparent text-right text-2xl font-bold tabular-nums text-text outline-none focus:border-accent/50 focus:bg-accent-tint/40"
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
                className="rounded-full bg-chip px-3 py-1 text-xs text-text-body transition hover:bg-accent-tint hover:text-accent"
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
            <label htmlFor="size" className="text-base font-semibold text-text">
              Flat size
            </label>
            <span className="text-2xl font-bold tabular-nums text-text">
              {answers.size_m2}
              <span className="ml-1 text-base font-normal text-text-muted">m²</span>
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
          <p className="mt-1 text-xs text-text-muted">Used to estimate typical rents in each area.</p>
        </div>
        <div>
          <p className="mb-2 text-base font-semibold text-text">Rooms</p>
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
