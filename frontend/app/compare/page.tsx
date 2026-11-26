"use client";

/**
 * /compare?ids=… (T9.7): up to four flats side by side, replacing the old pop-up. The ids
 * are in the address (listing ids aren't personal), so the page can be reloaded and shared.
 * Rows: price, rent check, scam risk, the flat, location (+ a trip to a place you choose),
 * around. The best value per row is marked calmly.
 */

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getListingAround, getListingCommute, getListingDetail } from "@/lib/api";
import type { ListingDetailResponse, PlaceProfile } from "@/lib/types";
import { compareHref, idFromLink, idsFromQuery, MAX_COMPARE, writeCompare } from "@/lib/compare/list";
import { compareGroups, type CompareFlat } from "@/lib/compare/rows";
import { commuteDetail, commuteMinutes } from "@/lib/commute";
import { readSaved } from "@/lib/saved";
import { RentChip, RiskChip } from "@/components/listing/VerdictChips";
import { ListingPhoto } from "@/components/ListingPhoto";
import { Button, ButtonLink } from "@/components/ui/primitives";

type Loaded = { detail?: ListingDetailResponse | null; around?: PlaceProfile | null };

export default function ComparePage() {
  return (
    <Suspense fallback={null}>
      <CompareInner />
    </Suspense>
  );
}

