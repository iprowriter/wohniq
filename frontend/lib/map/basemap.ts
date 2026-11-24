/**
 * The offline base map (ADR-0019): one local PMTiles file (Protomaps basemap v4 from
 * OpenStreetMap, Berlin, zoom 0–15), served by the API at /tiles/berlin.pmtiles and drawn
 * in the browser in Berlin Ink colours. No tile server is ever contacted.
 *
 * Pure module: URL resolution, the colour "flavor" protomaps-leaflet styles with, and the
 * patterns a test uses to make sure no online tile server sneaks back in.
 */

// Explicit .ts: this runtime import must also resolve under `node --test` (type stripping).
import { API_BASE } from "../api.ts";

/** Where the map file is. Override for a deployment without the Berlin build (e.g. a
 * public Supabase Storage URL) with NEXT_PUBLIC_MAP_TILES_URL. */
export function basemapUrl(): string {
  return process.env.NEXT_PUBLIC_MAP_TILES_URL ?? `${API_BASE}/tiles/berlin.pmtiles`;
}

export const BASEMAP_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · ' +
  '<a href="https://protomaps.com">Protomaps</a> · offline map';

/** Zoom levels the file holds; Leaflet over-zooms the last one. */
export const BASEMAP_MAX_DATA_ZOOM = 15;

/** Berlin Ink map colours (design/tokens.css: map-land, map-water, map-green, lines). */
const LAND = "#EBEEF3";
const WATER = "#B9C8E8";
const GREEN = "#D3E7DA";
const GREEN_DEEP = "#C7DFCF";
const ROAD = "#FFFFFF";
const CASING = "#DDE1E8";
const LABEL = "#5B6475";
const HALO = "#FFFFFF";

/** A complete protomaps "Flavor": every colour the basemap paint and label rules use. */
export const BERLIN_INK_FLAVOR = {
  background: LAND,
  earth: LAND,
  park_a: GREEN,
  park_b: GREEN_DEEP,
  hospital: "#EDE7EE",
  industrial: "#E6E8EE",
  school: "#ECE9E2",
  wood_a: GREEN_DEEP,
  wood_b: "#BFD9C8",
  pedestrian: "#F3F4F7",
  scrub_a: GREEN,
  scrub_b: GREEN_DEEP,
  glacier: "#FFFFFF",
  sand: "#EFEBE0",
  beach: "#EFEBE0",
  aerodrome: "#E4E7EE",
  runway: "#D6DBE4",
  water: WATER,
  zoo: GREEN,
  military: "#E6E8EE",
  tunnel_other_casing: CASING,
  tunnel_minor_casing: CASING,
  tunnel_link_casing: CASING,
  tunnel_major_casing: CASING,
  tunnel_highway_casing: CASING,
  tunnel_other: "#F4F5F7",
  tunnel_minor: "#F4F5F7",
  tunnel_link: "#F4F5F7",
  tunnel_major: "#F4F5F7",
  tunnel_highway: "#F4F5F7",
  pier: "#E2E6ED",
  buildings: "#E2E6ED",
  minor_service_casing: CASING,
  minor_casing: CASING,
  link_casing: CASING,
  major_casing_late: CASING,
  highway_casing_late: "#CFD5DF",
  other: ROAD,
  minor_service: ROAD,
  minor_a: ROAD,
  minor_b: ROAD,
  link: ROAD,
  major_casing_early: CASING,
  major: ROAD,
  highway_casing_early: "#CFD5DF",
  highway: ROAD,
  railway: "#C3CAD6",
  boundaries: "#9AA3B2",
  bridges_other_casing: CASING,
  bridges_minor_casing: CASING,
  bridges_link_casing: CASING,
  bridges_major_casing: CASING,
  bridges_highway_casing: "#CFD5DF",
  bridges_other: ROAD,
  bridges_minor: ROAD,
  bridges_link: ROAD,
  bridges_major: ROAD,
  bridges_highway: ROAD,
  roads_label_minor: "#7A8394",
  roads_label_minor_halo: HALO,
  roads_label_major: LABEL,
  roads_label_major_halo: HALO,
  ocean_label: "#6D86B8",
  subplace_label: LABEL,
  subplace_label_halo: HALO,
  city_label: "#3B4352",
  city_label_halo: HALO,
  state_label: "#7A8394",
  state_label_halo: HALO,
  country_label: "#7A8394",
  address_label: "#9AA3B2",
  address_label_halo: HALO,
  regular: "Geist, Inter, system-ui, sans-serif",
  bold: "Geist, Inter, system-ui, sans-serif",
  italic: "Geist, Inter, system-ui, sans-serif",
  pois: {
    blue: "#6D86B8",
    green: "#5E8F73",
    lapis: "#5168A8",
    pink: "#A8708F",
    red: "#A86A60",
    slategray: "#7A8394",
    tangerine: "#A8834F",
    turquoise: "#4F9A93",
  },
  landcover: {
    barren: "#EFEBE0",
    farmland: "#E8ECE3",
    forest: GREEN_DEEP,
    glacier: "#FFFFFF",
    grassland: GREEN,
    scrub: GREEN,
    urban_area: LAND,
  },
} as const;

/** Online tile servers the app must never use again (checked by tests/basemap.test.ts). */
export const ONLINE_TILE_PATTERNS: RegExp[] = [
  /tile\.openstreetmap\.org/,
  /\{s\}\.tile\./,
  /basemaps\.cartocdn\.com/,
  /tiles\.stadiamaps\.com/,
  /api\.maptiler\.com/,
  /tile\.thunderforest\.com/,
  /server\.arcgisonline\.com/,
];

/** First bytes of every PMTiles v3 file. */
export const PMTILES_MAGIC = "PMTiles";

/** Is the map file reachable? One 7-byte range request (no full download). */
export async function basemapAvailable(
  url = basemapUrl(),
  fetchFn: typeof fetch = fetch,
): Promise<boolean> {
  try {
    const res = await fetchFn(url, { headers: { Range: "bytes=0-6" } });
    if (!res.ok) return false;
    const head = new TextDecoder().decode(await res.arrayBuffer());
    return head.startsWith(PMTILES_MAGIC);
  } catch {
    return false;
  }
}
