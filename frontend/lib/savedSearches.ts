/**
 * Saved searches, kept in this browser only (no account, T9.7, ADR-0020). Only the flat
 * search is saved, and only when the user presses Save. A versioned record; broken or
 * foreign data reads as empty. "New since last time" compares the result ids of this run
 * with the ids the user saw on the previous run.
 *
 * Also: download and import of all saved items (flats + searches) as one small JSON file.
 */

import { SORT_LABELS, toQuery, type SearchParams, type SortKey } from "./results.ts";

const KEY = "wohniq_saved_searches_v1";
export const SEARCHES_EVENT = "wohniq:saved-searches";
export const MAX_SEARCHES = 30;
const MAX_IDS = 200;
const SORTS = Object.keys(SORT_LABELS) as SortKey[];

export interface SavedSearch {
  id: string;
  name: string;
  q: string;
  fair: boolean;
  sort: SortKey;
  budget?: number;
  savedAt: string; // ISO
  lastRunAt: string; // ISO
  lastCount: number;
  lastIds: string[];
}

type Stored = { v: 1; searches: SavedSearch[] };

/** Two searches are the same when they ask the same thing (sort/filter only reorder). */
export function searchKey(p: { q: string; budget?: number | null }): string {
  return `${p.q.trim().toLowerCase().replace(/\s+/g, " ")}|${p.budget ?? ""}`;
}

function clean(x: unknown): SavedSearch | null {
  if (!x || typeof x !== "object") return null;
  const s = x as Record<string, unknown>;
  if (typeof s.q !== "string" || !s.q.trim() || typeof s.id !== "string") return null;
  const ids = Array.isArray(s.lastIds) ? s.lastIds.filter((i): i is string => typeof i === "string").slice(0, MAX_IDS) : [];
  const date = (d: unknown) => (typeof d === "string" && !Number.isNaN(Date.parse(d)) ? d : new Date(0).toISOString());
  return {
    id: s.id,
    name: typeof s.name === "string" && s.name.trim() ? s.name.trim().slice(0, 80) : s.q.trim(),
    q: s.q.trim().slice(0, 300),
    fair: s.fair === true,
    sort: SORTS.includes(s.sort as SortKey) ? (s.sort as SortKey) : "fit",
    budget: typeof s.budget === "number" && s.budget > 0 ? s.budget : undefined,
    savedAt: date(s.savedAt),
    lastRunAt: date(s.lastRunAt),
    lastCount: typeof s.lastCount === "number" ? s.lastCount : ids.length,
    lastIds: ids,
  };
}

export function readSearches(storage: Storage | undefined = globalThis.localStorage): SavedSearch[] {
  try {
    const raw = storage?.getItem(KEY);
    if (!raw) return [];
    const data = JSON.parse(raw) as Stored;
    if (data?.v !== 1 || !Array.isArray(data.searches)) return [];
    return data.searches.map(clean).filter((s): s is SavedSearch => s !== null).slice(0, MAX_SEARCHES);
  } catch {
    return [];
  }
}

export function writeSearches(searches: SavedSearch[], storage: Storage | undefined = globalThis.localStorage): void {
  try {
    const seen = new Set<string>();
    const unique = searches.filter((s) => (seen.has(searchKey(s)) ? false : (seen.add(searchKey(s)), true)));
    storage?.setItem(KEY, JSON.stringify({ v: 1, searches: unique.slice(0, MAX_SEARCHES) } satisfies Stored));
    globalThis.dispatchEvent?.(new Event(SEARCHES_EVENT));
  } catch {
    /* storage unavailable: saving just doesn't persist */
  }
}

export function findSearch(searches: SavedSearch[], p: { q: string; budget?: number | null }): SavedSearch | undefined {
  const k = searchKey(p);
  return searches.find((s) => searchKey(s) === k);
}

