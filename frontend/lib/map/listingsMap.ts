// Pure logic for the homepage "See on the map" (no React, no Leaflet, no DOM).
// Unit-tested in tests/listings-map.test.ts.
//
// Zoom tiers — what the map shows at each Leaflet zoom level. At Berlin's latitude one
// screen pixel covers ≈ 93 m at z10, 47 m at z11, 23 m at z12, 12 m at z13, 6 m at z14:
//
//   z ≤ 10   city           A desktop map spans ≥ ~100 km: Potsdam, Oranienburg and other
//                           towns are on screen and Berlin's districts are < 90 px apart →
//                           one bubble: the Berlin median rent, labelled as such.
//   z 11     district       Bezirk centres are ≥ ~100 px apart → one median per Bezirk,
//                           drawn at the Bezirk's geographic centre.
//   z 12     neighbourhood  Kiez centres are ≥ ~70 px apart → one median per Kiez.
//   z ≥ 13   listing        Individual price pills. Pills that would overlap on screen are
//                           stacked into a "N flats" pill (click = zoom in) up to z15;
//                           from z16 every listing always has its own pill.
// Each zoom step out moves one tier: listings → neighbourhoods → districts → Berlin.
// (Checked against screenshots: at z10 the 12 district bubbles would overlap.)
//
// Rents are warm rents (all-in), as everywhere else in WohnIQ.

export interface MapListing {
  id: string;
  title: string;
  kiez: string;
  district?: string | null;
  lat: number;
  lng: number;
  rooms: number;
  size_m2: number;
  warmmiete_eur: number;
  photo_url?: string | null;
  risk_band?: "low" | "caution" | "high" | null;
}

export type MapTier = "city" | "district" | "neighbourhood" | "listing";

export const ZOOM = {
  min: 6, // most of eastern Germany: Berlin among other cities
  max: 18,
  cityMax: 10,
  districtMax: 11,
  neighbourhoodMax: 12,
  stackMax: 15, // overlapping pills are stacked up to this zoom
  initial: 13, // opens on individual listings
} as const;

/** Lowest zoom of each tier — where the tier buttons and cluster clicks fly to. */
export const TIER_ZOOM: Record<MapTier, number> = {
  city: 9, // a little wider than needed, so the surrounding cities are clearly visible
  district: 11,
  neighbourhood: 12,
  listing: 13,
};

// Where district bubbles are drawn: each Bezirk's geographic centre (same figures as the
// backend gazetteer, search/areas.py). Tempelhof-Schöneberg and Neukölln are nudged apart
// vertically so their bubbles don't touch at z11. Unknown districts fall back to the
// centroid of their listings.
export const DISTRICT_LABEL_POINTS: Record<string, [number, number]> = {
  Mitte: [52.531, 13.37],
  "Friedrichshain-Kreuzberg": [52.505, 13.43],
  Pankow: [52.59, 13.43],
  "Charlottenburg-Wilmersdorf": [52.5, 13.285],
  Spandau: [52.535, 13.185],
  "Steglitz-Zehlendorf": [52.435, 13.245],
  "Tempelhof-Schöneberg": [52.463, 13.37],
  Neukölln: [52.435, 13.46],
  "Treptow-Köpenick": [52.44, 13.58],
  "Marzahn-Hellersdorf": [52.525, 13.585],
  Lichtenberg: [52.54, 13.5],
  Reinickendorf: [52.6, 13.29],
};

export const TIERS: MapTier[] = ["city", "district", "neighbourhood", "listing"];

export const BERLIN_CENTER: [number, number] = [52.52, 13.405];
// Inner-city view the map opens on (Mitte, Kreuzberg, Friedrichshain, Prenzlauer Berg).
export const INITIAL_CENTER: [number, number] = [52.508, 13.4];

export function tierForZoom(zoom: number): MapTier {
  const z = Math.round(zoom);
  if (z <= ZOOM.cityMax) return "city";
  if (z <= ZOOM.districtMax) return "district";
  if (z <= ZOOM.neighbourhoodMax) return "neighbourhood";
  return "listing";
}

