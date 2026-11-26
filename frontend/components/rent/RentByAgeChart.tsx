import { euro2 } from "@/lib/format";

/** "How rents compare in this area": Mietspiegel mean by building age (to scale, from 0). */
export function RentByAgeChart({
  bars,
  selected,
}: {
  bars: { period: string; label: string; mean: number }[];
  selected: string | null;
}) {
  if (!bars.length) return null;
  const max = Math.max(...bars.map((b) => b.mean));
  return (
    <ol
      className="flex h-44 items-end gap-1.5 sm:gap-2"
      aria-label="Mietspiegel mean by building age"
    >
      {bars.map((b) => {
        const on = b.period === selected;
        return (
          <li key={b.period} className="flex min-w-0 flex-1 flex-col items-center justify-end gap-1">
            <span className={`text-[11px] tabular-nums ${on ? "font-semibold text-text" : "text-text-muted"}`}>
              {euro2(b.mean)}
            </span>
            <span
              className={`w-full rounded-t-sm ${on ? "bg-accent" : "bg-accent-soft"}`}
              style={{ height: `${Math.max(6, (b.mean / max) * 120)}px` }}
              aria-hidden="true"
            />
            <span
              className={`w-full truncate text-center text-[10.5px] ${on ? "font-semibold text-text" : "text-text-muted"}`}
              title={b.label}
            >
              {b.label.replace(/^before /, "<").replace(/ \((East|West)\)/, "").replace(/(\d{2})(\d{2})–\d{2}(\d{2})/, "$1$2–$3")}
            </span>
            <span className="sr-only">
              {b.label}: {euro2(b.mean)}
              {on ? " (your building age)" : ""}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
