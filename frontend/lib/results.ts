/**
 * Search results view logic (pure, unit-tested): sorting, the "Only fair rents" filter, the
 * heading, and the shareable URL. Ranking itself stays in the backend (golden rule 1); these
 * only re-order what was returned, by a field the user picks.
 */

import type { SearchResultItem } from "./types.ts";
import { isFairRent } from "./listing/chips.ts";

export type SortKey = "fit" | "price" | "rent" | "size";

export const SORT_LABELS: Record<SortKey, string> = {
  fit: "Best fit",
  price: "Warm rent, lowest first",
  rent: "Rent vs limit, fairest first",
  size: "Size, largest first",
};

/** How far a rent sits from its limit (negative = under). New builds/unknown sort last. */
function rentRatio(item: SearchResultItem): number {
  const r = item.listing.rent;
  if (!r || r.asked == null || r.limit == null) return Number.POSITIVE_INFINITY;
  return r.asked / r.limit;
}

export function sortResults(items: SearchResultItem[], key: SortKey): SearchResultItem[] {
  const out = [...items];
  const byFit = (a: SearchResultItem, b: SearchResultItem) => b.score - a.score;
  switch (key) {
    case "price":
      return out.sort((a, b) => a.listing.warmmiete_eur - b.listing.warmmiete_eur || byFit(a, b));
    case "rent":
      return out.sort((a, b) => rentRatio(a) - rentRatio(b) || byFit(a, b));
    case "size":
      return out.sort((a, b) => b.listing.size_m2 - a.listing.size_m2 || byFit(a, b));
    default:
      return out; // the backend's order is the fit ranking
  }
}

export function visibleResults(items: SearchResultItem[], fairOnly: boolean, sort: SortKey) {
  return sortResults(fairOnly ? items.filter((i) => isFairRent(i.listing.rent)) : items, sort);
}

export function resultsHeading(n: number, areas: string[]): string {
  const flats = n === 1 ? "1 flat" : `${n} flats`;
  return areas.length ? `${flats} in ${areas.join(", ")}` : `${flats} for your search`;
}

export interface SearchParams {
  q: string;
  fair: boolean;
  sort: SortKey;
  budget?: number;
}

export function readParams(p: URLSearchParams): SearchParams | null {
  const q = (p.get("q") ?? "").trim();
  if (!q) return null;
  const sort = (p.get("sort") ?? "fit") as SortKey;
  const budget = Number(p.get("budget"));
  return {
    q,
    fair: p.get("fair") === "1",
    sort: sort in SORT_LABELS ? sort : "fit",
    budget: Number.isFinite(budget) && budget >= 100 ? budget : undefined,
  };
}

export function toQuery(s: SearchParams): string {
  const p = new URLSearchParams({ q: s.q });
  if (s.fair) p.set("fair", "1");
  if (s.sort !== "fit") p.set("sort", s.sort);
  if (s.budget) p.set("budget", String(s.budget));
  return `?${p.toString()}`;
}