function CompareInner() {
  const params = useSearchParams();
  const router = useRouter();
  const ids = useMemo(() => idsFromQuery(params.get("ids")), [params]);
  const [loaded, setLoaded] = useState<Record<string, Loaded>>({});
  const [place, setPlace] = useState("");
  const [trip, setTrip] = useState<{ to: string; byId: Record<string, CompareFlat["trip"]> } | null>(null);
  const [tripBusy, setTripBusy] = useState(false);
  const [adding, setAdding] = useState("");
  const [addError, setAddError] = useState<string | null>(null);

  // The address is the truth: keep the shared compare list in step with it.
  useEffect(() => {
    writeCompare(ids);
  }, [ids]);

  useEffect(() => {
    for (const id of ids) {
      if (id in loaded) continue;
      setLoaded((p) => ({ ...p, [id]: {} }));
      getListingDetail(id)
        .then((d) => setLoaded((p) => ({ ...p, [id]: { ...p[id], detail: d } })))
        .catch(() => setLoaded((p) => ({ ...p, [id]: { ...p[id], detail: null } })));
      getListingAround(id)
        .then((a) => setLoaded((p) => ({ ...p, [id]: { ...p[id], around: a } })))
        .catch(() => setLoaded((p) => ({ ...p, [id]: { ...p[id], around: null } })));
    }
  }, [ids, loaded]);

  const go = (next: string[]) => router.replace(next.length ? compareHref(next) : "/compare", { scroll: false });
  const missing = ids.filter((id) => loaded[id]?.detail === null);
  const ready = ids.filter((id) => loaded[id]?.detail);
  const flats: CompareFlat[] = ready.map((id) => ({ detail: loaded[id].detail!, around: loaded[id].around, trip: trip?.byId[id] ?? null }));
  const groups = compareGroups(flats, trip?.to);
  const loading = ids.some((id) => loaded[id]?.detail === undefined);
  const [savedIds, setSavedIds] = useState<string[]>([]);
  useEffect(() => setSavedIds(readSaved()), []);
  const savedToAdd = savedIds.filter((id) => !ids.includes(id));

  async function runTrip(e: React.FormEvent) {
    e.preventDefault();
    const to = place.trim();
    if (!to) return;
    setTripBusy(true);
    const pairs = await Promise.all(
      ready.map((id) =>
        getListingCommute(id, to)
          .then((r) => [id, r.commute ? { minutes: r.commute.minutes, label: [commuteMinutes(r.commute), commuteDetail(r.commute)].filter(Boolean).join(", ") } : null] as const)
          .catch(() => [id, null] as const),
      ),
    );
    setTrip({ to, byId: Object.fromEntries(pairs) });
    setTripBusy(false);
  }

  function add(e: React.FormEvent) {
    e.preventDefault();
    const id = idFromLink(adding);
    if (!id) return setAddError("Paste the link of a WohnIQ listing.");
    if (ids.includes(id)) return setAddError("That flat is already here.");
    setAdding("");
    go([...ids, id]);
  }

  if (ids.length === 0)
    return (
      <div className="mx-auto flex max-w-page flex-col gap-4 px-[18px] py-10 md:px-8">
        <h1 className="text-[36px] font-bold tracking-tight text-text">Compare flats</h1>
        <div className="rounded-lg border border-dashed border-line-strong bg-surface p-8 text-text-body">
          <p>Nothing to compare yet. Press <strong>Compare</strong> on a search result, a listing or a similar flat to add up to {MAX_COMPARE}.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <ButtonLink href="/">Search flats</ButtonLink>
            <ButtonLink href="/saved" variant="outline">Your saved flats</ButtonLink>
          </div>
        </div>
      </div>
    );

  return (
    <div className="mx-auto flex max-w-page flex-col gap-6 px-[18px] py-10 md:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[36px] font-bold tracking-tight text-text">Compare {ids.length} flat{ids.length > 1 ? "s" : ""}</h1>
          <p className="mt-1 text-[15px] text-text-muted">The best value on each line is marked. This link can be reloaded and shared.</p>
        </div>
        <Button variant="ghost" onClick={() => go([])}>Clear all</Button>
      </div>

      {missing.length > 0 && (
        <p role="status" className="rounded-md bg-chip px-4 py-3 text-[14px] text-text-body">
          {missing.length === 1 ? "One flat is" : `${missing.length} flats are`} no longer available.{" "}
          <button type="button" className="font-semibold text-accent underline" onClick={() => go(ids.filter((id) => !missing.includes(id)))}>Remove</button>
        </p>
      )}

      {/* Table: the first column stays put; flats scroll sideways on phones. */}
      <div className="overflow-x-auto rounded-lg border border-line bg-surface" data-testid="compare-table">
        <table className="w-full border-collapse text-[14px]" style={{ minWidth: 120 + ready.length * 190 }}>
          <thead>
            <tr className="border-b border-line align-top">
              <th scope="col" className="sticky left-0 z-10 w-[120px] bg-surface p-3 text-left sm:w-[160px]"><span className="sr-only">Measure</span></th>
              {ready.map((id) => {
                const d = loaded[id].detail!;
                const l = d.listing;
                return (
                  <th key={id} scope="col" className="w-[190px] p-3 text-left font-normal sm:w-[210px]" data-testid="compare-column">
                    <div className="relative mb-2 h-[110px] overflow-hidden rounded-md bg-placeholder">
                      {l.photos[0] && <ListingPhoto url={l.photos[0].url} alt="" className="absolute inset-0 h-full w-full object-cover" placeholderClassName="absolute inset-0 h-full w-full bg-placeholder" />}
                    </div>
                    <Link href={`/listings/${id}`} className="block text-[15px] font-semibold leading-snug text-text hover:underline">{l.title}</Link>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      <RentChip rent={d.rent} short />
                      <RiskChip risk={d.risk} short />
                    </div>
                    <button type="button" onClick={() => go(ids.filter((x) => x !== id))} className="mt-2 text-[13px] text-accent underline" aria-label={`Remove ${l.title}`}>
                      Remove
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          {groups.map((g) => (
            <tbody key={g.title}>
              <tr className="bg-ground">
                <th scope="colgroup" colSpan={ready.length + 1} className="sticky left-0 px-3 py-2 text-left text-[12px] font-semibold uppercase tracking-[0.06em] text-text-muted">
                  {g.title}
                </th>
              </tr>
              {g.rows.map((r) => (
                <tr key={r.label} className="border-t border-line align-top">
                  <th scope="row" className="sticky left-0 z-10 bg-surface p-3 text-left text-[13px] font-normal text-text-muted sm:text-[14px]">{r.label}</th>
                  {r.values.map((v, i) => (
                    <td key={i} className={`p-3 tabular-nums ${r.best.includes(i) ? "font-semibold text-ok" : "text-text"}`}>
                      {v}
                      {r.best.includes(i) && <span className="ml-1.5 rounded-sm bg-ok-bg px-1.5 py-px text-[11px] font-medium">best</span>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          ))}
        </table>
        {loading && <div className="h-24 animate-pulse bg-chip" aria-busy="true" />}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <form onSubmit={runTrip} className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-4">
          <label htmlFor="trip-to" className="text-[15px] font-semibold text-text">Trip to a place you choose</label>
          <p className="text-[13px] text-text-muted">For example TU Berlin, Alexanderplatz or your office street. Adds a line to the table.</p>
          <div className="flex gap-2">
            <input id="trip-to" value={place} onChange={(e) => setPlace(e.target.value)} className="min-h-tap min-w-0 flex-1 rounded-md border border-input px-3 text-[15px] outline-none focus:border-accent" placeholder="Place or address" />
            <Button type="submit" disabled={tripBusy || !place.trim()}>{tripBusy ? "Working…" : "Add trip"}</Button>
          </div>
        </form>
        {ids.length < MAX_COMPARE && (
          <form onSubmit={add} className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-4">
            <label htmlFor="add-flat" className="text-[15px] font-semibold text-text">Add another flat ({ids.length} of {MAX_COMPARE})</label>
            <div className="flex gap-2">
              <input id="add-flat" value={adding} onChange={(e) => (setAdding(e.target.value), setAddError(null))} className="min-h-tap min-w-0 flex-1 rounded-md border border-input px-3 text-[15px] outline-none focus:border-accent" placeholder="Paste a WohnIQ listing link" />
              <Button type="submit">Add</Button>
            </div>
            {addError && <p role="alert" className="text-[13px] text-warn">{addError}</p>}
            {savedToAdd.length > 0 && (
              <p className="text-[13px] text-text-body">
                Or{" "}
                <button type="button" className="font-semibold text-accent underline" onClick={() => go([...ids, ...savedToAdd].slice(0, MAX_COMPARE))}>
                  add from your saved flats
                </button>
                .
              </p>
            )}
          </form>
        )}
      </div>
    </div>
  );
}
