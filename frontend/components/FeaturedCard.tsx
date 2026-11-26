import Link from "next/link";
import type { ListingOut } from "@/lib/types";
import type { CardTag } from "@/lib/map/exploreCards";
import { euro, rooms } from "@/lib/format";
import { rentChip } from "@/lib/listing/chips";
import { Chip } from "@/components/ui/primitives";
import { StationChip } from "@/components/listing/VerdictChips";
import { ListingPhoto } from "./ListingPhoto";

/** What the card needs: a full listing (`photos`, `rent`, `location`) or a map point. */
export type CardListing = Pick<
  ListingOut,
  "id" | "title" | "kiez" | "warmmiete_eur" | "size_m2" | "rooms"
> & {
  photos?: ListingOut["photos"];
  photo_url?: string | null;
  rent?: ListingOut["rent"];
  location?: ListingOut["location"];
  rent_verdict?: string | null;
  rail_stop?: string | null;
  rail_modes?: string[];
  rail_walk_minutes?: number | null;
};

interface Props {
  listing: CardListing;
  /** Explore Berlin follows the map: in the current map view, or a filler from elsewhere. */
  tag?: CardTag;
}

export function FeaturedCard({ listing, tag = null }: Props) {
  const cover = listing.photos?.[0]?.url ?? listing.photo_url ?? null;
  const verdict = listing.rent?.verdict ?? listing.rent_verdict ?? null;
  const chip = verdict ? rentChip({ verdict } as NonNullable<ListingOut["rent"]>) : null;
  const station = listing.location?.rail_stop ?? listing.rail_stop;
  const modes = listing.location?.rail_modes ?? listing.rail_modes ?? [];
  const walk = listing.location?.rail_walk_minutes ?? listing.rail_walk_minutes;

  return (
    <Link
      href={`/listings/${listing.id}`}
      data-testid="explore-card"
      data-tag={tag ?? "none"}
      data-id={listing.id}
      className={`group relative flex flex-col overflow-hidden rounded-lg border bg-surface transition-shadow hover:shadow-md ${
        tag === "in-view" ? "border-accent ring-2 ring-accent-soft" : "border-line"
      }`}
    >
      {cover ? (
        <ListingPhoto
          url={cover}
          alt={listing.title}
          className="h-40 w-full bg-placeholder object-cover"
          placeholderClassName="h-40 w-full bg-placeholder"
        />
      ) : (
        <div className="h-40 w-full bg-placeholder" />
      )}
      {tag === "in-view" && (
        <span className="absolute left-3 top-3 rounded-full bg-accent px-2.5 py-1 text-[12px] font-semibold text-white shadow">
          In map view
        </span>
      )}
      {tag === "elsewhere" && (
        <span className="absolute left-3 top-3 rounded-full bg-surface/95 px-2.5 py-1 text-[12px] font-medium text-text-body shadow-sm">
          Elsewhere in Berlin
        </span>
      )}
      {/* Fixed height: Explore Berlin swaps cards as the map moves, and the map below must
          never jump (e2e "map never moves"). One line per row, the chip row always there. */}
      <div className="flex h-[118px] flex-col gap-1.5 p-4">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="truncate text-[16px] font-semibold text-text">{listing.kiez}</h3>
          <span className="text-[17px] font-semibold tabular-nums text-text">{euro(listing.warmmiete_eur)}</span>
        </div>
        <p className="sr-only">{listing.title}</p>
        <div className="flex min-w-0 flex-nowrap items-center gap-x-1.5 overflow-hidden whitespace-nowrap text-[13px] text-text-muted">
          <span>{rooms(listing.rooms)}</span>
          <span aria-hidden="true">·</span>
          <span>{listing.size_m2} m²</span>
          {station && (
            <>
              <span aria-hidden="true">·</span>
              <StationChip stop={station} modes={modes} minutes={walk} compact />
            </>
          )}
        </div>
        <div className="mt-auto h-6 pt-0.5">{chip && <Chip tone={chip.tone}>{chip.short}</Chip>}</div>
      </div>
    </Link>
  );
}
