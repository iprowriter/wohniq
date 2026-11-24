import type { ListingLocationOut, RentOut, RiskOut } from "@/lib/types";
import { rentChip, riskChip } from "@/lib/listing/chips";
import { Chip } from "@/components/ui/primitives";
import { StopModes } from "@/components/ui/TransitIcon";

export function RentChip({ rent, short = false }: { rent?: RentOut | null; short?: boolean }) {
  const c = rentChip(rent);
  if (!c) return null;
  return (
    <span data-testid="rent-chip" data-verdict={rent?.verdict}>
      <Chip tone={c.tone}>{short ? c.short : c.text}</Chip>
    </span>
  );
}

export function RiskChip({ risk, short = false }: { risk?: RiskOut | null; short?: boolean }) {
  const c = riskChip(risk);
  if (!c) return null;
  return (
    <span data-testid="risk-chip" data-band={risk?.band}>
      <Chip tone={c.tone}>{short ? c.short : c.text}</Chip>
    </span>
  );
}

/** Nearest S/U-Bahn with its BVG icons and walking minutes ("U Moritzplatz · 4 min"). */
export function StationChip({
  stop,
  modes,
  minutes,
  compact = false,
}: {
  stop?: string | null;
  modes?: string[];
  minutes?: number | null;
  compact?: boolean;
}) {
  if (!stop) return null;
  const rail = (modes ?? []).filter((m) => m === "ubahn" || m === "sbahn");
  return (
    <span className={`inline-flex min-w-0 items-center gap-1.5 ${compact ? "text-[13px] text-text-muted" : ""}`}>
      {!compact ? (
        <Chip>
          <StopModes modes={rail.length ? rail : (modes ?? [])} size={15} />
          {stop} · {minutes} min walk
        </Chip>
      ) : (
        <>
          <StopModes modes={rail.length ? rail : (modes ?? [])} size={14} />
          <span className="truncate">
            {stop.replace(/^(S\+U|U|S) /, "")} {minutes} min
          </span>
        </>
      )}
    </span>
  );
}

export function locationLine(loc?: ListingLocationOut | null, kiez?: string): string {
  if (!loc) return kiez ?? "";
  return [loc.district, loc.planning_area, loc.street].filter(Boolean).join(" · ");
}
