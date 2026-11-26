import Link from "next/link";
import type { ListingOut } from "@/lib/types";
import { euro, rooms } from "@/lib/format";
import { Chip } from "@/components/ui/primitives";
import { StationChip } from "@/components/listing/VerdictChips";
import { LIFESTYLE_FACTS, LIFESTYLE_PATH } from "@/lib/lifestyle/marketing";

function Tick() {
  return (
    <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-live)" strokeWidth="2.4" className="mt-0.5 shrink-0">
      <path d="M5 12.5l4.5 4.5L19 7.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Hero side card: one real listing with its verdicts, and what every listing gets. */
export function CheckedCard({ listing, lowRisk }: { listing: ListingOut | null; lowRisk: boolean }) {
  return (
    <aside
      className="flex flex-col gap-4 rounded-xl border border-white/10 bg-white/[0.04] p-6"
      aria-labelledby="checked-heading"
      data-testid="checked-card"
    >
      <p id="checked-heading" className="text-[13px] font-semibold uppercase tracking-[0.08em] text-accent-on-ink">
        Every listing, checked
      </p>
      {listing ? (
        <Link href={`/listings/${listing.id}`} className="flex flex-col gap-2 rounded-lg bg-surface p-4 text-text hover:shadow-lg">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-[16px] font-semibold">
              {rooms(listing.rooms)} · {listing.size_m2} m² · {listing.kiez}
            </span>
            <span className="text-[18px] font-bold tabular-nums">{euro(listing.warmmiete_eur)}</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {listing.rent?.verdict === "within_limit" && <Chip tone="ok">Fair rent · in Mietspiegel range</Chip>}
            {lowRisk && <Chip tone="ok">Low scam risk</Chip>}
            <StationChip
              stop={listing.location?.rail_stop}
              modes={listing.location?.rail_modes}
              minutes={listing.location?.rail_walk_minutes}
            />
          </div>
        </Link>
      ) : (
        <div className="h-[104px] animate-pulse rounded-lg bg-white/10" />
      )}
      <ul className="flex flex-col gap-2 text-[15px] text-text-on-ink-soft">
        <li className="flex gap-2.5"><Tick /> Rent checked against the official rent index</li>
        <li className="flex gap-2.5"><Tick /> Scam signals explained, not just scored</li>
        <li className="flex gap-2.5"><Tick /> Transit, schools, parks and air around the flat</li>
      </ul>
    </aside>
  );
}

const ENTRY = [
  {
    href: LIFESTYLE_PATH,
    title: "Lifestyle match",
    body: "Pick a profile, set your budget and what matters, and watch the map re-rank Berlin's areas as you go, with reasons.",
    cta: "Start the match",
    tint: "bg-accent-tint text-accent",
    icon: <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 8a7 7 0 0 1 14 0" />,
  },
  {
    href: "/neighborhoods",
    title: "Explore neighbourhoods",
    body: `All ${LIFESTYLE_FACTS.areas} areas on one map: transit, green space, schools, safety and rents, ranked by what matters to you.`,
    cta: "Open the map",
    tint: "bg-accent-tint text-accent",
    icon: <path d="M9 4 3 6.5V20l6-2.5 6 2.5 6-2.5V4l-6 2.5L9 4zm0 0v13.5M15 6.5V20" />,
  },
  {
    href: "/rent-check",
    title: "Check a rent",
    body: "Already have an offer? Check any Berlin address against the Mietspiegel and the rent brake.",
    cta: "Check a rent",
    tint: "bg-ok-bg text-ok",
    icon: <path d="M15.5 7.5a5 5 0 1 0 0 9M6 10.5h7M6 13.5h7" />,
  },
];

export function EntryCards() {
  return (
    <section aria-labelledby="entry-heading" className="flex flex-col gap-5">
      <div>
        <h2 id="entry-heading" className="text-[26px] font-bold tracking-tight text-text">
          Not sure where to start?
        </h2>
        <p className="mt-1 text-[15px] text-text-muted">Three ways in, besides the search.</p>
      </div>
      <ul className="grid gap-4 md:grid-cols-3">
        {ENTRY.map((e) => (
          <li key={e.href}>
            <Link
              href={e.href}
              data-testid="entry-card"
              className="flex h-full flex-col gap-2 rounded-lg border border-line bg-surface p-6 hover:border-line-strong hover:shadow-sm"
            >
              <span className={`flex h-11 w-11 items-center justify-center rounded-md ${e.tint}`}>
                <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                  {e.icon}
                </svg>
              </span>
              <h3 className="mt-2 text-[18px] font-semibold text-text">{e.title}</h3>
              <p className="text-[15px] leading-relaxed text-text-muted">{e.body}</p>
              <span className="mt-auto pt-2 text-[15px] font-semibold text-accent">{e.cta}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function HowItWorks() {
  const steps = [
    ["You describe it", "Budget, rooms, area, commute, quiet or lively: in your own words."],
    ["We rank and check", "Each flat is scored on fit, its rent compared with the Mietspiegel, and screened for scam patterns."],
    ["You see why", "Every result explains itself: what matches, what doesn't, and what to ask the landlord."],
  ];
  return (
    <section id="how-it-works" aria-labelledby="how-heading" className="rounded-lg border border-line bg-surface p-7 sm:p-8">
      <h2 id="how-heading" className="text-[26px] font-bold tracking-tight text-text">
        How WohnIQ works
      </h2>
      <ol className="mt-6 grid gap-6 md:grid-cols-3">
        {steps.map(([title, body], i) => (
          <li key={title} className="flex flex-col gap-1.5">
            <span className="font-mono text-[13px] text-accent">0{i + 1}</span>
            <h3 className="text-[18px] font-semibold text-text">{title}</h3>
            <p className="text-[15px] leading-relaxed text-text-muted">{body}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
