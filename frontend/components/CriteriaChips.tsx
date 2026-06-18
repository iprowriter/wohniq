import type { SearchCriteria } from "@/lib/types";

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-gray-200 bg-white px-3 py-1 text-xs text-gray-600">
      {children}
    </span>
  );
}

export function CriteriaChips({ criteria }: { criteria: SearchCriteria }) {
  const chips: string[] = [];
  if (criteria.work_location) chips.push(`near ${criteria.work_location}`);
  if (criteria.max_warm_rent) chips.push(`≤ €${criteria.max_warm_rent} warm`);
  if (criteria.min_rooms) chips.push(`${criteria.min_rooms}+ rooms`);
  if (criteria.min_size_m2) chips.push(`${criteria.min_size_m2}+ m²`);
  if (criteria.quiet_priority) chips.push("quiet");
  if (criteria.transport_priority) chips.push("good transport");
  if (criteria.furnished === true) chips.push("furnished");
  if (criteria.furnished === false) chips.push("unfurnished");
  for (const a of criteria.desired_amenities) chips.push(a);

  if (chips.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-gray-400">Understood as</span>
      {chips.map((c) => (
        <Chip key={c}>{c}</Chip>
      ))}
    </div>
  );
}
