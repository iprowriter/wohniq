/**
 * The search a listing was opened from (this tab only): the link back, its heading, and each
 * result's fit, so the listing page can show "Fit for your search" and "Back to 8 results".
 */

const KEY = "wohniq_last_results";

export interface LastSearch {
  url: string; // "/?q=…"
  heading: string; // "8 flats in Mitte"
  count: number;
  areas: string[];
  fit: Record<string, { score: number; summary: string }>;
  // For "Compare with…" on the listing page (T9.7): the results in order, title and rent.
  items?: { id: string; title: string; warm: number; kiez: string }[];
}

export function saveLastSearch(s: LastSearch, storage: Storage | undefined = globalThis.sessionStorage): void {
  try {
    storage?.setItem(KEY, JSON.stringify(s));
  } catch {
    /* unavailable: the listing page just shows "Search to see the fit" */
  }
}

export function readLastSearch(storage: Storage | undefined = globalThis.sessionStorage): LastSearch | null {
  try {
    const raw = storage?.getItem(KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as LastSearch;
    return typeof s?.url === "string" && s.fit && typeof s.fit === "object" ? s : null;
  } catch {
    return null;
  }
}

/** "Back to 8 results in Mitte" / "Back to 8 results" / "Back to search". */
export function backLabel(s: LastSearch | null): string {
  if (!s) return "Back to search";
  const n = s.count === 1 ? "1 result" : `${s.count} results`;
  return s.areas.length ? `Back to ${n} in ${s.areas.join(", ")}` : `Back to ${n}`;
}

export function fitLabel(score: number): string {
  const v = Math.round(score * 100);
  return v >= 80 ? "Strong match" : v >= 60 ? "Good match" : "Partial match";
}
