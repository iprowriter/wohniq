// Pure logic for the Lifestyle Match results page (no React, no fetch, no DOM).
// Unit-tested in tests/lifestyle-results.test.ts.

import type { Answers, SourceOut, WeightOut } from "./types";
import type { StorageLike } from "./logic";

// --- Weights: the user's adjustments ---------------------------------------------------

/** Weights as the answers imply them (ignoring any user overrides). */
export function weightMap(weights: WeightOut[]): Record<string, number> {
  return Object.fromEntries(weights.map((w) => [w.attribute, w.value]));
}

/**
 * Only the weights the user actually changed, relative to what their answers imply.
 * Sending just these keeps "because of your answer …" intact for everything else.
 */
export function weightOverrides(
  base: Record<string, number>,
  draft: Record<string, number>,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [attr, value] of Object.entries(draft)) {
    if ((base[attr] ?? 0) !== value) out[attr] = value;
  }
  return out;
}

export function sameWeights(a: Record<string, number>, b: Record<string, number>): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of keys) if ((a[k] ?? 0) !== (b[k] ?? 0)) return false;
  return true;
}

/** Number of sliders whose value differs from the last applied result. */
export function pendingChanges(applied: Record<string, number>, draft: Record<string, number>): number {
  const keys = new Set([...Object.keys(applied), ...Object.keys(draft)]);
  let n = 0;
  for (const k of keys) if ((applied[k] ?? 0) !== (draft[k] ?? 0)) n += 1;
  return n;
}

export function setWeight(draft: Record<string, number>, attr: string, value: number): Record<string, number> {
  const v = Math.max(0, Math.min(5, Math.round(value)));
  return { ...draft, [attr]: v };
}

export function activeCount(weights: Record<string, number>): number {
  return Object.values(weights).filter((v) => v > 0).length;
}

// --- Removed areas ----------------------------------------------------------------------

export function addExcluded(list: string[], key: string): string[] {
  return list.includes(key) ? list : [...list, key];
}

export function removeExcluded(list: string[], key: string): string[] {
  return list.filter((k) => k !== key);
}

// --- Map colours ------------------------------------------------------------------------

/** Sequential scale (light → deep indigo) in five bands of match score. */
export const SCORE_BANDS: { min: number; color: string; label: string }[] = [
  { min: 80, color: "#3730a3", label: "80+" },
  { min: 70, color: "#4f46e5", label: "70–79" },
  { min: 60, color: "#818cf8", label: "60–69" },
  { min: 50, color: "#c7d2fe", label: "50–59" },
  { min: 0, color: "#eef2ff", label: "< 50" },
];
export const EXCLUDED_COLOR = "#e5e7eb";

export function scoreColor(score: number | null | undefined): string {
  if (score == null) return EXCLUDED_COLOR;
  return (SCORE_BANDS.find((b) => score >= b.min) ?? SCORE_BANDS[SCORE_BANDS.length - 1]).color;
}

// --- Sources & formatting -----------------------------------------------------------------

export function sourceIndex(sources: SourceOut[]): Record<string, SourceOut> {
  return Object.fromEntries(sources.map((s) => [s.id, s]));
}

/** Short publisher names for source chips (the full name is in the tooltip and panel). */
const SHORT_PUBLISHER: Record<string, string> = {
  pks_kriminalitaetsatlas: "Polizei Berlin",
  afs_einwohnerregister_2024: "Statistik Berlin-Brandenburg",
  senstadt_betriebskosten_2026: "Senate of Berlin",
  ibb_wohnungsmarktbericht_2025: "IBB",
  ibb_tabellenband_2025: "IBB",
  senstadt_lor_2021: "LOR 2021",
  umweltgerechtigkeitsatlas_2023_2024: "Umweltatlas",
  mmi_studentisches_wohnen_sose_2025: "Moses Mendelssohn Inst.",
  openstreetmap_geofabrik: "OpenStreetMap",
  vbb_gtfs: "VBB timetable",
};

/** "noise 2022 · air 2023 · green space 2020" → "2020–2023"; "2025" stays "2025". */
export function yearSpan(text: string): string {
  const years = (text.match(/\d{4}/g) ?? []).map(Number);
  if (years.length === 0) return text;
  const lo = Math.min(...years);
  const hi = Math.max(...years);
  return lo === hi ? String(lo) : `${lo}–${hi}`;
}

/** Short chip label for a source, e.g. "Polizei Berlin · 2023–2025". */
export function sourceChip(source: SourceOut | undefined): string {
  if (!source) return "Source";
  const publisher = SHORT_PUBLISHER[source.id] ?? source.publisher.split(/[(,;]/)[0].trim();
  return `${publisher} · ${yearSpan(source.data_year)}`;
}

export function commuteLabel(minutes: number, changes?: number | null, estimated = false): string {
  const base = `≈ ${minutes} min`;
  if (estimated || changes == null) return base;
  return changes === 0 ? `${base}, direct` : `${base}, ${changes} change${changes > 1 ? "s" : ""}`;
}

export function percent(x: number): string {
  return `${Math.round(x * 100)}%`;
}

// --- Session storage for adjustments (current tab only, ADR-0012) ---------------------------

export const RESULTS_KEY = "wohniq_lifestyle_results";
const VERSION = 1;

export interface Adjustments {
  overrides: Record<string, number>;
  excluded: string[];
}

/** Identifies a set of answers, so slider overrides made for old answers are dropped. */
export function answersFingerprint(a: Answers): string {
  const keys = Object.keys(a).sort() as (keyof Answers)[];
  return JSON.stringify(keys.map((k) => [k, a[k] ?? null]));
}

export function saveAdjustments(storage: StorageLike, adj: Adjustments, answers: Answers): void {
  try {
    storage.setItem(RESULTS_KEY, JSON.stringify({ v: VERSION, answers: answersFingerprint(answers), ...adj }));
  } catch {
    // in-memory only
  }
}

/**
 * Restore the user's adjustments. Removed areas are kept; weight overrides only if
 * they were made for these exact answers (changed answers → fresh weights).
 */
export function loadAdjustments(storage: StorageLike, answers: Answers): Adjustments {
  const empty: Adjustments = { overrides: {}, excluded: [] };
  try {
    const raw = storage.getItem(RESULTS_KEY);
    if (!raw) return empty;
    const data = JSON.parse(raw);
    if (!data || data.v !== VERSION) return empty;
    const overrides: Record<string, number> = {};
    const sameAnswers = data.answers === answersFingerprint(answers);
    if (sameAnswers && data.overrides && typeof data.overrides === "object") {
      for (const [k, v] of Object.entries(data.overrides)) {
        if (typeof v === "number" && Number.isInteger(v) && v >= 0 && v <= 5) overrides[k] = v;
      }
    }
    const excluded = Array.isArray(data.excluded)
      ? data.excluded.filter((k: unknown) => typeof k === "string" && /^\d{6}$/.test(k))
      : [];
    return { overrides, excluded };
  } catch {
    return empty;
  }
}

export function clearAdjustments(storage: StorageLike): void {
  try {
    storage.removeItem(RESULTS_KEY);
  } catch {
    // nothing to clear
  }
}
