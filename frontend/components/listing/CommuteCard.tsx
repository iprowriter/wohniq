"use client";

/** Trip time from the flat to a place the user types; the stops map underneath. */

import { useEffect, useState } from "react";
import { getListingCommute } from "@/lib/api";
import type { CommuteOut } from "@/lib/types";
import { StopsMap } from "@/components/place/StopsMap";

const PLACE_KEY = "wohniq_commute_place"; // this tab only

export function CommuteCard({ listingId, lat, lng }: { listingId: string; lat: number; lng: number }) {
  const [place, setPlace] = useState("Alexanderplatz");
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(PLACE_KEY);
      if (saved) setPlace(saved);
    } catch {
      /* unavailable */
    }
  }, []);
  const [result, setResult] = useState<{ to: string; commute: CommuteOut | null; note: string | null } | null>(null);
  const [busy, setBusy] = useState(false);

  async function go() {
    if (place.trim().length < 2) return;
    setBusy(true);
    try {
      sessionStorage.setItem(PLACE_KEY, place.trim());
    } catch {
      /* ignore */
    }
    try {
      setResult(await getListingCommute(listingId, place.trim()));
    } catch {
      setResult({ to: place.trim(), commute: null, note: "Couldn't work out the trip time right now." });
    } finally {
      setBusy(false);
    }
  }

  const c = result?.commute;
  return (
    <section className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-5" aria-labelledby="commute-heading">
      <h2 id="commute-heading" className="text-[17px] font-semibold text-text">
        Commute
      </h2>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void go();
        }}
      >
        <label htmlFor="commute-to" className="sr-only">
          Where do you go most?
        </label>
        <input
          id="commute-to"
          value={place}
          onChange={(e) => setPlace(e.target.value)}
          placeholder="A place, e.g. TU Berlin"
          className="min-h-tap min-w-0 flex-1 rounded-md border border-input bg-surface px-3 text-[15px] text-text outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
        />
        <button type="submit" disabled={busy} className="min-h-tap rounded-md bg-ink px-4 text-[15px] font-semibold text-white disabled:opacity-60">
          {busy ? "…" : "Go"}
        </button>
      </form>
      {result && (
        <div data-testid="commute-result">
          {c ? (
            <p className="flex items-baseline justify-between gap-3 text-[15px] text-text-body">
              <span>To {result.to}</span>
              <span className="text-[20px] font-semibold tabular-nums text-text">
                {c.estimated ? "≈" : ""}
                {c.minutes} min
              </span>
            </p>
          ) : null}
          {c && (
            <p className="text-[13px] text-text-muted">
              {c.estimated ? "estimated" : "live BVG journey"}
              {c.changes != null ? ` · ${c.changes === 0 ? "direct" : `${c.changes} change${c.changes > 1 ? "s" : ""}`}` : ""}
            </p>
          )}
          {result.note && <p className="mt-1 text-[12.5px] leading-snug text-text-muted">{result.note}</p>}
        </div>
      )}
      <StopsMap lat={lat} lng={lng} height={260} label="This flat" />
      <p className="text-[12px] leading-snug text-text-muted">
        Stops within 700 m with what stops there · dashed circle: 500 m · offline map ©
        OpenStreetMap contributors
      </p>
    </section>
  );
}
