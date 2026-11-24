import type { Measure } from "@/lib/types";
import { MeasureBar, SourceLabel } from "@/components/ui/primitives";

/** "Around this flat": the eight measures, each with its source and its place among Berlin's
 * areas. Wording is neutral (describe, don't judge). `limit` shows the first N (phones). */
export function AroundGrid({ measures, limit }: { measures: Measure[]; limit?: number }) {
  const shown = limit ? measures.slice(0, limit) : measures;
  return (
    <ul className="grid gap-3 sm:grid-cols-2" data-testid="around-grid">
      {shown.map((m) => (
        <li
          key={m.key}
          data-key={m.key}
          className="flex min-w-0 flex-col gap-1.5 rounded-md border border-line bg-surface p-4"
        >
          <div className="flex items-baseline justify-between gap-2 text-[13px] text-text-muted">
            <span>{m.label}</span>
            <SourceLabel>{m.source}</SourceLabel>
          </div>
          <p className="text-[17px] font-semibold leading-snug text-text">{m.headline}</p>
          <MeasureBar position={m.position} label={m.comparison} />
          <p className="text-[13px] text-text-body">{m.comparison}</p>
          <p className="text-[12.5px] leading-snug text-text-muted">{m.detail}</p>
        </li>
      ))}
    </ul>
  );
}
