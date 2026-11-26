"use client";

import Link from "next/link";
import type { SearchResultItem } from "@/lib/types";
import { euro } from "@/lib/format";
import { worthAsking } from "@/lib/listing/chips";
import { commuteMinutes, commuteTooltip } from "@/lib/commute";
import { Button, buttonClass, Chip } from "@/components/ui/primitives";
import { RentChip, RiskChip, StationChip, locationLine } from "@/components/listing/VerdictChips";
import { ListingPhoto } from "./ListingPhoto";

const NAV_FLAG = "wohniq_navigating_to_listing";

interface Props {
  item: SearchResultItem;
  compared?: boolean;
  onToggleCompare?: (id: string) => void;
  compareDisabled?: boolean;
  saved?: boolean;
  onToggleSave?: (id: string) => void;
  highlighted?: boolean;
  onHover?: (id: string | null) => void;
  isNew?: boolean; // new since the last run of this saved search
}

function AreaBadge({ match }: { match: NonNullable<SearchResultItem["area_match"]> }) {
  const inArea = match.status === "in_area";
  return (
    <span
      data-testid="area-badge"
      title={
        inArea
          ? `In ${match.area}, an area you asked for`
          : `Not in the areas you asked for: ${match.distance_km?.toFixed(1)} km from ${match.area}`
      }
      className={`inline-flex items-center rounded-sm px-2 py-0.5 text-[13px] font-medium ${
        inArea ? "bg-accent-tint text-accent" : "bg-warn-bg text-warn"
      }`}
    >
      {match.label}
    </span>
  );
}

function facts(item: SearchResultItem): string {
  const l = item.listing;
  const r = `${l.rooms % 1 === 0 ? Math.round(l.rooms) : l.rooms} rooms`;
  const parts = [r, `${l.size_m2} m²`];
  if (l.year_built) parts.push(`built ${l.year_built}`);
  if (l.available_from) {
    const d = new Date(l.available_from);
    parts.push(`from ${d.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`);
  }
  if (l.furnished) parts.push("furnished");
  return parts.join(" · ");
}

/** One search result: fit, rent check, risk, station or commute, and why it ranks here. */
export function ResultCard({
  item,
  compared = false,
  onToggleCompare,
  compareDisabled = false,
  saved = false,
  onToggleSave,
  highlighted = false,
  onHover,
  isNew = false,
}: Props) {
  const { listing, explanation, commute, risk, area_match } = item;
  const cover = listing.photos[0];
  const fit = Math.round(item.score * 100);
  const ask = worthAsking(listing.rent, risk);
  const href = `/listings/${listing.id}`;

  return (
    <article
      data-testid="result-card"
      data-id={listing.id}
      onMouseEnter={() => onHover?.(listing.id)}
      onMouseLeave={() => onHover?.(null)}
      className={`grid overflow-hidden rounded-lg border bg-surface sm:grid-cols-[260px_1fr] ${
        highlighted ? "border-accent ring-1 ring-accent" : compared ? "border-accent" : "border-line"
      }`}
    >
      <Link
        href={href}
        className="relative block min-h-[180px] bg-placeholder"
        onClick={() => sessionStorage.setItem(NAV_FLAG, "1")}
        tabIndex={-1}
        aria-hidden="true"
      >
        {cover && (
          <ListingPhoto
            url={cover.url}
            alt=""
            className="absolute inset-0 h-full w-full object-cover"
            placeholderClassName="absolute inset-0 h-full w-full bg-placeholder"
          />
        )}
        <span className="absolute left-3 top-3 rounded-full bg-ink px-2.5 py-1 text-[13px] font-semibold text-white">
          {fit} fit
        </span>
        {isNew && (
          <span className="absolute right-3 top-3 rounded-full bg-accent px-2.5 py-1 text-[13px] font-semibold text-white" data-testid="new-badge">
            New
          </span>
        )}
      </Link>
      <div className="flex min-w-0 flex-col gap-2.5 p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h3 className="text-[18px] font-semibold leading-snug text-text">
              <Link href={href} onClick={() => sessionStorage.setItem(NAV_FLAG, "1")} className="hover:underline">
                {listing.title}
              </Link>
            </h3>
            <p className="text-[14px] text-text-muted">{locationLine(listing.location, listing.kiez)}</p>
          </div>
          <div className="shrink-0 text-right">
            <p className="text-[22px] font-bold tabular-nums text-text">{euro(listing.warmmiete_eur)}</p>
            <p className="text-[13px] text-text-muted">warm / month</p>
          </div>
        </div>
        <p className="text-[14px] text-text-body">{facts(item)}</p>
        <div className="flex flex-wrap gap-1.5">
          <RentChip rent={listing.rent} />
          <RiskChip risk={risk} />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {commute ? (
            <span title={commuteTooltip(commute)}>
              <Chip>{commuteMinutes(commute)}</Chip>
            </span>
          ) : (
            <StationChip
              stop={listing.location?.rail_stop}
              modes={listing.location?.rail_modes}
              minutes={listing.location?.rail_walk_minutes}
            />
          )}
          {area_match && <AreaBadge match={area_match} />}
        </div>
        <p className="text-[14.5px] leading-relaxed text-text-body" data-testid="result-why" data-source={item.explanation_source ?? "pending"}>
          {explanation.summary}
        </p>
        {ask && <p className="text-[14px] leading-relaxed text-warn">{ask}</p>}
        <div className="mt-1 flex flex-wrap gap-2">
          <Link
            href={href}
            className={buttonClass("dark")}
            onClick={() => sessionStorage.setItem(NAV_FLAG, "1")}
          >
            View dossier
          </Link>
          {onToggleCompare && (
            <Button
              variant="outline"
              aria-pressed={compared}
              disabled={compareDisabled && !compared}
              onClick={() => onToggleCompare(listing.id)}
            >
              {compared ? "Comparing" : "Compare"}
            </Button>
          )}
          {onToggleSave && (
            <Button variant="outline" aria-pressed={saved} onClick={() => onToggleSave(listing.id)}>
              {saved ? "Saved" : "Save"}
            </Button>
          )}
        </div>
      </div>
    </article>
  );
}
