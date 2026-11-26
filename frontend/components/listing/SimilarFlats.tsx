"use client";

/**
 * "Similar apartments to this" (T9.7): ranked by the backend on named factors, each card
 * saying why. High-risk flats are included with their risk chip (owner's decision). When this
 * flat is above the rent-brake limit, flats within the limit come first.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { getSimilarListings } from "@/lib/api";
import type { SimilarResponse } from "@/lib/types";
import { euro, rooms } from "@/lib/format";
import { useSaved } from "@/lib/useSaved";
import { useCompare } from "@/lib/compare/useCompare";
import { RentChip, RiskChip } from "@/components/listing/VerdictChips";
import { ListingPhoto } from "@/components/ListingPhoto";
import { Button, buttonClass } from "@/components/ui/primitives";

export function SimilarFlats({ listingId, onLoaded }: { listingId: string; onLoaded?: (d: SimilarResponse) => void }) {
  const [data, setData] = useState<SimilarResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [more, setMore] = useState(false);
  const saved = useSaved();
  const compare = useCompare();

  useEffect(() => {
    let live = true;
    setData(null);
    getSimilarListings(listingId)
      .then((d) => {
        if (!live) return;
        setData(d);
        onLoaded?.(d);
      })
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listingId]);

  if (error) return null; // optional section: the rest of the page stands on its own
  const items = data?.items ?? [];
  const title = data?.within_limit_first ? "Similar flats within the rent limit" : "Similar apartments to this";

  return (
    <section className="no-print flex flex-col gap-4" aria-labelledby="similar-heading" data-testid="similar">
      <div>
        <h2 id="similar-heading" className="text-[22px] font-semibold text-text">{title}</h2>
        <p className="text-[14px] text-text-muted">
          {data?.within_limit_first
            ? "This flat asks more than the rent-brake limit, so flats within it come first. "
            : ""}
          Ranked by distance, rooms, size, warm rent, furnishing and building age.
        </p>
      </div>
      {!data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => <div key={i} className="h-72 animate-pulse rounded-lg bg-chip" />)}
        </div>
      ) : (
        <>
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {items.slice(0, 6).map((it, i) => {
              const l = it.listing;
              const inCompare = compare.has(l.id);
              return (
                <li
                  key={l.id}
                  data-testid="similar-card"
                  className={`flex flex-col overflow-hidden rounded-lg border border-line bg-surface ${i >= 3 && !more ? "hidden sm:flex" : "flex"}`}
                >
                  <Link href={`/listings/${l.id}`} className="relative block h-[150px] bg-placeholder" tabIndex={-1} aria-hidden="true">
                    {l.photos[0] && <ListingPhoto url={l.photos[0].url} alt="" className="absolute inset-0 h-full w-full object-cover" placeholderClassName="absolute inset-0 h-full w-full bg-placeholder" />}
                  </Link>
                  <div className="flex flex-1 flex-col gap-2 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="min-w-0 text-[15.5px] font-semibold leading-snug text-text">
                        <Link href={`/listings/${l.id}`} className="hover:underline">{l.title}</Link>
                      </h3>
                      <p className="shrink-0 text-[16px] font-bold tabular-nums text-text">{euro(l.warmmiete_eur)}</p>
                    </div>
                    <p className="text-[13px] text-text-muted">{l.kiez} · {rooms(l.rooms)} · {l.size_m2} m²</p>
                    <div className="flex flex-wrap gap-1.5">
                      <RentChip rent={l.rent} short />
                      <RiskChip risk={it.risk} short />
                    </div>
                    <ul className="flex flex-col gap-0.5 text-[13px] text-text-body" aria-label="Why it's similar">
                      {it.reasons.filter((r) => r !== "Fair rent").map((r) => <li key={r}>{r}</li>)} {/* the rent chip already says it */}
                    </ul>
                    <div className="mt-auto grid grid-cols-3 gap-1.5 pt-2">
                      <Link href={`/listings/${l.id}`} className={buttonClass("dark", "!px-2 text-[13.5px]")}>View</Link>
                      <Button variant="outline" className="!px-2 text-[13.5px]" aria-pressed={saved.has(l.id)} onClick={() => saved.toggle(l.id)} aria-label={`${saved.has(l.id) ? "Saved" : "Save"}: ${l.title}`}>
                        {saved.has(l.id) ? "Saved" : "Save"}
                      </Button>
                      <Button
                        variant="outline"
                        className="!px-2 text-[13.5px]"
                        aria-pressed={inCompare}
                        disabled={!inCompare && compare.full}
                        onClick={() => compare.toggle(l.id)}
                        aria-label={`Compare: ${l.title}`}
                      >
                        {inCompare ? "Comparing" : "Compare"}
                      </Button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
          {items.length > 3 && !more && (
            <Button variant="outline" className="self-center sm:hidden" onClick={() => setMore(true)}>Show more similar flats</Button>
          )}
        </>
      )}
    </section>
  );
}
