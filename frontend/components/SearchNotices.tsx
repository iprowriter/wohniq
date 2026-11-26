import type { SearchNotice } from "@/lib/types";

function euro(n: number) {
  return `€${n.toLocaleString("en-GB")}`;
}

const STYLES: Record<string, { box: string; icon: string; title: string }> = {
  budget: { box: "border-transparent bg-warn-bg", icon: "text-warn", title: "text-warn" },
  nearby: { box: "border-transparent bg-accent-tint", icon: "text-accent", title: "text-text" },
  empty: { box: "border-line bg-surface", icon: "text-text-muted", title: "text-text" },
};

function styleFor(kind: SearchNotice["kind"]) {
  if (kind === "budget_too_low" || kind === "budget_too_low_in_some_areas") return STYLES.budget;
  if (kind === "nearby_results") return STYLES.nearby;
  return STYLES.empty;
}

function Icon({ kind }: { kind: SearchNotice["kind"] }) {
  if (kind === "nearby_results") {
    return (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12z" />
        <circle cx="12" cy="10" r="2.5" />
      </svg>
    );
  }
  if (kind === "budget_too_low" || kind === "budget_too_low_in_some_areas") {
    return (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M17 7a6 6 0 1 0 0 10M4 10h9M4 14h9" />
      </svg>
    );
  }
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

interface Props {
  notices: SearchNotice[];
  /** Re-run the same search with this warm-rent budget. */
  onRaiseBudget?: (budget: number) => void;
  busy?: boolean;
}

/** Explains empty or fallback results: budget too low (with a one-click fix), nearby flats. */
export function SearchNotices({ notices, onRaiseBudget, busy = false }: Props) {
  if (!notices.length) return null;
  return (
    <div className="mb-5 space-y-3" data-testid="search-notices">
      {notices.map((n) => {
        const s = styleFor(n.kind);
        const budgets: { value: number; label: string }[] = [];
        if (n.suggested_budget) {
          const count = n.options_at_suggested;
          budgets.push({
            value: n.suggested_budget,
            label: `Search with ${euro(n.suggested_budget)}${count ? ` · ${count} flat${count === 1 ? "" : "s"}` : ""}`,
          });
        }
        if (n.comfortable_budget && n.comfortable_budget !== n.suggested_budget) {
          const count = n.options_at_comfortable;
          budgets.push({
            value: n.comfortable_budget,
            label: `${euro(n.comfortable_budget)}${count ? ` · ${count} flats` : ""}`,
          });
        }
        return (
          <div
            key={`${n.kind}-${n.title}`}
            role="status"
            data-kind={n.kind}
            className={`flex gap-3 rounded-xl border px-4 py-3 ${s.box}`}
          >
            <span className={`mt-0.5 flex-shrink-0 ${s.icon}`}>
              <Icon kind={n.kind} />
            </span>
            <div className="min-w-0 flex-1">
              <p className={`text-sm font-semibold ${s.title}`}>{n.title}</p>
              <p className="mt-0.5 text-sm leading-relaxed text-text-body">{n.message}</p>
              {onRaiseBudget && budgets.length > 0 && (
                <div className="mt-2.5 flex flex-wrap gap-2">
                  {budgets.map((b, i) => (
                    <button
                      key={b.value}
                      type="button"
                      disabled={busy}
                      onClick={() => onRaiseBudget(b.value)}
                      className={
                        i === 0
                          ? "inline-flex min-h-tap items-center rounded-md bg-ink px-4 text-sm font-semibold text-white hover:bg-[#1c2436] disabled:opacity-50"
                          : "inline-flex min-h-tap items-center rounded-md border border-line-strong bg-surface px-4 text-sm font-semibold text-text hover:bg-ground disabled:opacity-50"
                      }
                    >
                      {b.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
