// Pure logic for the Berlin Neighborhoods page (no React, no fetch, no DOM).
// Unit-tested in tests/neighborhoods.test.ts.

import type { CategoryInfo, NeighborhoodCatalog, RankedArea, SourceInfo, Tier } from "./types";

export const OVERALL = "overall";

// --- Weights (overall ranking) ----------------------------------------------------------

export function defaultWeights(catalog: NeighborhoodCatalog): Record<string, number> {
  return Object.fromEntries(catalog.categories.map((c) => [c.id, c.default_weight]));
}

/** {safety: 3, parking: 0} → "parking:0,safety:3" (sorted, so equal weights give equal URLs). */
export function weightsParam(weights: Record<string, number>): string {
  return Object.keys(weights)
    .sort()
    .map((k) => `${k}:${weights[k]}`)
    .join(",");
}

/**
 * Parse "safety:3,parking:0" from a URL. Unknown categories and out-of-range values are
 * dropped; returns null when nothing valid remains or every weight would be 0.
 */
export function parseWeightsParam(
  text: string | null | undefined,
  catalog: NeighborhoodCatalog,
): Record<string, number> | null {
  if (!text) return null;
  const known = new Set(catalog.categories.map((c) => c.id));
  const out = defaultWeights(catalog);
  let any = false;
  for (const part of text.split(",")) {
    const [id, value] = part.split(":").map((s) => s?.trim());
    const n = Number(value);
    if (known.has(id) && Number.isInteger(n) && n >= 0 && n <= catalog.max_weight) {
      out[id] = n;
      any = true;
    }
  }
  if (!any || Object.values(out).every((v) => v === 0)) return null;
  return out;
}

export function sameWeights(a: Record<string, number>, b: Record<string, number>): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of keys) if ((a[k] ?? 0) !== (b[k] ?? 0)) return false;
  return true;
}

export function changedWeights(applied: Record<string, number>, draft: Record<string, number>): number {
  const keys = new Set([...Object.keys(applied), ...Object.keys(draft)]);
  let n = 0;
  for (const k of keys) if ((applied[k] ?? 0) !== (draft[k] ?? 0)) n += 1;
  return n;
}

export function setWeight(
  draft: Record<string, number>,
  id: string,
  value: number,
  max: number,
): Record<string, number> {
  return { ...draft, [id]: Math.max(0, Math.min(max, Math.round(value))) };
}

export const WEIGHT_LABELS = ["Ignore", "Some", "Important", "Top priority"];

// --- URL state (shareable: ?category=safety&area=011001&w=…) --------------------------------

export interface PageState {
  category: string;
  area: string | null;
  weights: Record<string, number> | null;
}

export function parsePageState(params: URLSearchParams, catalog: NeighborhoodCatalog): PageState {
  const cat = params.get("category") ?? OVERALL;
  const category = cat === OVERALL || catalog.categories.some((c) => c.id === cat) ? cat : OVERALL;
  const area = params.get("area");
  return {
    category,
    area: area && /^\d{6}$/.test(area) ? area : null,
    weights: parseWeightsParam(params.get("w"), catalog),
  };
}

export function pageQuery(state: PageState, catalog: NeighborhoodCatalog): string {
  const p = new URLSearchParams();
  if (state.category !== OVERALL) p.set("category", state.category);
  if (state.area) p.set("area", state.area);
  if (state.weights && !sameWeights(state.weights, defaultWeights(catalog))) {
    p.set("w", weightsParam(state.weights));
  }
  const q = p.toString();
  return q ? `?${q}` : "";
}

// --- Filtering and ordering the list ---------------------------------------------------------

