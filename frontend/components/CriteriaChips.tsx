import Link from "next/link";
import type { SearchCriteria } from "@/lib/types";

/** What the parser understood, as chips on the dark results hero. */
export function criteriaChips(criteria: SearchCriteria): string[] {
  const chips: string[] = [];
  const areas = criteria.areas ?? [];
  if (areas.length) chips.push(`in ${areas.join(" / ")}`);
  for (const a of criteria.excluded_areas ?? []) chips.push(`not ${a}`);
  if (criteria.work_location) chips.push(`work near ${criteria.work_location}`);
  if (criteria.max_warm_rent) chips.push(`≤ €${criteria.max_warm_rent.toLocaleString("en-GB")} warm`);
  if (criteria.min_rooms) chips.push(`${criteria.min_rooms}+ rooms`);
  if (criteria.min_size_m2) chips.push(`${criteria.min_size_m2}+ m²`);
  if (criteria.quiet_priority) chips.push("quiet");
  if (criteria.transport_priority) chips.push("good transport");
  if (criteria.furnished === true) chips.push("furnished");
  if (criteria.furnished === false) chips.push("unfurnished");
  for (const a of criteria.desired_amenities) chips.push(a);
  return chips;
}

export function CriteriaChips({ criteria }: { criteria: SearchCriteria }) {
  const chips = criteriaChips(criteria);
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="criteria-chips">
      <span className="text-[14px] text-text-on-ink-muted">We understood:</span>
      {chips.length === 0 && <span className="text-[14px] text-text-on-ink-muted">no specific wishes</span>}
      {chips.map((c) => (
        <span
          key={c}
          className={`rounded-full border px-3 py-1 text-[14px] ${
            c.startsWith("in ") ? "border-accent-on-ink/60 bg-accent/20 text-white" : "border-white/20 text-text-on-ink-soft"
          }`}
        >
          {c}
        </span>
      ))}
      <Link href="/lifestyle" className="text-[14px] text-accent-on-ink underline underline-offset-2 hover:text-white">
        Not sure where? Take the lifestyle match
      </Link>
    </div>
  );
}
