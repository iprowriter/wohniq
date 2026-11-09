"use client";

import { useState } from "react";
import type { RegionResult, SourceOut } from "@/lib/lifestyle/types";
import { commuteLabel } from "@/lib/lifestyle/results";
import { euro } from "@/lib/lifestyle/logic";
import { ScoreRing } from "./ScoreRing";
import { SourceChip } from "./SourceChip";
import { FactorBars } from "./FactorBars";
import { DataBehind } from "./DataBehind";

interface Props {
  result: RegionResult;
  sources: Record<string, SourceOut>;
  destinationName?: string;
  selected: boolean;
  onSelect: (key: string) => void;
  onExclude: (key: string) => void;
  onSeeFlats: (key: string, name: string) => void;
  style?: React.CSSProperties;
}

type Panel = "why" | "data" | null;

export function RegionCard({ result: r, sources, destinationName, selected, onSelect, onExclude, onSeeFlats, style }: Props) {
  const [panel, setPanel] = useState<Panel>(null);
  const toggle = (p: Panel) => setPanel((cur) => (cur === p ? null : p));
  const tab = (p: Panel) =>
    `rounded-full px-3 py-1.5 text-xs font-medium transition ${
      panel === p ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
    }`;

  return (
    <article
      id={`region-${r.key}`}
      style={style}
      onMouseEnter={() => onSelect(r.key)}
      className={`animate-fade-up scroll-mt-24 rounded-2xl border bg-white p-5 transition-shadow ${
        selected ? "border-indigo-300 shadow-lg shadow-indigo-600/10 ring-1 ring-indigo-300" : "border-gray-200 hover:shadow-md"
      }`}
    >
      <div className="flex items-start gap-4">
        <ScoreRing score={r.score} />
        <div className="min-w-0 flex-1">
          <p className="text-xs text-gray-400">
            <span className="font-semibold text-indigo-600">#{r.rank}</span> · {r.district}
          </p>
          <h3 className="text-lg font-semibold leading-tight text-gray-900">{r.name}</h3>
          <p className="mt-1 text-sm text-gray-600">{r.headline}</p>
        </div>
        <button
          type="button"
          onClick={() => onExclude(r.key)}
          className="flex-shrink-0 rounded-full px-2.5 py-1 text-xs text-gray-400 transition hover:bg-red-50 hover:text-red-600"
          aria-label={`Remove ${r.name} from my results`}
          title="Not for me — remove this area"
        >
          ✕ Not for me
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <span
          className={`rounded-full px-2.5 py-1 font-medium ${r.fits_budget ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800"}`}
          title="Typical warm rent for your flat size (district median + running costs)"
        >
          {r.fits_budget ? "Fits budget" : "Over budget"} · ≈ {euro(r.warm_rent_eur)}/mo
        </span>
        {r.commute && (
          <span
            className={`rounded-full px-2.5 py-1 font-medium ${
              r.within_commute === false ? "bg-amber-50 text-amber-800" : "bg-sky-50 text-sky-700"
            }`}
          >
            🚆 {commuteLabel(r.commute.minutes, r.commute.changes, r.commute.estimated)}
            {destinationName ? ` to ${destinationName}` : ""}
          </span>
        )}
        <span className="rounded-full bg-gray-50 px-2.5 py-1 text-gray-500">{r.population.toLocaleString("en-US")} residents</span>
      </div>

      {r.reasons.length > 0 && (
        <ul className="mt-4 space-y-1.5 text-sm text-gray-700">
          {r.reasons.map((e) => (
            <li key={e.attribute} className="flex gap-2">
              <span className="mt-0.5 text-emerald-500" aria-hidden="true">✓</span>
              <span>
                {e.text}
                <SourceChip source={sources[e.source_id]} />
              </span>
            </li>
          ))}
        </ul>
      )}
      {r.caveats.length > 0 && (
        <ul className="mt-3 space-y-1 rounded-xl bg-amber-50/70 px-3 py-2 text-xs leading-relaxed text-amber-900">
          {r.caveats.map((c) => (
            <li key={c}>• {c}</li>
          ))}
        </ul>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-gray-100 pt-4">
        <button type="button" className={tab("why")} aria-expanded={panel === "why"} onClick={() => toggle("why")}>
          Why this score
        </button>
        <button type="button" className={tab("data")} aria-expanded={panel === "data"} onClick={() => toggle("data")}>
          The data behind this
        </button>
        <button
          type="button"
          onClick={() => onSeeFlats(r.key, r.name)}
          className="ml-auto rounded-full bg-gray-900 px-4 py-1.5 text-xs font-semibold text-white transition hover:bg-gray-700"
        >
          See flats here →
        </button>
      </div>
      {panel && (
        <div className="animate-fade-up mt-4 rounded-xl border border-gray-100 p-4">
          {panel === "why" ? <FactorBars factors={r.factors} /> : <DataBehind evidence={r.evidence} notes={r.notes} sources={sources} />}
        </div>
      )}
    </article>
  );
}
