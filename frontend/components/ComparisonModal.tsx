"use client";

import { useEffect } from "react";
import type { SearchResultItem, RiskBand } from "@/lib/types";

const RISK_STYLES: Record<RiskBand, string> = {
  low: "bg-green-100 text-green-800",
  caution: "bg-amber-100 text-amber-800",
  high: "bg-red-100 text-red-800",
};

const RISK_LABELS: Record<RiskBand, string> = {
  low: "Low",
  caution: "Caution",
  high: "High",
};

function euro(n: number) {
  return `€${n.toLocaleString("de-DE")}`;
}

function Cell({ children, highlight }: { children: React.ReactNode; highlight?: boolean }) {
  return (
    <td className={`px-4 py-3 text-sm text-gray-700 align-top ${highlight ? "bg-indigo-50" : ""}`}>
      {children}
    </td>
  );
}

function RowLabel({ children }: { children: React.ReactNode }) {
  return (
    <td className="sticky left-0 bg-white px-4 py-3 text-xs font-semibold uppercase tracking-wide text-gray-400 whitespace-nowrap">
      {children}
    </td>
  );
}

interface Props {
  items: SearchResultItem[];
  onClose: () => void;
}

export function ComparisonModal({ items, onClose }: Props) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const best = {
    price: Math.min(...items.map((i) => i.listing.warmmiete_eur)),
    commute: Math.min(...items.filter((i) => i.commute).map((i) => i.commute!.minutes)),
    score: Math.max(...items.map((i) => i.score)),
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="relative w-full max-w-5xl max-h-[90vh] overflow-hidden rounded-2xl bg-white shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <h2 className="text-base font-semibold text-gray-900">
            Comparing {items.length} listings
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
            aria-label="Close comparison"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Scrollable table */}
        <div className="overflow-auto flex-1">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="sticky left-0 bg-white px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-400 w-32">
                  Field
                </th>
                {items.map((item) => (
                  <th
                    key={item.listing.id}
                    className="px-4 py-3 text-left text-sm font-semibold text-gray-900 min-w-[180px]"
                  >
                    <div className="line-clamp-2 leading-snug">{item.listing.title}</div>
                    <div className="mt-0.5 text-xs font-normal text-gray-400">{item.listing.kiez}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {/* Price */}
              <tr>
                <RowLabel>Warm rent</RowLabel>
                {items.map((item) => (
                  <Cell key={item.listing.id} highlight={item.listing.warmmiete_eur === best.price}>
                    <span className={item.listing.warmmiete_eur === best.price ? "font-semibold text-indigo-700" : ""}>
                      {euro(item.listing.warmmiete_eur)}
                    </span>
                    {item.listing.warmmiete_eur === best.price && items.length > 1 && (
                      <span className="ml-1.5 text-xs text-indigo-500">lowest</span>
                    )}
                    <div className="text-xs text-gray-400">
                      {euro(item.listing.kaltmiete_eur)} cold + {euro(item.listing.nebenkosten_eur)} extras
                    </div>
                  </Cell>
                ))}
              </tr>

              {/* Size */}
              <tr>
                <RowLabel>Size</RowLabel>
                {items.map((item) => (
                  <Cell key={item.listing.id}>
                    {item.listing.size_m2} m² · {item.listing.rooms} room{item.listing.rooms !== 1 ? "s" : ""}
                  </Cell>
                ))}
              </tr>

              {/* Commute */}
              <tr>
                <RowLabel>Commute</RowLabel>
                {items.map((item) => (
                  <Cell key={item.listing.id} highlight={item.commute?.minutes === best.commute}>
                    {item.commute ? (
                      <>
                        <span className={item.commute.minutes === best.commute ? "font-semibold text-indigo-700" : ""}>
                          {item.commute.minutes} min
                        </span>
                        {item.commute.minutes === best.commute && items.filter((i) => i.commute).length > 1 && (
                          <span className="ml-1.5 text-xs text-indigo-500">fastest</span>
                        )}
                        <div className="text-xs text-gray-400">
                          {item.commute.changes === 0 ? "Direct" : `${item.commute.changes} change${item.commute.changes > 1 ? "s" : ""}`}
                        </div>
                      </>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </Cell>
                ))}
              </tr>

              {/* Neighborhood */}
              <tr>
                <RowLabel>Neighborhood</RowLabel>
                {items.map((item) => (
                  <Cell key={item.listing.id}>
                    {item.neighborhood?.summary ? (
                      <span>{item.neighborhood.summary}</span>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </Cell>
                ))}
              </tr>

              {/* Risk */}
              <tr>
                <RowLabel>Risk</RowLabel>
                {items.map((item) => (
                  <Cell key={item.listing.id}>
                    {item.risk ? (
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${RISK_STYLES[item.risk.band]}`}
                      >
                        {RISK_LABELS[item.risk.band]} · {item.risk.score}
                      </span>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </Cell>
                ))}
              </tr>

              {/* Fit score */}
              <tr>
                <RowLabel>Fit score</RowLabel>
                {items.map((item) => (
                  <Cell key={item.listing.id} highlight={item.score === best.score}>
                    <span className={item.score === best.score ? "font-semibold text-indigo-700" : ""}>
                      {(item.score * 100).toFixed(0)}%
                    </span>
                    {item.score === best.score && items.length > 1 && (
                      <span className="ml-1.5 text-xs text-indigo-500">best fit</span>
                    )}
                  </Cell>
                ))}
              </tr>

              {/* AI summary */}
              <tr>
                <RowLabel>AI summary</RowLabel>
                {items.map((item) => (
                  <Cell key={item.listing.id}>
                    <p className="text-xs leading-relaxed">{item.explanation.summary}</p>
                    {item.explanation.caveats.length > 0 && (
                      <ul className="mt-1 space-y-0.5">
                        {item.explanation.caveats.map((c) => (
                          <li key={c} className="text-xs text-amber-700">! {c}</li>
                        ))}
                      </ul>
                    )}
                  </Cell>
                ))}
              </tr>

              {/* Furnished */}
              <tr>
                <RowLabel>Furnished</RowLabel>
                {items.map((item) => (
                  <Cell key={item.listing.id}>
                    {item.listing.furnished ? "Yes" : "No"}
                  </Cell>
                ))}
              </tr>

              {/* Available */}
              {items.some((i) => i.listing.available_from) && (
                <tr>
                  <RowLabel>Available</RowLabel>
                  {items.map((item) => (
                    <Cell key={item.listing.id}>
                      {item.listing.available_from ?? <span className="text-gray-400">—</span>}
                    </Cell>
                  ))}
                </tr>
              )}

              {/* Deposit */}
              {items.some((i) => i.listing.deposit_eur) && (
                <tr>
                  <RowLabel>Deposit</RowLabel>
                  {items.map((item) => (
                    <Cell key={item.listing.id}>
                      {item.listing.deposit_eur ? euro(item.listing.deposit_eur) : <span className="text-gray-400">—</span>}
                    </Cell>
                  ))}
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
