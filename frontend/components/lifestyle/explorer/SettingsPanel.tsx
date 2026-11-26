"use client";

/**
 * Lifestyle explorer settings (left column; behind "Adjust" on phones). Every change
 * re-ranks immediately. Answers stay in this tab only (ADR-0012).
 */

import Link from "next/link";
import { useState } from "react";
import type { Answers, Catalog, PresetOut, WeightOut } from "@/lib/lifestyle/types";
import { splitWeights, TRIP_OPTIONS } from "@/lib/lifestyle/explorer";
import { ProfileIcon } from "./icons";

type Props = {
  catalog: Catalog;
  answers: Answers;
  presetId: string | null;
  weights: WeightOut[];
  removed: { key: string; name: string }[];
  onPreset: (p: PresetOut) => void;
  onAnswers: (a: Answers) => void;
  onWeight: (attribute: string, value: number) => void;
  onResetProfile: () => void;
  onRestore: (key: string) => void;
  onClear: () => void;
};

const label = "text-[12px] font-semibold uppercase tracking-[0.06em] text-text-muted";
const input =
  "min-h-tap w-full rounded-md border border-input bg-surface px-3 text-[15px] text-text outline-none focus:border-accent focus:ring-2 focus:ring-accent/20";

function Segmented<T extends string | number>({
  name,
  options,
  value,
  onChange,
}: {
  name: string;
  options: { value: T; label: string }[];
  value: T | null | undefined;
  onChange: (v: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={name} className="grid overflow-hidden rounded-md border border-line-strong" style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={`min-h-tap border-l border-line-strong px-1 text-[13.5px] first:border-l-0 ${
            value === o.value ? "bg-accent-tint font-semibold text-accent" : "bg-surface text-text-body hover:bg-ground"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** 0–5 importance as six clickable steps; arrow keys work (radio group). */
function Importance({ w, onChange }: { w: WeightOut; onChange: (v: number) => void }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="min-w-0 truncate text-[14px] text-text" id={`imp-${w.attribute}`} title={w.reasons.join(" · ") || undefined}>
        {w.label}
      </span>
      <div
        role="radiogroup"
        aria-labelledby={`imp-${w.attribute}`}
        className="flex shrink-0 gap-1"
        onKeyDown={(e) => {
          if (e.key === "ArrowRight" || e.key === "ArrowUp") {
            e.preventDefault();
            onChange(Math.min(5, w.value + 1));
          } else if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
            e.preventDefault();
            onChange(Math.max(0, w.value - 1));
          }
        }}
      >
        {[0, 1, 2, 3, 4, 5].map((v) => (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={w.value === v}
            aria-label={`${w.label}: ${v === 0 ? "doesn't count" : `${v} of 5`}`}
            tabIndex={w.value === v ? 0 : -1}
            onClick={() => onChange(v)}
            className="flex h-[26px] w-[18px] items-center justify-center"
          >
            <span
              aria-hidden="true"
              className={`block rounded-[3px] ${v === 0 ? "h-[3px] w-3" : "h-[18px] w-[14px]"} ${
                v === 0 ? (w.value === 0 ? "bg-text-muted" : "bg-line-strong") : v <= w.value ? "bg-accent" : "bg-chip"
              }`}
            />
          </button>
        ))}
      </div>
    </div>
  );
}

export function SettingsPanel({
  catalog,
  answers,
  presetId,
  weights,
  removed,
  onPreset,
  onAnswers,
  onWeight,
  onResetProfile,
  onRestore,
  onClear,
}: Props) {
  const [more, setMore] = useState(false);
  const { counted, rest } = splitWeights(weights);
  const strictness = catalog.questions.find((q) => q.id === "budget_strictness");
  const universities = catalog.destinations.filter((d) => d.kind === "university");
  const hubs = catalog.destinations.filter((d) => d.kind === "hub");
  const set = (patch: Partial<Answers>) => onAnswers({ ...answers, ...patch });

  return (
    <div className="flex flex-col gap-5" data-testid="lifestyle-settings">
      <div>
        <h1 className="text-[20px] font-bold tracking-tight text-text">Lifestyle match</h1>
        <p className="text-[13px] text-text-muted">Change anything. The map and the ranking update as you go.</p>
      </div>

      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Profile">
        {catalog.presets.map((p) => (
          <button
            key={p.id}
            type="button"
            aria-pressed={presetId === p.id}
            onClick={() => onPreset(p)}
            className={`inline-flex min-h-[38px] items-center gap-1.5 rounded-full border px-3 text-[13.5px] ${
              presetId === p.id ? "border-ink bg-ink text-white" : "border-line-strong bg-surface text-text-body hover:border-input"
            }`}
          >
            <ProfileIcon id={p.id} size={15} />
            {p.label}
          </button>
        ))}
      </div>
      {presetId && (
        <button type="button" onClick={onResetProfile} className="-mt-3 self-start text-[13px] text-accent underline underline-offset-2">
          Reset to profile
        </button>
      )}

      <section className="flex flex-col gap-2.5 border-t border-line pt-4">
        <h2 className={label}>Your flat</h2>
        <div className="grid grid-cols-2 gap-2.5">
          <label className="flex flex-col gap-1 text-[12.5px] text-text-muted">
            Budget, warm (€/month)
            <input
              className={input}
              type="number"
              min={200}
              max={5000}
              step={50}
              value={answers.budget_eur}
              aria-label="Budget in euros"
              onChange={(e) => set({ budget_eur: Number(e.target.value) || answers.budget_eur })}
            />
          </label>
          <label className="flex flex-col gap-1 text-[12.5px] text-text-muted">
            Size (m²)
            <input
              className={input}
              type="number"
              min={10}
              max={250}
              value={answers.size_m2}
              aria-label="Size in square metres"
              onChange={(e) => set({ size_m2: Number(e.target.value) || answers.size_m2 })}
            />
          </label>
        </div>
        {strictness && (
          <>
            <span className="text-[12.5px] text-text-muted">Budget is</span>
            <Segmented
              name="Budget is"
              value={answers.budget_strictness ?? null}
              onChange={(v) => set({ budget_strictness: v })}
              options={strictness.options.map((o) => ({ value: o.id, label: o.id === "strict" ? "Firm" : o.id === "balanced" ? "Some room" : "Flexible" }))}
            />
          </>
        )}
      </section>

      <section className="flex flex-col gap-2.5 border-t border-line pt-4">
        <h2 className={label}>Your trip</h2>
        <label className="flex flex-col gap-1 text-[12.5px] text-text-muted">
          Where you go most
          <select
            className={input}
            value={answers.destination ?? ""}
            onChange={(e) => set({ destination: e.target.value || null })}
          >
            <option value="">Nowhere in particular</option>
            <optgroup label="Universities">
              {universities.map((d) => (
                <option key={d.id} value={d.id}>{d.short}</option>
              ))}
            </optgroup>
            <optgroup label="Hubs">
              {hubs.map((d) => (
                <option key={d.id} value={d.id}>{d.short}</option>
              ))}
            </optgroup>
          </select>
        </label>
        {answers.destination && (
          <>
            <span className="text-[12.5px] text-text-muted">Longest trip you accept</span>
            <Segmented
              name="Longest trip you accept"
              value={answers.max_commute_min}
              onChange={(v) => set({ max_commute_min: v })}
              options={TRIP_OPTIONS.map((m) => ({ value: m, label: `${m} min` }))}
            />
          </>
        )}
      </section>

      <section className="flex flex-col gap-2 border-t border-line pt-4" aria-labelledby="what-matters">
        <h2 id="what-matters" className={label}>What matters</h2>
        {counted.length === 0 && (
          <p className="rounded-md bg-warn-bg px-3 py-2 text-[13px] text-warn">Turn at least one thing up to rank areas.</p>
        )}
        {counted.map((w) => (
          <Importance key={w.attribute} w={w} onChange={(v) => onWeight(w.attribute, v)} />
        ))}
        {more && rest.map((w) => <Importance key={w.attribute} w={w} onChange={(v) => onWeight(w.attribute, v)} />)}
        {rest.length > 0 && (
          <button type="button" onClick={() => setMore((m) => !m)} className="self-start text-[13px] text-accent underline underline-offset-2">
            {more ? "Show fewer" : `+ ${rest.length} more things to weigh`}
          </button>
        )}
      </section>

      {removed.length > 0 && (
        <section className="flex flex-col gap-2 border-t border-line pt-4">
          <h2 className={label}>Removed areas</h2>
          <div className="flex flex-wrap gap-1.5">
            {removed.map((r) => (
              <button
                key={r.key}
                type="button"
                onClick={() => onRestore(r.key)}
                className="min-h-[34px] rounded-full border border-line-strong px-3 text-[13px] text-text-body hover:border-input"
                aria-label={`Bring back ${r.name}`}
              >
                {r.name} ↺
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="flex flex-col gap-2 border-t border-line pt-4">
        <h2 className={label}>Prefer questions?</h2>
        <Link href="/lifestyle/questions" className="inline-flex min-h-tap items-center justify-center gap-2 rounded-md border border-line-strong bg-surface px-3 text-[14px] font-medium text-text hover:bg-ground">
          Answer {catalog.questions.length} questions instead
        </Link>
        <p className="text-[12.5px] text-text-muted">Household, evenings, weekends and neighbours set the weights above for you.</p>
      </section>

      <section className="flex flex-col gap-2 border-t border-line pt-4">
        <p className="text-[12.5px] leading-relaxed text-text-muted">{catalog.privacy}</p>
        <button type="button" onClick={onClear} className="self-start text-[13px] text-text-body underline underline-offset-2 hover:text-text">
          Clear my answers
        </button>
      </section>
    </div>
  );
}
