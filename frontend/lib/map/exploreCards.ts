// "Explore Berlin" follows the map (no React, no Leaflet). Unit-tested in
// tests/explore-cards.test.ts.
//
// Always exactly EXPLORE_COUNT cards:
//   * page load              → random listings (no area yet)
//   * map area has ≥ 6       → 6 of them, all highlighted ("In map view")
//   * map area has 1–5       → those first (highlighted), the rest filled with random
//                              listings from elsewhere ("Elsewhere in Berlin")
//   * map area has none      → random fillers only
//   * every listing in view  → (zoomed out to all of Berlin) nothing to highlight: keep
//                              the current cards, shown as plain random picks
// Stable: cards still in view keep their place; only cards that left the view are
// replaced, and fillers stay put while they're still needed. So a small pan doesn't
// reshuffle the row.

// Explicit .ts: this runtime import must also resolve under `node --test` (type stripping).
import { tierForZoom, type Bounds, type MapListing } from "./listingsMap.ts";

export const EXPLORE_COUNT = 6;

export type CardTag = "in-view" | "elsewhere" | null;

export interface ExploreCard<T extends { id: string }> {
  listing: T;
  tag: CardTag;
}

/** What the heading says about the current cards. */
export type ExploreStatus =
  | { kind: "random" } // page load, or the whole city is in view
  | { kind: "area"; inView: number } // the map area has `inView` listings (≥ 1)
  | { kind: "empty" }; // nothing in this part of the map

export function listingsInBounds(listings: MapListing[], b: Bounds): MapListing[] {
  return listings.filter(
    (l) => l.lat >= b.south && l.lat <= b.north && l.lng >= b.west && l.lng <= b.east,
  );
}

/**
 * The listings the cards should follow. At the Berlin zoom level the map shows one "Berlin
 * median" bubble, so that view is the whole city on any screen, even a phone too narrow
 * to contain every listing.
 */
export function listingsForView(listings: MapListing[], b: Bounds, zoom: number): MapListing[] {
  return tierForZoom(zoom) === "city" ? listings : listingsInBounds(listings, b);
}

/** Fisher–Yates with an injectable random source (tests pass a seeded one). */
export function shuffled<T>(items: T[], random: () => number = Math.random): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

interface PickInput<T extends { id: string }> {
  /** Listings inside the current map view. */
  inView: T[];
  /** Random listings to fill with, in preferred order (the page-load pool). */
  pool: T[];
  /** Every listing: a last resort for fillers if the pool runs out. */
  all: T[];
  /** The cards currently shown (for stability). */
  previous: ExploreCard<T>[];
  count?: number;
  random?: () => number;
}

/** The cards for the current map view. Always `count` cards (if that many exist). */
export function pickExploreCards<T extends { id: string }>({
  inView,
  pool,
  all,
  previous,
  count = EXPLORE_COUNT,
  random = Math.random,
}: PickInput<T>): { cards: ExploreCard<T>[]; status: ExploreStatus } {
  const inViewIds = new Set(inView.map((l) => l.id));

  // Zoomed out far enough to see every listing: there's no "area" to highlight.
  if (all.length > 0 && inView.length >= all.length) {
    const kept = previous.slice(0, count).map((c) => ({ listing: c.listing, tag: null }));
    const used = new Set(kept.map((c) => c.listing.id));
    const extra = [...pool, ...all].filter((l) => !used.has(l.id) && used.add(l.id));
    return {
      cards: [...kept, ...extra.slice(0, count - kept.length).map((l) => ({ listing: l, tag: null }))],
      status: { kind: "random" },
    };
  }

  // 1. Listings in view: keep the ones already shown (in their order), then add others.
  const shownInView = previous.filter((c) => inViewIds.has(c.listing.id)).map((c) => c.listing);
  const shownIds = new Set(shownInView.map((l) => l.id));
  const newInView = shuffled(
    inView.filter((l) => !shownIds.has(l.id)),
    random,
  );
  const area = [...shownInView, ...newInView].slice(0, count);

  // 2. Fillers from outside the view: keep current fillers, then the pool, then anything.
  const used = new Set(area.map((l) => l.id));
  const candidates = [
    ...previous.filter((c) => c.tag !== "in-view").map((c) => c.listing),
    ...pool,
    ...shuffled(all, random),
  ];
  const fillers: T[] = [];
  for (const l of candidates) {
    if (area.length + fillers.length >= count) break;
    if (inViewIds.has(l.id) || used.has(l.id)) continue;
    used.add(l.id);
    fillers.push(l);
  }

  return {
    cards: [
      ...area.map((l) => ({ listing: l, tag: "in-view" as const })),
      ...fillers.map((l) => ({ listing: l, tag: "elsewhere" as const })),
    ],
    status: inView.length ? { kind: "area", inView: inView.length } : { kind: "empty" },
  };
}

/** The line under "Explore Berlin". Always present, so the section never changes height. */
export function exploreSubtitle(status: ExploreStatus, shownInView: number): string {
  switch (status.kind) {
    case "area":
      return status.inView > shownInView
        ? `${shownInView} of ${status.inView} listings in this map area`
        : `${status.inView} listing${status.inView === 1 ? "" : "s"} in this map area` +
            (shownInView < EXPLORE_COUNT ? ", plus others elsewhere in Berlin" : "");
    case "empty":
      return "No listings in this part of the map, so here are some elsewhere in Berlin";
    default:
      return "A random selection. Move the map below to see listings there";
  }
}

/** The note under the map pointing up at the cards (null when there's nothing to say). */
export function mapToCardsNote(status: ExploreStatus, shownInView: number): string | null {
  if (status.kind !== "area") return null;
  return `${shownInView} listing${shownInView === 1 ? "" : "s"} from this map area ${
    shownInView === 1 ? "is" : "are"
  } shown in Explore Berlin above`;
}
