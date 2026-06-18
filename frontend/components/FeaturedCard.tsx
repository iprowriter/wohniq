import Link from "next/link";
import type { ListingOut } from "@/lib/types";

function euro(n: number) {
  return `€${n.toLocaleString("de-DE")}`;
}

function formatRooms(n: number) {
  return n % 1 === 0 ? String(Math.round(n)) : n.toFixed(1);
}

export function FeaturedCard({ listing }: { listing: ListingOut }) {
  const cover = listing.photos[0];

  return (
    <Link
      href={`/listings/${listing.id}`}
      className="group block overflow-hidden rounded-2xl border border-gray-200 bg-white transition-all hover:border-gray-300 hover:shadow-lg"
    >
      {cover ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={cover.url}
          alt={listing.title}
          className="h-44 w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
        />
      ) : (
        <div className="h-44 w-full bg-gray-100" />
      )}
      <div className="p-4">
        <p className="mb-0.5 text-xs font-medium uppercase tracking-wide text-gray-400">
          {listing.kiez}
        </p>
        <h3 className="mb-3 line-clamp-2 text-sm font-medium leading-snug">{listing.title}</h3>
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
