"use client";

/** "Best areas for you": compact rows that open into the numbers, reasons and actions. */

import { useState } from "react";
import type { Persona, RegionResult, SourceOut, WeightOut } from "@/lib/lifestyle/types";
import { compareRows, MAX_COMPARE, tripDetail, tripLabel } from "@/lib/lifestyle/explorer";
import { sourceChip } from "@/lib/lifestyle/results";
import { euro } from "@/lib/format";
import { Button } from "@/components/ui/primitives";

type Props = {
  results: RegionResult[];
  weights: WeightOut[];
  persona: Persona | null;
  sources: Record<string, SourceOut>;
  destination?: string;
  open: string | null;
  hovered: string | null;
  compare: string[];
  remaining: number;
  onOpen: (key: string | null) => void;
  onHover: (key: string | null) => void;
  onToggleCompare: (key: string) => void;
  onExclude: (key: string) => void;
  onSeeFlats: (key: string, name: string) => void;
  onMore: () => void;
};

function Bars({ r }: { r: RegionResult }) {
  const factors = r.factors.filter((f) => f.weight > 0).sort((a, b) => b.weight - a.weight);
  return (
    <ul className="grid gap-x-5 gap-y-2.5 sm:grid-cols-2" aria-label="Score by what you weigh">
      {factors.map((f) => (
        <li key={f.attribute}>
          <div className="flex justify-between gap-2 text-[13px] text-text-body">
            <span className="truncate">{f.label}</span>
            <span className="tabular-nums text-text-muted">{Math.round(f.score * 100)}</span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-chip" role="img" aria-label={`${f.label}: ${Math.round(f.score * 100)} of 100`}>
            <div className="h-full rounded-full bg-accent" style={{ width: `${Math.round(f.score * 100)}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

function Row({ r, p }: { r: RegionResult; p: Props }) {
  const isOpen = p.open === r.key;
  const [data, setData] = useState(false);
  const trip = tripLabel(r, p.destination);
  const detail = tripDetail(r);
  const inCompare = p.compare.includes(r.key);
  return (
    <li
      id={`area-${r.key}`}
      data-testid="area-row"
      data-key={r.key}
      onMouseEnter={() => p.onHover(r.key)}
      onMouseLeave={() => p.onHover(null)}
      className={`scroll-mt-24 border-b border-line last:border-0 ${isOpen ? "bg-ground/60" : ""} ${p.hovered === r.key && !isOpen ? "bg-ground" : ""}`}
    >
      <h3>
        <button
          type="button"
          aria-expanded={isOpen}
          aria-controls={`area-detail-${r.key}`}
          onClick={() => p.onOpen(isOpen ? null : r.key)}
          className="grid min-h-[60px] w-full grid-cols-[32px_minmax(0,1fr)_auto] items-center gap-3 px-4 py-2.5 text-left sm:grid-cols-[32px_minmax(0,1.4fr)_1fr_1fr_auto]"
        >
          <span className={`flex h-7 w-7 items-center justify-center rounded-full border-2 text-[12px] font-bold ${isOpen ? "border-ink bg-ink text-white" : "border-ink text-ink"}`}>
            {r.rank}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-[15px] font-semibold text-text">{r.name}</span>
            <span className="block truncate text-[12.5px] text-text-muted">{r.district}</span>
            <span className="block truncate text-[12.5px] text-text-body sm:hidden">
              {euro(r.warm_rent_eur)} · <span className={r.fits_budget ? "text-ok" : "text-warn"}>{r.fits_budget ? "fits budget" : "over budget"}</span>
              {trip ? ` · ${trip}` : ""}
            </span>
          </span>
          <span className="hidden text-[13px] sm:block">
            <span className="font-semibold tabular-nums text-text">{euro(r.warm_rent_eur)} warm</span>
            <span className={`block text-[12px] ${r.fits_budget ? "text-ok" : "text-warn"}`}>{r.fits_budget ? "fits budget" : "over budget"}</span>
          </span>
          <span className="hidden text-[13px] sm:block">
            {trip ? (
              <>
                <span className="font-semibold tabular-nums text-text">{trip.split(" to ")[0]}</span>
                {trip.includes(" to ") && <span className="text-text-muted"> to {trip.split(" to ")[1]}</span>}
                {detail && <span className="block text-[12px] text-text-muted">{detail}</span>}
              </>
            ) : (
              <span className="text-text-faint">no trip set</span>
            )}
          </span>
          <span className="text-right">
            <span className="block text-[20px] font-bold tabular-nums text-text">{Math.round(r.score)}</span>
            <span className="block text-[11px] text-text-muted">match</span>
          </span>
        </button>
      </h3>
      {isOpen && (
        <div id={`area-detail-${r.key}`} className="grid gap-5 px-4 pb-5 pl-[60px] lg:grid-cols-2" data-testid="area-detail">
          <div className="flex flex-col gap-3">
            <p className="text-[13px] text-text-muted">{r.headline}</p>
            <Bars r={r} />
          </div>
          <div className="flex flex-col gap-3">
            <ul className="flex flex-col gap-2">
              {r.reasons.map((e) => (
                <li key={e.attribute} className="flex gap-2 text-[13.5px] leading-snug text-text-body">
                  <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-ok-text)" strokeWidth="2.4" className="mt-0.5 shrink-0"><path d="M5 12.5l4.5 4.5L19 7.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                  <span>
                    {e.text}{" "}
                    <span className="ml-1 rounded-sm bg-chip px-1.5 py-px text-[10.5px] font-medium text-text-muted">{sourceChip(p.sources[e.source_id])}</span>
                  </span>
                </li>
              ))}
              {r.caveats.map((c) => (
                <li key={c} className="flex gap-2 text-[13.5px] leading-snug text-warn">
                  <span aria-hidden="true" className="w-4 shrink-0 text-center font-bold">!</span>
                  {c}
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap gap-2">
              <Button variant="dark" onClick={() => p.onSeeFlats(r.key, r.name)}>See flats here</Button>
              <Button
                variant="outline"
                aria-pressed={inCompare}
                disabled={!inCompare && p.compare.length >= MAX_COMPARE}
                onClick={() => p.onToggleCompare(r.key)}
              >
                {inCompare ? "In compare" : "Compare"}
              </Button>
              <Button variant="ghost" onClick={() => p.onExclude(r.key)} aria-label={`Remove ${r.name} from my results`}>
                Not for me
              </Button>
            </div>
            <button type="button" onClick={() => setData((d) => !d)} aria-expanded={data} className="self-start text-[13px] text-accent underline underline-offset-2">
              The data behind this
            </button>
            {data && (
              <div className="flex flex-col gap-2 rounded-md bg-surface p-3 text-[12.5px] leading-relaxed text-text-body">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Sources</p>
                <ul className="flex flex-col gap-1">
                  {r.evidence.map((e) => (
                    <li key={e.attribute}>
                      <strong className="font-medium text-text">{e.label}:</strong> {e.text}{" "}
                      <span className="text-text-muted">({p.sources[e.source_id]?.title ?? e.source_id})</span>
                    </li>
                  ))}
                </ul>
                {r.notes.length > 0 && (
                  <ul className="flex flex-col gap-1 text-text-muted">
                    {r.notes.map((n) => <li key={n}>{n}</li>)}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

export function RankingList(p: Props) {
  return (
    <section aria-labelledby="best-areas" className="rounded-lg border border-line bg-surface" data-testid="ranking">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-4">
        <div>
          <h2 id="best-areas" className="text-[18px] font-semibold text-text">Best areas for you</h2>
          <p className="text-[13px] text-text-muted">Sorted by match. Open an area for the numbers, the reasons and its flats.</p>
        </div>
        {p.persona && (
          <div className="max-w-sm rounded-md bg-ink px-4 py-2.5 text-text-on-ink-soft" data-testid="persona">
            <p className="text-[14px] font-semibold text-white">{p.persona.title}</p>
            <p className="text-[12.5px] leading-snug text-text-on-ink-muted">{p.persona.tagline}</p>
          </div>
        )}
      </div>
      <ol>
        {p.results.map((r) => (
          <Row key={r.key} r={r} p={p} />
        ))}
      </ol>
      {p.remaining > 0 && (
        <div className="flex justify-center border-t border-line p-4">
          <Button variant="outline" onClick={p.onMore}>Show {Math.min(10, p.remaining)} more areas</Button>
        </div>
      )}
    </section>
  );
}

export function CompareAreas({
  regions,
  weights,
  destination,
  onRemove,
}: {
  regions: RegionResult[];
  weights: WeightOut[];
  destination?: string;
  onRemove: (key: string) => void;
}) {
  if (regions.length < 2) return null;
  const rows = compareRows(regions, weights, destination);
  return (
    <section aria-labelledby="compare-areas" className="rounded-lg border border-line bg-surface p-4" data-testid="compare-areas">
      <h2 id="compare-areas" className="mb-3 text-[18px] font-semibold text-text">Side by side</h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[480px] text-[14px]">
          <thead>
            <tr className="border-b border-line">
              <th className="py-2 pr-3 text-left text-[12px] font-semibold uppercase tracking-wide text-text-muted"><span className="sr-only">Measure</span></th>
              {regions.map((r) => (
                <th key={r.key} className="px-3 py-2 text-left">
                  <span className="block font-semibold text-text">{r.name}</span>
                  <button type="button" onClick={() => onRemove(r.key)} className="text-[12px] font-normal text-accent underline">Remove</button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label} className="border-b border-line last:border-0">
                <th scope="row" className="py-2 pr-3 text-left font-normal text-text-muted">{row.label}</th>
                {row.values.map((v, i) => (
                  <td key={i} className={`px-3 py-2 tabular-nums ${row.best.includes(i) ? "font-semibold text-ok" : "text-text"}`}>
                    {v}
                    {row.best.includes(i) && <span className="ml-1.5 rounded-sm bg-ok-bg px-1.5 py-px text-[11px] font-medium">best</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
