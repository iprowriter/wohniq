import Link from "next/link";
import type { ListingOut } from "@/lib/types";
import type { CardTag } from "@/lib/map/exploreCards";
import { ListingPhoto } from "./ListingPhoto";

/** What the card needs: a full listing (`photos`) or a map point (`photo_url`). */
export type CardListing = Pick<
  ListingOut,
  "id" | "title" | "kiez" | "warmmiete_eur" | "size_m2" | "rooms"
> & { photos?: ListingOut["photos"]; photo_url?: string | null };

function euro(n: number) {
  return `€${n.toLocaleString("de-DE")}`;
}

function formatRooms(n: number) {
  return n % 1 === 0 ? String(Math.round(n)) : n.toFixed(1);
}

interface Props {
  listing: CardListing;
  /** Explore Berlin follows the map: in the current map view, or a filler from elsewhere. */
  tag?: CardTag;
}

export function FeaturedCard({ listing, tag = null }: Props) {
  const cover = listing.photos?.[0]?.url ?? listing.photo_url ?? null;
  const inView = tag === "in-view";

  return (
    <Link
      href={`/listings/${listing.id}`}
      data-testid="explore-card"
      data-tag={tag ?? "none"}
      data-id={listing.id}
      className={`group relative block overflow-hidden rounded-2xl border bg-white transition-all hover:shadow-lg ${
        inView
          ? "border-violet-300 ring-2 ring-violet-200 hover:border-violet-400"
          : "border-gray-200 hover:border-gray-300"
      }`}
    >
      {cover ? (
        <ListingPhoto
          url={cover}
          alt={listing.title}
          className="h-44 w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
        />
      ) : (
        <div className="h-44 w-full bg-gray-100" />
      )}
      {/* Overlay tags: on the photo, so they never change the card's height. */}
      {tag === "in-view" && (
        <span className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-violet-700 px-2.5 py-1 text-[11px] font-semibold text-white shadow">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
            <path d="M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12z" />
          </svg>
          In map view
        </span>
      )}
      {tag === "elsewhere" && (
        <span className="absolute left-3 top-3 rounded-full bg-white/90 px-2.5 py-1 text-[11px] font-medium text-gray-600 shadow-sm">
          Elsewhere in Berlin
        </span>
      )}
      <div className="p-4">
        <p className="mb-0.5 truncate text-xs font-medium uppercase tracking-wide text-gray-400">
          {listing.kiez}
        </p>
        {/* Fixed two-line height: the grid (and the map below it) never shifts. */}
        <h3 className="mb-3 line-clamp-2 h-10 text-sm font-medium leading-snug">{listing.title}</h3>
        <div className="flex items-center justify-between">
          <span className="text-base font-semibold">{euro(listing.warmmiete_eur)}</span>
          <span className="text-xs text-gray-400">
            {listing.size_m2} m² · {formatRooms(listing.rooms)} Zi.
          </span>
        </div>
      </div>
    </Link>
  );
}
