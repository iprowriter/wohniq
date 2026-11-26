"use client";

/**
 * The rent check page (F11, ADR-0017). Everything about the user's flat (size, rent,
 * features, energy value) is computed here in the browser with lib/rent/check.ts and never
 * sent to the server or put in a URL. Only the address is looked up (public data), plus the
 * area profile and departures for its coordinates.
 */

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getAddress, getListingDetail, getPlaceProfile, getRentIndex } from "@/lib/api";
import type { AddressOut, PlaceProfile } from "@/lib/types";
import type { RentIndex } from "@/lib/rent/index";
import { ageIdForYear, ageOptions, checkRent, rentByPeriod, type RentResult } from "@/lib/rent/check";
import { explainResult, VERDICT_TITLE, verdictTone } from "@/lib/rent/explain";
import { euro, euro2 } from "@/lib/format";
import { AddressSearch } from "./AddressSearch";
import { RentByAgeChart } from "./RentByAgeChart";
import { RentScale } from "@/components/ui/RentScale";
import { Button, ButtonLink, SectionHeading } from "@/components/ui/primitives";
import { AroundGrid } from "@/components/place/AroundGrid";
import { RightNowCard } from "@/components/place/RightNowCard";
import { StopsMap } from "@/components/place/StopsMap";

type Entry = {
  key: string;
  address: AddressOut;
  size: number;
  ageLabel: string;
  cold: number;
  result: RentResult;
};

const COMPARE_KEY = "wohniq_rent_compare"; // sessionStorage: this browser tab only
const MAX_COMPARE = 4;

