/**
 * Lifestyle explorer (design B, T9.6): the settings, the live ranking and the area compare.
 * Pure helpers, unit-tested. Ranking itself is the backend's deterministic engine
 * (ADR-0011); these only choose what to show and how to word it.
 */

import type { MatchResponse, RegionResult, WeightOut } from "./types.ts";

export const TRIP_OPTIONS = [20, 30, 45, 60] as const;
export const MAX_COMPARE = 3;
export const PAGE = 10;

/** Weights that count now (value > 0, highest first), and the rest behind "+N more". */
export function splitWeights(weights: WeightOut[]): { counted: WeightOut[]; rest: WeightOut[] } {
  const counted = weights.filter((w) => w.value > 0).sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));
  const rest = weights.filter((w) => w.value === 0).sort((a, b) => a.label.localeCompare(b.label));
  return { counted, rest };
}

/** "143 areas ranked · 12 fit your budget and trip" */
export function liveSummary(data: Pick<MatchResponse, "scores" | "total_regions" | "excluded">, hasTrip: boolean): string {
  const fit = data.scores.filter((s) => s.fits_budget && (s.within_commute ?? true)).length;
  const ranked = data.scores.length;
  const what = hasTrip ? "your budget and trip" : "your budget";
  const removed = data.excluded.length ? ` · ${data.excluded.length} removed` : "";
  return `${ranked} areas ranked · ${fit} fit ${what}${removed}`;
}

export function tripLabel(r: RegionResult, destination?: string): string | null {
  if (!r.commute) return null;
  return `${r.commute.minutes} min${destination ? ` to ${destination}` : ""}`;
}

export function tripDetail(r: RegionResult): string | null {
  const c = r.commute;
  if (!c) return null;
  if (c.estimated) return "estimated";
  if (c.changes == null) return null;
  return c.changes === 0 ? "direct" : `${c.changes} change${c.changes > 1 ? "s" : ""}`;
}

export interface CompareRow {
  label: string;
  values: string[];
  best: number[]; // column indexes with the best value (none for text rows)
}

/** Side-by-side rows for up to three areas; "best" marked per row, calmly. */
export function compareRows(regions: RegionResult[], weights: WeightOut[], destination?: string): CompareRow[] {
  const bestOf = (nums: (number | null)[], higher: boolean) => {
    const valid = nums.filter((n): n is number => n != null);
    if (valid.length < 2) return [];
    const target = higher ? Math.max(...valid) : Math.min(...valid);
    if (valid.every((n) => n === target)) return [];
    return nums.flatMap((n, i) => (n === target ? [i] : []));
  };
  const rows: CompareRow[] = [
    {
      label: "Match",
      values: regions.map((r) => String(Math.round(r.score))),
      best: bestOf(regions.map((r) => r.score), true),
    },
    {
      label: "Typical warm rent",
      values: regions.map((r) => `€${Math.round(r.warm_rent_eur).toLocaleString("en-GB")}${r.fits_budget ? " · fits" : " · over"}`),
      best: bestOf(regions.map((r) => r.warm_rent_eur), false),
    },
  ];
  if (regions.some((r) => r.commute)) {
    rows.push({
      label: destination ? `Trip to ${destination}` : "Trip",
      values: regions.map((r) => (r.commute ? `${r.commute.minutes} min` : "–")),
      best: bestOf(regions.map((r) => r.commute?.minutes ?? null), false),
    });
  }
  for (const w of weights.filter((x) => x.value > 0).sort((a, b) => b.value - a.value)) {
    if (w.attribute === "affordability" || w.attribute === "commute") continue;
    const scores = regions.map((r) => r.factors.find((f) => f.attribute === w.attribute)?.score ?? null);
    rows.push({
      label: w.label,
      values: scores.map((s) => (s == null ? "–" : `${Math.round(s)}/100`)),
      best: bestOf(scores, true),
    });
  }
  return rows;
}
