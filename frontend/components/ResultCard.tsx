import type { SearchResultItem } from "@/lib/types";
import { RiskBadge } from "./RiskBadge";

function euro(n: number) {
  return `€${n.toLocaleString("de-DE")}`;
}

export function ResultCard({ item }: { item: SearchResultItem }) {
  const { listing, explanation, commute, neighborhood, risk } = item;
  const cover = listing.photos[0];
  const isHighRisk = risk?.band === "high";

  return (
    <article
      className={`overflow-hidden rounded-xl border bg-white ${
        isHighRisk ? "border-red-200" : "border-gray-200"
      }`}
    >
      <div className="flex gap-4 p-4">
        {cover ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={cover.url}
            alt={listing.title}
            className="h-28 w-36 flex-shrink-0 rounded-lg object-cover"
          />
        ) : (
          <div className="h-28 w-36 flex-shrink-0 rounded-lg bg-gray-100" />
        )}

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-base font-medium leading-tight">{listing.title}</h3>
              <p className="mt-0.5 text-sm text-gray-500">
                {listing.kiez} · {listing.size_m2} m² · {listing.rooms} rooms
              </p>
            </div>
            <RiskBadge risk={risk} />
          </div>

          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600">
            <span>{euro(listing.warmmiete_eur)} warm</span>
            {commute && (
              <span>
                {commute.minutes} min
                {commute.changes > 0 ? ` · ${commute.changes} change${commute.changes > 1 ? "s" : ""}` : " · direct"}
              </span>
            )}
            {neighborhood?.summary && <span>{neighborhood.summary}</span>}
          </div>
        </div>
      </div>

      <div
        className={`mx-4 mb-4 rounded-lg px-3 py-2.5 ${
          isHighRisk ? "bg-red-50" : "bg-gray-50"
        }`}
      >
        <p className={`text-sm font-medium ${isHighRisk ? "text-red-800" : ""}`}>
          {explanation.summary}
        </p>
        <ul className="mt-1 space-y-0.5">
          {explanation.reasons.map((r) => (
            <li key={r} className="text-sm text-gray-700">
              + {r}
            </li>
          ))}
          {explanation.caveats.map((c) => (
            <li key={c} className="text-sm text-amber-700">
              ! {c}
            </li>
          ))}
        </ul>

        {risk && risk.band !== "low" && risk.signals.length > 0 && (
          <div className="mt-2 border-t border-black/5 pt-2">
            <ul className="space-y-0.5">
              {risk.signals.map((s) => (
                <li key={s.name} className="text-sm text-red-700">
                  ⚠ {s.evidence}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </article>
  );
}