function loadCompare(): Entry[] {
  try {
    return JSON.parse(sessionStorage.getItem(COMPARE_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function saveCompare(entries: Entry[]) {
  try {
    sessionStorage.setItem(COMPARE_KEY, JSON.stringify(entries));
  } catch {
    /* storage unavailable: the comparison just isn't kept */
  }
}

const inputClass =
  "min-h-tap w-full rounded-md border border-input bg-surface px-3.5 text-base text-text outline-none placeholder:text-text-faint focus:border-accent focus:ring-2 focus:ring-accent/20";

/** `listingId`: opened from a listing's "Check this rent"; its figures fill the form. */
export function RentCheck({ listingId }: { listingId?: string }) {
  const [index, setIndex] = useState<RentIndex | null>(null);
  const [indexError, setIndexError] = useState<string | null>(null);
  const [address, setAddress] = useState<AddressOut | null>(null);
  const [size, setSize] = useState("");
  const [ageId, setAgeId] = useState("pre1918");
  const [cold, setCold] = useState("");
  const [energy, setEnergy] = useState("");
  const [energyDemand, setEnergyDemand] = useState(false);
  const [noHotWater, setNoHotWater] = useState(false);
  const [noHeating, setNoHeating] = useState(false);
  const [features, setFeatures] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<RentResult | null>(null);
  const [checked, setChecked] = useState<{ size: number; cold: number; ageLabel: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [profile, setProfile] = useState<PlaceProfile | null>(null);
  const [compare, setCompare] = useState<Entry[]>([]);
  const [fromListing, setFromListing] = useState<{ id: string; title: string } | null>(null);
  const [addressKey, setAddressKey] = useState(0); // remounts the address box after a prefill
  const [runWhenReady, setRunWhenReady] = useState(false);

  useEffect(() => {
    getRentIndex().then(setIndex).catch((e) => setIndexError(String(e.message ?? e)));
    setCompare(loadCompare());
  }, []);

  // Prefill from a listing: its matched address, size, building age and cold rent (the
  // listing is a sample, so its id in the URL says nothing about the user).
  useEffect(() => {
    if (!listingId) return;
    let live = true;
    getListingDetail(listingId)
      .then(async (d) => {
        const l = d.listing;
        const id = d.location?.address_id;
        const a = id != null ? await getAddress(id).catch(() => null) : null;
        if (!live) return;
        if (a) {
          setAddress(a);
          setAddressKey((k) => k + 1);
        }
        setSize(String(l.size_m2));
        setCold(String(l.kaltmiete_eur));
        if (l.year_built) setAgeId(ageIdForYear(l.year_built, a?.east ?? d.location?.east ?? false));
        setFromListing({ id: l.id, title: l.title });
        if (a) setRunWhenReady(true);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [listingId]);

  const ages = ageOptions(address?.east ?? false);
  const age = ages.find((a) => a.id === ageId) ?? ages[0];
  useEffect(() => {
    if (!ages.some((a) => a.id === ageId)) setAgeId(ages[0].id);
  }, [ages, ageId]);

  const period = useMemo(() => {
    if (!index) return null;
    const side = address?.east ? "east" : "west";
    for (const [k, p] of Object.entries(index.periods)) {
      if ((p.from ?? -Infinity) <= age.year && age.year <= p.to && (p.side === null || p.side === side)) return k;
    }
    return null;
  }, [index, age, address]);

  useEffect(() => {
    setProfile(null);
    if (address) {
      getPlaceProfile(address.lat, address.lng, address.location_class).then(setProfile).catch(() => {});
    }
  }, [address]);

  useEffect(() => {
    if (runWhenReady && index && address) {
      setRunWhenReady(false);
      submit();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runWhenReady, index, address, ageId]);

  function toggle(id: string) {
    setFeatures((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function submit() {
    setError(null);
    if (!index) return;
    if (!address) return setError("Pick an address from the list first.");
    const s = Number(size.replace(",", "."));
    const c = Number(cold.replace(",", "."));
    if (!(s >= 10 && s <= 400)) return setError("Enter the living space in m² (10–400).");
    if (!(c > 0)) return setError("Enter your monthly net cold rent in euros.");
    const e = energy.trim() ? Number(energy.replace(",", ".")) : null;
    const r = checkRent(
      {
        location_class: address.location_class,
        east: address.east,
        year_built: age.year,
        size_m2: s,
        cold_rent_eur: c,
        features: [...features],
        energy_kwh: e != null && e > 0 ? e : null,
        energy_is_demand: energyDemand,
        energy_without_hot_water: noHotWater,
        no_central_heating_or_bath: noHeating,
      },
      index.rows,
      index.periods,
      index.checklist,
    );
    setResult(r);
    setChecked({ size: s, cold: c, ageLabel: age.label });
    setTimeout(() => document.getElementById("rent-result")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }

  function addToCompare() {
    if (!result || !address || !checked) return;
    const entry: Entry = { key: `${address.id}-${Date.now()}`, address, ...checked, result };
    const next = [...compare.filter((e) => e.address.id !== address.id), entry].slice(-MAX_COMPARE);
    setCompare(next);
    saveCompare(next);
  }

  function removeCompare(key: string) {
    const next = compare.filter((e) => e.key !== key);
    setCompare(next);
    saveCompare(next);
  }

  const bars = index && address && checked
    ? rentByPeriod(index.rows, address.location_class, address.east, checked.size, index.periods)
    : [];
  const tone = result ? verdictTone(result.verdict) : "neutral";
  const toneBox = { ok: "bg-ok-bg text-ok-body", warn: "bg-warn-bg text-warn", neutral: "bg-surface border border-line text-text-body" }[tone];
  const toneTitle = { ok: "text-ok-strong", warn: "text-warn", neutral: "text-text" }[tone];

  return (
    <div className="mx-auto flex max-w-page flex-col gap-10 px-[18px] py-8 md:px-8">
      <div className="grid items-start gap-6 lg:grid-cols-[400px_1fr]">
        {/* ── Form ── */}
        <form
          className="no-print flex flex-col gap-4 rounded-lg border border-line bg-surface p-5 sm:p-6"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          aria-label="Your flat"
        >
          {fromListing && (
            <p className="rounded-md bg-accent-tint px-3 py-2 text-[13.5px] leading-snug text-text-body" data-testid="prefill-note">
              Filled in from{" "}
              <Link href={`/listings/${fromListing.id}`} className="font-semibold text-accent underline underline-offset-2">
                {fromListing.title}
              </Link>
              . The address is the nearest real one to this sample listing. Change anything and check again; add the
              features from the checklist for a closer result.
            </p>
          )}
          <AddressSearch key={addressKey} value={address} onPick={setAddress} />
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1.5 text-[15px] font-semibold text-text">
              Size (m²)
              <input className={inputClass} inputMode="decimal" value={size} onChange={(e) => setSize(e.target.value)} placeholder="61" />
            </label>
            <label className="flex flex-col gap-1.5 text-[15px] font-semibold text-text">
              Built
              <select className={inputClass} value={age.id} onChange={(e) => setAgeId(e.target.value)}>
                {ages.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5 text-[15px] font-semibold text-text">
              Your cold rent (€)
              <input className={inputClass} inputMode="decimal" value={cold} onChange={(e) => setCold(e.target.value)} placeholder="860" />
              <span className="text-[12px] font-normal text-text-muted">Nettokalt: without heating and service charges</span>
            </label>
            <label className="flex flex-col gap-1.5 text-[15px] font-semibold text-text">
              <span>
                Energy value <span className="font-normal text-text-muted">(kWh/m²a)</span>
              </span>
              <input className={inputClass} inputMode="decimal" value={energy} onChange={(e) => setEnergy(e.target.value)} placeholder="optional" />
              <span className="text-[12px] font-normal text-text-muted">From the energy certificate</span>
            </label>
          </div>
          {energy.trim() && (
            <div className="flex flex-col gap-1 text-[14px] text-text-body">
              <label className="flex min-h-tap items-center gap-2">
                <input type="checkbox" className="h-4 w-4 accent-[var(--color-accent)]" checked={energyDemand} onChange={(e) => setEnergyDemand(e.target.checked)} />
                It&apos;s a demand value (Energiebedarf), not consumption
              </label>
              <label className="flex min-h-tap items-center gap-2">
                <input type="checkbox" className="h-4 w-4 accent-[var(--color-accent)]" checked={noHotWater} onChange={(e) => setNoHotWater(e.target.checked)} />
                The value doesn&apos;t include hot water
              </label>
            </div>
          )}
          {(age.id === "pre1918" || age.id === "1919-1949") && (
            <label className="flex min-h-tap items-center gap-2 text-[14px] text-text-body">
              <input type="checkbox" className="h-4 w-4 accent-[var(--color-accent)]" checked={noHeating} onChange={(e) => setNoHeating(e.target.checked)} />
              No central heating and/or no bathroom (−€0.33/m²)
            </label>
          )}

          <fieldset className="flex flex-col gap-2">
            <legend className="text-[15px] font-semibold text-text">
              Features that raise or lower the value{" "}
              <span className="font-normal text-text-muted">(Mietspiegel checklist)</span>
            </legend>
            <p className="text-[13px] text-text-muted">
              Tick what the landlord provides. In each group the side with more ticks wins; each group
              moves the rent 20% of the way to the top or bottom of the range. Optional: without ticks
              the estimate is the index mean.
            </p>
            {index &&
              Object.entries(index.groups).map(([g, label]) => {
                const items = index.checklist.filter((i) => i.group === Number(g) && !i.energy_kwh);
                const ticked = items.filter((i) => features.has(i.id)).length;
                return (
                  <details key={g} className="group rounded-md border border-line">
                    <summary className="flex min-h-tap cursor-pointer list-none items-center justify-between px-3.5 text-[14px] font-medium text-text">
                      {label}
                      <span className="text-[12.5px] font-normal text-text-muted">
                        {ticked ? `${ticked} ticked` : ""} <span aria-hidden="true">▾</span>
                      </span>
                    </summary>
                    <div className="flex flex-col gap-3 border-t border-line px-3.5 py-3">
                      {(["+", "-"] as const).map((sign) => (
                        <div key={sign}>
                          <p className="mb-1 text-[12px] font-semibold uppercase tracking-wide text-text-muted">
                            {sign === "+" ? "Raises the value" : "Lowers the value"}
                          </p>
                          <ul className="flex flex-col">
                            {items
                              .filter((i) => i.sign === sign)
                              .map((i) => {
                                const na =
                                  (period !== null && (i.not_applicable ?? []).includes(period)) ||
                                  (energy.trim() !== "" && index.insulation_items.includes(i.id));
                                return (
                                  <li key={i.id}>
                                    <label
                                      className={`flex min-h-tap items-start gap-2.5 py-1.5 text-[14px] leading-snug ${na ? "text-text-faint" : "text-text-body"}`}
                                      title={i.text_de}
                                    >
                                      <input
                                        type="checkbox"
                                        className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--color-accent)]"
                                        checked={features.has(i.id) && !na}
                                        disabled={na}
                                        onChange={() => toggle(i.id)}
                                      />
                                      <span>
                                        {i.label}
                                        {na && <span className="block text-[12px]">Doesn&apos;t count for this building age or with an energy value</span>}
                                      </span>
                                    </label>
                                  </li>
                                );
                              })}
                          </ul>
                        </div>
                      ))}
                    </div>
                  </details>
                );
              })}
          </fieldset>
          {error && (
            <p role="alert" className="rounded-md bg-warn-bg px-3 py-2 text-[14px] text-warn">
              {error}
            </p>
          )}
          {indexError && <p className="text-[14px] text-warn">{indexError}</p>}
          <Button type="submit" disabled={!index} className="w-full">
            Check this rent
          </Button>
        </form>

        {/* ── Result ── */}
        <div id="rent-result" className="flex min-w-0 scroll-mt-24 flex-col gap-4" aria-live="polite">
          {!result || !checked || !address ? (
            <div className="rounded-lg border border-dashed border-line-strong bg-surface p-6 text-[14px] text-text-body">
              <h2 className="text-[17px] font-semibold text-text">Your result appears here</h2>
              <ol className="mt-3 list-decimal space-y-1 pl-5">
                <li>Find the address: the location class comes from the official register.</li>
                <li>Add size, construction period and your cold rent.</li>
                <li>Optionally tick the flat&apos;s features to place it within the range.</li>
              </ol>
              <p className="mt-4 text-[13px] text-text-muted">
                Not legal advice. The Mietspiegel covers flats in buildings with three or more flats,
                ready for occupancy up to 2024.
              </p>
            </div>
          ) : (
            <>
              <p className="print-only text-sm">
                Rent check for {address.label} · {checked.size} m² · built {checked.ageLabel} · {euro(checked.cold)} cold
              </p>
              <section className={`rounded-lg p-5 sm:p-6 ${toneBox}`} data-testid="rent-verdict" data-verdict={result.verdict}>
                <p className="text-[13px] font-semibold opacity-90">Result</p>
                <h2 className={`mt-1 text-[26px] font-bold leading-tight tracking-tight ${toneTitle}`}>
                  {VERDICT_TITLE[result.verdict]}
                </h2>
                <p className="mt-2 text-[15px] leading-relaxed">{explainResult(result, checked.size)}</p>
              </section>
              {result.covered && (
                <>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <Tile label="Mietspiegel range" value={`${euro2(result.low!)}–${result.high!.toFixed(2)}`} sub={`per m², mean ${euro2(result.mean!)}`} />
                    <Tile
                      label="Rent-brake limit"
                      value={result.limit != null ? euro2(result.limit) : "none"}
                      sub={result.limit != null ? `per m², ${result.used_checklist ? "comparable rent" : "mean"} + 10%` : "new build: exempt"}
                    />
                    <Tile label="You pay" value={euro2(result.asked!)} sub={`per m², ${euro(checked.cold)} cold`} accent />
                  </div>
                  <section className="rounded-lg border border-line bg-surface p-5">
                    <h3 className="text-[17px] font-semibold text-text">Where your rent sits</h3>
                    <p className="text-[13px] text-text-muted">
                      Row {result.row!.row}: {address.location_class} location, {index!.periods[result.period!].label},{" "}
                      {result.row!.size_min}
                      {result.row!.size_max ? `–${result.row!.size_max}` : "+"} m²
                    </p>
                    <div className="mt-3">
                      <RentScale low={result.low!} mean={result.mean!} high={result.high!} limit={result.limit} asked={result.asked} />
                    </div>
                  </section>
                  <section className="rounded-lg border border-line bg-surface p-5">
                    <h3 className="text-[17px] font-semibold text-text">How rents compare in this area</h3>
                    <p className="mb-3 text-[13px] text-text-muted">
                      Mietspiegel mean by building age · {address.location_class} location, {checked.size} m²
                      {address.east ? " · former East" : " · former West"}
                    </p>
                    <RentByAgeChart bars={bars} selected={result.period} />
                  </section>
                </>
              )}
              <div className="no-print flex flex-wrap gap-2">
                <ButtonLink variant="dark" href={`/?q=${encodeURIComponent(`flat in ${address.district}`)}&fair=1`}>
                  See flats in {address.district} with fair rents
                </ButtonLink>
                <Button variant="outline" onClick={addToCompare} disabled={compare.length >= MAX_COMPARE && !compare.some((e) => e.address.id === address.id)}>
                  Add to comparison
                </Button>
                <Button variant="outline" onClick={() => window.print()}>
                  Print / PDF
                </Button>
              </div>
              <div className="flex flex-col gap-2 text-[13px] leading-relaxed text-text-muted">
                <p>
                  <strong className="text-text-body">The rent brake has exceptions:</strong> {index?.exemptions}
                </p>
                <p>
                  {index?.disclaimer} {index?.source}. {index?.checklist_note}
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Around this address ── */}
      {address && (
        <div className="no-print grid items-start gap-6 lg:grid-cols-[1fr_380px]">
          <section className="flex min-w-0 flex-col gap-4 rounded-lg border border-line bg-surface p-5 sm:p-6" aria-labelledby="around-heading">
            <div>
              <h2 id="around-heading" className="text-[22px] font-semibold tracking-tight text-text">
                Around this address
              </h2>
              <p className="text-[13px] text-text-muted">
                {[address.district, address.planning_area, address.street].filter(Boolean).join(" · ")}. Compared with Berlin&apos;s
                542 planning areas; differences are described, not judged.
              </p>
            </div>
            {profile ? <AroundGrid measures={profile.measures} /> : <div className="h-64 animate-pulse rounded-md bg-chip" />}
          </section>
          <div className="flex flex-col gap-4">
            <RightNowCard lat={address.lat} lng={address.lng} />
            <section className="rounded-lg border border-line bg-surface p-4">
              <h3 className="text-[15px] font-semibold text-text">On the map</h3>
              <p className="mb-2 text-[13px] text-text-muted">The address and the stops around it.</p>
              <StopsMap lat={address.lat} lng={address.lng} label={address.label} />
              <p className="mt-2 text-[12px] text-text-muted">
                Stops within 700 m with what stops there · dashed circle: 500 m · offline map © OpenStreetMap contributors
              </p>
            </section>
          </div>
        </div>
      )}

      {/* ── Compare addresses ── */}
      <section className="no-print flex flex-col gap-3" aria-labelledby="compare-heading" data-testid="rent-compare">
        <SectionHeading
          title={<span id="compare-heading">Compare addresses</span>}
          lede={`Check a rent, then "Add to comparison". Up to ${MAX_COMPARE} addresses side by side, kept in this browser tab only.`}
        />
        {compare.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-line bg-surface">
            <table className="w-full min-w-[640px] text-[14px]">
              <thead>
                <tr className="border-b border-line text-left text-[12px] uppercase tracking-wide text-text-muted">
                  <th className="px-4 py-2.5 font-semibold">Address</th>
                  <th className="px-4 py-2.5 font-semibold">Flat</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Index</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Limit</th>
                  <th className="px-4 py-2.5 text-right font-semibold">You pay</th>
                  <th className="px-4 py-2.5 font-semibold">Result</th>
                  <th className="px-4 py-2.5"><span className="sr-only">Remove</span></th>
                </tr>
              </thead>
              <tbody>
                {compare.map((e) => (
                  <tr key={e.key} className="border-b border-line last:border-0">
                    <td className="px-4 py-2.5">
                      <span className="text-text">{e.address.label}</span>
                      <span className="block text-[12.5px] text-text-muted">{e.address.district} · {e.address.location_class}</span>
                    </td>
                    <td className="px-4 py-2.5 text-text-body">{e.size} m² · {e.ageLabel}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{e.result.low != null ? `${euro2(e.result.low)}–${e.result.high!.toFixed(2)}` : "–"}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{e.result.limit != null ? euro2(e.result.limit) : "none"}</td>
                    <td className="px-4 py-2.5 text-right font-semibold tabular-nums">{e.result.asked != null ? euro2(e.result.asked) : "–"}</td>
                    <td className="px-4 py-2.5">{VERDICT_TITLE[e.result.verdict].replace(/^Your rent is /, "").replace(/^./, (c) => c.toUpperCase())}</td>
                    <td className="px-4 py-2.5 text-right">
                      <Button variant="ghost" onClick={() => removeCompare(e.key)} aria-label={`Remove ${e.address.label}`}>
                        Remove
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Tile({ label, value, sub, accent = false }: { label: string; value: string; sub: string; accent?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-lg border border-line bg-surface p-4">
      <span className="text-[13px] text-text-muted">{label}</span>
      <span className={`text-[22px] font-semibold tabular-nums ${accent ? "text-accent" : "text-text"}`}>{value}</span>
      <span className="text-[12.5px] text-text-muted">{sub}</span>
    </div>
  );
}
