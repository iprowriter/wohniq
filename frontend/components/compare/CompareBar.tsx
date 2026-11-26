"use client";

/** "Compare (2) · Open": follows the user across pages while the compare list has flats. */

import { usePathname } from "next/navigation";
import { useCompare } from "@/lib/compare/useCompare";
import { compareHref, MAX_COMPARE } from "@/lib/compare/list";
import { Button, ButtonLink } from "@/components/ui/primitives";

export function CompareBar() {
  const pathname = usePathname() ?? "/";
  const compare = useCompare();
  const n = compare.ids.length;
  // Not on /compare itself, and not on the listing page's phone layout (its own bottom bar).
  if (!n || pathname.startsWith("/compare")) return null;
  const onListing = pathname.startsWith("/listings/");
  return (
    <div
      className={`no-print fixed inset-x-0 z-[1040] border-t border-line bg-surface/95 px-[18px] py-2.5 shadow-lg backdrop-blur-sm ${onListing ? "bottom-[76px] md:bottom-0" : "bottom-0"}`}
      role="region"
      aria-label="Compare list"
      data-testid="compare-bar"
    >
      <div className="mx-auto flex max-w-page items-center justify-between gap-3">
        <p className="text-[14px] text-text-body">
          <span className="font-semibold text-text">Compare ({n})</span>
          <span className="text-text-muted"> · {n < 2 ? "add one more flat" : `up to ${MAX_COMPARE}`}</span>
        </p>
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={compare.clear}>Clear</Button>
          <ButtonLink href={compareHref(compare.ids)} aria-disabled={n < 2} className={n < 2 ? "pointer-events-none opacity-50" : ""} tabIndex={n < 2 ? -1 : undefined}>
            Open
          </ButtonLink>
        </div>
      </div>
    </div>
  );
}
