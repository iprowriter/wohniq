"use client";

import dynamic from "next/dynamic";
import type { SearchResultItem } from "@/lib/types";
import type { MapListing } from "@/lib/map/listingsMap";

export type ResultsMapProps = {
  results: SearchResultItem[];
  /** Areas the user asked for ("Mitte · as you asked"). */
  areas: string[];
  /** Every listing (for the Median rent layer). */
  allListings: MapListing[] | null;
  highlighted: string | null;
  onHighlight: (id: string | null) => void;
};

const Inner = dynamic(() => import("./ResultsMapInner"), {
  ssr: false,
  loading: () => <div className="h-[560px] animate-pulse rounded-lg bg-map-land" />,
});

/** Sticky map next to the search results, with Listings / Median rent / Transit / Green. */
export function ResultsMap(props: ResultsMapProps) {
  return <Inner {...props} />;
}
