"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { RegionListingsResponse } from "@/lib/lifestyle/types";
import { getRegionListings } from "@/lib/lifestyle/api";
import { euro } from "@/lib/lifestyle/logic";
import { ListingPhoto } from "@/components/ListingPhoto";
import { RiskBadge } from "@/components/RiskBadge";

interface Props {
  region: { key: string; name: string } | null;
  budget: number;
  onClose: () => void;
}

/** Slide-over panel: WohnIQ listings located inside the chosen area (by coordinates). */
export function ListingsPanel({ region, budget, onClose }: Props) {
  const [data, setData] = useState<RegionListingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const open = region !== null;

  useEffect(() => {
    if (!region) return;
    let cancelled = false;
    setData(null);
    setError(null);
    getRegionListings(region.key, budget)
      .then((d) => !cancelled && setData(d))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [region, budget]);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      previous?.focus();
    };
  }, [open, onClose]);

  if (!region) return null;
  return (
    <div className="fixed inset-0 z-[1000]" role="dialog" aria-modal="true" aria-labelledby="flats-title">
      <button type="button" className="absolute inset-0 bg-gray-950/40 backdrop-blur-[2px]" onClick={onClose} aria-label="Close" tabIndex={-1} />
      <aside className="animate-[slide-in_0.35s_ease-out_both] absolute inset-y-0 right-0 flex w-full max-w-md flex-col bg-white shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-gray-100 px-5 py-4">
          <div>
            <p className="text-xs text-gray-400">WohnIQ listings in</p>
            <h2 id="flats-title" className="text-lg font-semibold text-gray-900">
              {region.name}
            </h2>
            {data && (
              <p className="mt-0.5 text-xs text-gray-500">
                {data.count} flat{data.count === 1 ? "" : "s"} located in this area · budget {euro(budget)}
              </p>
            )}
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-full p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
            aria-label="Close listings"
          >
            ✕
          </button>
        </header>

        <div className="flex-1 space-y-3 overflow-y-auto p-5">
          {error && <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
          {!data && !error && [0, 1, 2].map((i) => <div key={i} className="h-28 animate-pulse rounded-xl bg-gray-100" />)}
          {data && data.count === 0 && (
            <div className="px-2 py-12 text-center">
              <p className="text-4xl" aria-hidden="true">🏘️</p>
              <p className="mt-3 font-semibold text-gray-900">No WohnIQ listings here yet</p>
              <p className="mt-1 text-sm leading-relaxed text-gray-500">
                {region.name} still matches your lifestyle — our listing inventory is small. Try the next areas on
                your list, or check back later.
              </p>
            </div>
          )}
          {data?.listings.map(({ listing, fits_budget, risk }) => {
            const high = risk?.band === "high";
            return (
              <Link
                key={listing.id}
                href={`/listings/${listing.id}`}
                className={`block overflow-hidden rounded-xl border transition hover:shadow-md ${high ? "border-red-200" : "border-gray-200"}`}
              >
                {high && (
                  <p className="bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700">
                    ⚠ High scam risk — read the warning signs before contacting anyone.
                  </p>
                )}
                <div className="flex gap-3 p-3">
                  {listing.photos[0] ? (
                    <ListingPhoto url={listing.photos[0].url} alt={listing.title} className="h-20 w-24 flex-shrink-0 rounded-lg object-cover" />
                  ) : (
                    <div className="h-20 w-24 flex-shrink-0 rounded-lg bg-gray-100" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-sm font-medium text-gray-900">{listing.title}</p>
                    <p className="mt-0.5 text-xs text-gray-500">
                      {listing.size_m2} m² · {listing.rooms} room{listing.rooms === 1 ? "" : "s"}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold">{euro(listing.warmmiete_eur)} warm</span>
                      {fits_budget !== null && (
                        <span
                          className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                            fits_budget ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800"
                          }`}
                        >
                          {fits_budget ? "Within budget" : "Over budget"}
                        </span>
                      )}
                      <RiskBadge risk={risk} />
                    </div>
                  </div>
                </div>
              </Link>
            );
          })}
          {data && data.count > data.listings.length && (
            <p className="text-center text-xs text-gray-400">
              Showing {data.listings.length} of {data.count}.
            </p>
          )}
        </div>
        <footer className="border-t border-gray-100 px-5 py-3 text-[11px] leading-relaxed text-gray-400">
          Matched by each flat&apos;s location inside the area. Every listing is risk-scored — a very low price is a
          common scam pattern.
        </footer>
      </aside>
    </div>
  );
}