/** The tier below this one (what a click on a cluster reveals). */
export function nextTier(tier: MapTier): MapTier {
  return TIERS[Math.min(TIERS.indexOf(tier) + 1, TIERS.length - 1)];
}

export function median(values: number[]): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : Math.round((sorted[mid - 1] + sorted[mid]) / 2);
}

/** €1.068 — the German thousands separator used for prices across WohnIQ. */
export function formatEuro(amount: number): string {
  return `€${Math.round(amount)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ".")}`;
}

export function formatRooms(rooms: number): string {
  return Number.isInteger(rooms) ? String(rooms) : rooms.toFixed(1);
}

export interface Bounds {
  south: number;
  west: number;
  north: number;
  east: number;
}

export function boundsOf(points: { lat: number; lng: number }[]): Bounds {
  return {
    south: Math.min(...points.map((p) => p.lat)),
    west: Math.min(...points.map((p) => p.lng)),
    north: Math.max(...points.map((p) => p.lat)),
    east: Math.max(...points.map((p) => p.lng)),
  };
}

function centroid(points: { lat: number; lng: number }[]): [number, number] {
  const n = points.length;
  return [points.reduce((s, p) => s + p.lat, 0) / n, points.reduce((s, p) => s + p.lng, 0) / n];
}

// --- Markers -----------------------------------------------------------------------------

/** A median-rent bubble for Berlin, a district or a neighbourhood. */
export interface AreaMarker {
  kind: "area";
  tier: Exclude<MapTier, "listing">;
  key: string;
  name: string;
  lat: number;
  lng: number;
  count: number;
  median: number;
  bounds: Bounds;
}

/** One listing's price pill. */
export interface ListingMarker {
  kind: "listing";
  key: string;
  listing: MapListing;
  lat: number;
  lng: number;
}

/** Listings whose pills would overlap at this zoom; click to zoom in and separate them. */
export interface StackMarker {
  kind: "stack";
  key: string;
  lat: number;
  lng: number;
  count: number;
  median: number;
  ids: string[];
  bounds: Bounds;
}

export type MapMarker = AreaMarker | ListingMarker | StackMarker;

function areaKey(listing: MapListing, tier: "district" | "neighbourhood"): string {
  return tier === "district" ? listing.district || listing.kiez : listing.kiez;
}

/** Median bubbles for one aggregate tier (sorted by name for a stable render order). */
export function areaMarkers(
  listings: MapListing[],
  tier: Exclude<MapTier, "listing">,
): AreaMarker[] {
  if (!listings.length) return [];
  if (tier === "city") {
    return [
      {
        kind: "area",
        tier,
        key: "city:Berlin",
        name: "Berlin",
        lat: BERLIN_CENTER[0],
        lng: BERLIN_CENTER[1],
        count: listings.length,
        median: median(listings.map((l) => l.warmmiete_eur)),
        bounds: boundsOf(listings),
      },
    ];
  }
  const groups = new Map<string, MapListing[]>();
  for (const l of listings) {
    const key = areaKey(l, tier);
    groups.set(key, [...(groups.get(key) ?? []), l]);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([name, members]) => {
      const [lat, lng] =
        (tier === "district" && DISTRICT_LABEL_POINTS[name]) || centroid(members);
      return {
        kind: "area" as const,
        tier,
        key: `${tier}:${name}`,
        name,
        lat,
        lng,
        count: members.length,
        median: median(members.map((m) => m.warmmiete_eur)),
        bounds: boundsOf(members),
      };
    });
}

// Marker footprint used for overlap detection (px): a price pill ("€1.068") and a stack
// ("3 flats") are both ~58 × 24; the box adds a couple of pixels of breathing room.
export const PILL_W = 60;
export const PILL_H = 26;

export type Project = (lat: number, lng: number) => { x: number; y: number };

