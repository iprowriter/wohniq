"use client";

/** Saved flats, kept in this browser (no account). Saved searches come in T9.7. */

import { useEffect, useState } from "react";
import { getListingDetail } from "@/lib/api";
import type { ListingOut } from "@/lib/types";
import { useSaved } from "@/lib/useSaved";
import { FeaturedCard } from "@/components/FeaturedCard";
import { Button, ButtonLink } from "@/components/ui/primitives";

export default function SavedPage() {
  const saved = useSaved();
  const [listings, setListings] = useState<Record<string, ListingOut | null>>({});

  useEffect(() => {
    const missing = saved.ids.filter((id) => !(id in listings));
    if (!missing.length) return;
    Promise.all(
      missing.map((id) =>
        getListingDetail(id)
          .then((d) => [id, { ...d.listing, rent: d.rent, location: d.location }] as const)
          .catch(() => [id, null] as const),
      ),
    ).then((pairs) => setListings((prev) => ({ ...prev, ...Object.fromEntries(pairs) })));
  }, [saved.ids, listings]);

  return (
    <div className="mx-auto flex max-w-page flex-col gap-6 px-[18px] py-10 md:px-8">
      <div>
        <h1 className="text-[36px] font-bold tracking-tight text-text">Saved flats</h1>
        <p className="mt-1 text-[15px] text-text-muted">Kept in this browser only. No account needed.</p>
      </div>
      {saved.ids.length === 0 ? (
        <div className="rounded-lg border border-dashed border-line-strong bg-surface p-8 text-text-body">
          <p>Nothing saved yet. Press <strong>Save</strong> on a search result to keep it here.</p>
          <ButtonLink href="/" className="mt-4">Search flats</ButtonLink>
        </div>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="saved-list">
          {saved.ids.map((id) => {
            const l = listings[id];
            return (
              <li key={id} className="flex flex-col gap-2">
                {l ? <FeaturedCard listing={l} /> : l === null ? (
                  <div className="rounded-lg border border-line bg-surface p-4 text-[14px] text-text-muted">This listing is no longer available.</div>
                ) : (
                  <div className="h-64 animate-pulse rounded-lg bg-chip" />
                )}
                <Button variant="outline" onClick={() => saved.toggle(id)}>Remove</Button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