/** Case- and accent-insensitive: "muggelheim" finds "Müggelheim", "strasse" finds "straße". */
export function normalize(text: string): string {
  return text
    .toLowerCase()
    .replace(/ß/g, "ss")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

export interface ListFilter {
  query: string;
  district: string; // "" = all districts
}

export function filterAreas(areas: RankedArea[], filter: ListFilter): RankedArea[] {
  const q = normalize(filter.query);
  return areas.filter(
    (a) =>
      (!filter.district || a.district === filter.district) &&
      (!q || normalize(`${a.name} ${a.area_group} ${a.district}`).includes(q)),
  );
}

export type Order = "best" | "worst";

/** Best first (the API's order) or worst first; ties stay alphabetical either way. */
export function orderAreas(areas: RankedArea[], order: Order): RankedArea[] {
  const sorted = [...areas].sort((a, b) => a.rank - b.rank || a.name.localeCompare(b.name));
  if (order === "best") return sorted;
  return sorted.sort((a, b) => b.rank - a.rank || a.name.localeCompare(b.name));
}

/** "Lowest crime first" / "Highest crime first"; plain "Best first" for the overall score. */
export function orderLabel(order: Order, bestLabel: string | null, worstLabel: string | null): string {
  if (order === "best") return bestLabel ? `${bestLabel} first` : "Best first";
  return worstLabel ? `${worstLabel} first` : "Worst first";
}

// --- Colours and tiers ---------------------------------------------------------------------------

/**
 * Five rank bands (quintiles of Berlin's 143 areas) on one calm Berlin Ink blue scale:
 * deep blue = best 20%, palest = bottom 20% (no alarm colour; T9.6). Rank-based (not
 * score-based), so every category uses the full scale.
 */
export const BANDS: { color: string; label: string }[] = [
  { color: "#1A33B3", label: "Top 20%" },
  { color: "#2747E6", label: "20–40%" },
  { color: "#6F8BFF", label: "Middle" },
  { color: "#B4C2FF", label: "60–80%" },
  { color: "#E3E8FF", label: "Bottom 20%" },
];
export const MUTED_COLOR = "#E3E6EC";

export function bandIndex(rank: number, total: number): number {
  if (total <= 0) return 2;
  return Math.max(0, Math.min(4, Math.floor(((rank - 1) / total) * 5)));
}

export function rankColor(rank: number, total: number): string {
  return BANDS[bandIndex(rank, total)].color;
}

/** Readable text on a band colour: white on the two dark bands, ink on the lighter ones. */
export function rankTextColor(rank: number, total: number): string {
  return [0, 1].includes(bandIndex(rank, total)) ? "#ffffff" : "#0D1321";
}

export function tierBadge(
  tier: Tier,
  bestLabel: string | null,
  worstLabel: string | null,
): { text: string; className: string } | null {
  if (tier === "best" && bestLabel)
    return {
      text: bestLabel,
      className: "bg-accent-tint text-accent ring-accent/30",
    };
  if (tier === "worst" && worstLabel)
    return {
      text: worstLabel,
      className: "bg-chip text-text-body ring-line-strong",
    };
  return null;
}

/** How an area's value compares with the Berlin figure, given the metric's direction. */
export function versusBerlin(raw: number, berlin: number | null, higherIsBetter: boolean): "better" | "worse" | "same" {
  if (berlin == null) return "same";
  const tolerance = Math.max(Math.abs(berlin) * 0.03, 1e-9); // within 3% = about the same
  if (Math.abs(raw - berlin) <= tolerance) return "same";
  return raw > berlin === higherIsBetter ? "better" : "worse";
}

export function categoryById(catalog: NeighborhoodCatalog, id: string): CategoryInfo | undefined {
  return catalog.categories.find((c) => c.id === id);
}

// --- Sources -------------------------------------------------------------------------------------------

const SHORT_PUBLISHER: Record<string, string> = {
  pks_kriminalitaetsatlas: "Polizei Berlin",
  unfallatlas_2025: "Unfallatlas",
  mss_2023: "Senate MSS",
  blickpunkt_schule_2026: "SenBJF schools",
  openstreetmap_geofabrik: "OpenStreetMap",
  openstreetmap_geofabrik_2026_11_12: "OpenStreetMap",
  vbb_gtfs: "VBB timetable",
  umweltgerechtigkeitsatlas_2023_2024: "Umweltatlas",
  ibb_tabellenband_2025: "IBB",
  afs_einwohnerregister_2024: "Statistik BB",
  senstadt_lor_2021: "LOR 2021",
  bodenrichtwerte_2026: "Gutachterausschuss",
  afs_lohnsteuer_2022: "Statistik BB",
};

/** Short chip label, e.g. "Polizei Berlin · 2023–2025" or "SenBJF schools · 2024/25". */
export function sourceLabel(source: SourceInfo | undefined): string {
  if (!source) return "Source";
  const publisher = SHORT_PUBLISHER[source.id] ?? source.publisher.split(/[(,;—]/)[0].trim();
  const schoolYear = source.data_year.match(/\b\d{4}\/\d{2}\b/);
  if (schoolYear) return `${publisher} · ${schoolYear[0]}`;
  const years = (source.data_year.match(/\d{4}/g) ?? []).map(Number);
  if (years.length === 0) return `${publisher} · ${source.data_year}`;
  const lo = Math.min(...years);
  const hi = Math.max(...years);
  return `${publisher} · ${lo === hi ? lo : `${lo}–${hi}`}`;
}

export function sourceMap(sources: SourceInfo[]): Record<string, SourceInfo> {
  return Object.fromEntries(sources.map((s) => [s.id, s]));
}