/**
 * Listing pills at `zoom`, with pills that would overlap on screen stacked together.
 * `project` maps lat/lng to absolute pixels at this zoom (Leaflet's map.project), so the
 * result doesn't change while panning. The selected listing always keeps its own pill.
 */
export function listingMarkers(
  listings: MapListing[],
  zoom: number,
  project: Project,
  selectedId: string | null = null,
): (ListingMarker | StackMarker)[] {
  const pill = (l: MapListing): ListingMarker => ({
    kind: "listing",
    key: `listing:${l.id}`,
    listing: l,
    lat: l.lat,
    lng: l.lng,
  });
  if (Math.round(zoom) > ZOOM.stackMax) return listings.map(pill);

  // Greedy, deterministic: north-to-south, then by id.
  const ordered = [...listings].sort((a, b) => b.lat - a.lat || a.id.localeCompare(b.id));
  const groups: { x: number; y: number; members: MapListing[] }[] = [];
  for (const l of ordered) {
    if (l.id === selectedId) continue;
    const p = project(l.lat, l.lng);
    const hit = groups.find((g) => Math.abs(g.x - p.x) < PILL_W && Math.abs(g.y - p.y) < PILL_H);
    if (hit) hit.members.push(l);
    else groups.push({ x: p.x, y: p.y, members: [l] });
  }

  const out: (ListingMarker | StackMarker)[] = groups.map((g) => {
    if (g.members.length === 1) return pill(g.members[0]);
    // Drawn at the group's anchor (its first listing), not the centroid: anchors are
    // at least one marker box apart, so stacks never cover a neighbouring pill.
    const anchor = g.members[0];
    const ids = g.members.map((m) => m.id).sort();
    return {
      kind: "stack",
      key: `stack:${ids.join(",")}`,
      lat: anchor.lat,
      lng: anchor.lng,
      count: g.members.length,
      median: median(g.members.map((m) => m.warmmiete_eur)),
      ids,
      bounds: boundsOf(g.members),
    };
  });
  const selected = listings.find((l) => l.id === selectedId);
  if (selected) out.push(pill(selected)); // last = drawn on top
  return out;
}

/** Everything the map draws at `zoom`. */
export function markersForZoom(
  listings: MapListing[],
  zoom: number,
  project: Project,
  selectedId: string | null = null,
): MapMarker[] {
  const tier = tierForZoom(zoom);
  if (tier === "listing") return listingMarkers(listings, zoom, project, selectedId);
  return areaMarkers(listings, tier);
}

// --- Copy ------------------------------------------------------------------------------------

export const TIER_LABEL: Record<MapTier, string> = {
  city: "Berlin",
  district: "Districts",
  neighbourhood: "Neighbourhoods",
  listing: "Listings",
};

/** The status line under the map controls, e.g. "Median warm rent by district · 100 listings". */
export function tierStatus(tier: MapTier, total: number, inView: number): string {
  const listings = `${total} listing${total === 1 ? "" : "s"}`;
  switch (tier) {
    case "city":
      return `Berlin median warm rent · ${listings}. Zoom in for districts`;
    case "district":
      return `Median warm rent by district · ${listings}. Zoom in for neighbourhoods`;
    case "neighbourhood":
      return `Median warm rent by neighbourhood · ${listings}. Zoom in for single flats`;
    default:
      return `Showing ${inView} of ${listings} · zoom out for median rents`;
  }
}

/**
 * Zoom for a click on a cluster. Median bubbles go exactly one tier deeper (Berlin →
 * districts → neighbourhoods → listings), so the user always sees the next level rather
 * than skipping one. "N flats" stacks zoom until their listings' bounds fit.
 */
export function zoomIntoCluster(tier: MapTier, boundsZoom: number): number {
  if (tier === "listing") return Math.min(ZOOM.max, Math.round(boundsZoom));
  return TIER_ZOOM[nextTier(tier)];
}
