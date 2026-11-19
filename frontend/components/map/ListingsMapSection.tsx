"use client";

import dynamic from "next/dynamic";
import type { Bounds, MapListing } from "@/lib/map/listingsMap";

// Leaflet needs `window`: load the map on the client only.
const ListingsMap = dynamic(() => import("./ListingsMap").then((m) => m.ListingsMap), {
  ssr: false,
  loading: () => <div className="h-[560px] animate-pulse rounded-2xl bg-gray-100" />,
});

interface Props {
  /** Every listing (null while loading). Loaded by the page, which shares it with Explore Berlin. */
  listings: MapListing[] | null;
  error?: string | null;
  /** The visible map area after the user moved the map (Explore Berlin follows it). */
  onUserViewChange?: (bounds: Bounds, zoom: number) => void;
  /** "2 listings from this map area are shown in Explore Berlin above" — click scrolls up. */
  cardsNote?: string | null;
  onCardsNoteClick?: () => void;
}

/** Homepage section under "Explore Berlin": every listing on the map. */
export function ListingsMapSection({
  listings,
  error,
  onUserViewChange,
  cardsNote,
  onCardsNoteClick,
}: Props) {
  return (
    <section className="pb-14" id="map" aria-labelledby="map-heading">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="map-heading" className="text-lg font-semibold">
            See on the map
          </h2>
          <p className="mt-0.5 text-sm text-gray-500">
            Every listing with its warm rent. Zoom out for median rents by neighbourhood, district
            and for all of Berlin; click a price to see the flat. Explore Berlin above follows the
            map.
          </p>
        </div>
      </div>
      {error ? (
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      ) : listings === null ? (
        <div className="h-[560px] animate-pulse rounded-2xl bg-gray-100" />
      ) : (
        <ListingsMap listings={listings} onUserViewChange={onUserViewChange} />
      )}
      {/* Always rendered (empty when there's nothing to say), so nothing below jumps. */}
      <div className="mt-2 min-h-[1.25rem]" aria-live="polite">
        {cardsNote && (
          <button
            type="button"
            onClick={onCardsNoteClick}
            data-testid="map-cards-note"
            className="inline-flex items-center gap-1 text-xs font-medium text-violet-700 hover:text-violet-900"
          >
            <span aria-hidden="true">↑</span> {cardsNote}
          </button>
        )}
      </div>
    </section>
  );
}