function newId(): string {
  return `s_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
}

/** Save the current search (newest first). Saving the same search again updates it. */
export function addSearch(
  searches: SavedSearch[],
  p: SearchParams,
  resultIds: string[],
  now: Date = new Date(),
): SavedSearch[] {
  const existing = findSearch(searches, p);
  const at = now.toISOString();
  const entry: SavedSearch = {
    id: existing?.id ?? newId(),
    name: existing?.name ?? p.q.trim(),
    q: p.q.trim(),
    fair: p.fair,
    sort: p.sort,
    budget: p.budget ?? undefined,
    savedAt: existing?.savedAt ?? at,
    lastRunAt: at,
    lastCount: resultIds.length,
    lastIds: resultIds.slice(0, MAX_IDS),
  };
  return [entry, ...searches.filter((s) => s.id !== entry.id)].slice(0, MAX_SEARCHES);
}

export function removeSearch(searches: SavedSearch[], id: string): SavedSearch[] {
  return searches.filter((s) => s.id !== id);
}

export function renameSearch(searches: SavedSearch[], id: string, name: string): SavedSearch[] {
  const n = name.trim().slice(0, 80);
  return searches.map((s) => (s.id === id ? { ...s, name: n || s.q } : s));
}

export interface RunResult {
  searches: SavedSearch[];
  newIds: string[];
  previousRunAt: string;
}

/**
 * A saved search ran again: which results are new since the previous run, and the record
 * updated to this run. Nothing is "new" on the very first run of a fresh save.
 */
export function recordRun(searches: SavedSearch[], id: string, resultIds: string[], now: Date = new Date()): RunResult | null {
  const s = searches.find((x) => x.id === id);
  if (!s) return null;
  const before = new Set(s.lastIds);
  const newIds = resultIds.filter((r) => !before.has(r));
  const updated = { ...s, lastRunAt: now.toISOString(), lastCount: resultIds.length, lastIds: resultIds.slice(0, MAX_IDS) };
  return { searches: searches.map((x) => (x.id === id ? updated : x)), newIds, previousRunAt: s.lastRunAt };
}

export function searchHref(s: Pick<SavedSearch, "q" | "fair" | "sort" | "budget">): string {
  return `/${toQuery(s)}`;
}

// --- Download / import ----------------------------------------------------------------

export const EXPORT_KIND = "wohniq-saved-items";

export interface SavedExport {
  app: "WohnIQ";
  kind: typeof EXPORT_KIND;
  v: 1;
  exportedAt: string;
  flats: string[];
  searches: SavedSearch[];
}

export function buildExport(flats: string[], searches: SavedSearch[], now: Date = new Date()): SavedExport {
  return { app: "WohnIQ", kind: EXPORT_KIND, v: 1, exportedAt: now.toISOString(), flats, searches };
}

export interface ImportResult {
  flats: string[];
  searches: SavedSearch[];
  addedFlats: number;
  addedSearches: number;
}

/**
 * Merge an exported file into what this browser already has: only adds what is missing,
 * never overwrites. Throws a readable Error for files that didn't come from WohnIQ.
 */
export function mergeImport(text: string, flats: string[], searches: SavedSearch[], maxFlats = 100): ImportResult {
  let data: Partial<SavedExport>;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("This file isn't a WohnIQ saved-items file.");
  }
  if (!data || data.app !== "WohnIQ" || data.kind !== EXPORT_KIND || data.v !== 1) {
    throw new Error("This file isn't a WohnIQ saved-items file.");
  }
  const inFlats = Array.isArray(data.flats) ? data.flats.filter((x): x is string => typeof x === "string" && /^[\w-]{1,64}$/.test(x)) : [];
  const inSearches = Array.isArray(data.searches) ? data.searches.map(clean).filter((s): s is SavedSearch => s !== null) : [];
  const haveFlats = new Set(flats);
  const addFlats = [...new Set(inFlats)].filter((f) => !haveFlats.has(f));
  const outFlats = [...flats, ...addFlats].slice(0, maxFlats);
  const haveKeys = new Set(searches.map(searchKey));
  const haveIds = new Set(searches.map((s) => s.id));
  const addSearches = inSearches
    .filter((s) => !haveKeys.has(searchKey(s)))
    .map((s) => (haveIds.has(s.id) ? { ...s, id: newId() } : s));
  const outSearches = [...searches, ...addSearches].slice(0, MAX_SEARCHES);
  return {
    flats: outFlats,
    searches: outSearches,
    addedFlats: outFlats.length - flats.length,
    addedSearches: outSearches.length - searches.length,
  };
}

export const SEARCHES_STORAGE_KEY = KEY;
