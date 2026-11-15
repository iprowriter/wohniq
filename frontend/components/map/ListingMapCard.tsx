import Link from "next/link";
import { ListingPhoto } from "@/components/ListingPhoto";
import { formatEuro, formatRooms, type MapListing } from "@/lib/map/listingsMap";

interface Props {
  listing: MapListing;
  onClose: () => void;
}

/** The card shown above a clicked price pill: photo, rent, location, rooms, size. */
export function ListingMapCard({ listing, onClose }: Props) {
  const location =
    listing.district && listing.district !== listing.kiez
      ? `${listing.kiez}, ${listing.district}`
      : listing.kiez;
  return (
    <div className="wq-card" data-testid="map-card">
      <div className="relative">
        {listing.photo_url ? (
          <ListingPhoto url={listing.photo_url} alt={listing.title} className="h-36 w-full object-cover" />
        ) : (
          <div className="h-36 w-full bg-gray-100" />
        )}
        <button
          type="button"
          aria-label="Close"
          onClick={(e) => {
            e.stopPropagation();
            onClose();
          }}
          className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-full bg-white/95 text-gray-700 shadow hover:bg-white"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
        {listing.risk_band === "high" && (
          <span className="absolute left-2 top-2 rounded-full bg-red-600 px-2 py-0.5 text-[11px] font-semibold text-white shadow">
            High scam risk
          </span>
        )}
      </div>
      <div className="px-3.5 pb-3.5 pt-3">
        <div className="leading-none">
          <span className="text-lg font-bold text-gray-900">{formatEuro(listing.warmmiete_eur)}</span>
          <span className="ml-1 text-xs text-gray-500">warm / month</span>
        </div>
        <div className="mt-1.5 line-clamp-2 text-sm font-medium leading-snug text-gray-900">{listing.title}</div>
        <div className="mt-1.5 flex items-center gap-1 text-xs text-gray-500">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12z" />
            <circle cx="12" cy="10" r="2.5" />
          </svg>
          {location}
        </div>
        <div className="mt-1 text-xs text-gray-600">
          {formatRooms(listing.rooms)} room{listing.rooms === 1 ? "" : "s"} <span className="text-gray-300">•</span>{" "}
          {listing.size_m2} m²
        </div>
        <Link href={`/listings/${listing.id}`} className="wq-card-link mt-3 block rounded-lg py-2 text-center text-sm font-semibold">
          View listing
        </Link>
      </div>
    </div>
  );
}
