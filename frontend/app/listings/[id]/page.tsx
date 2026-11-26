"use client";

/**
 * The listing page ("dossier", Berlin Ink T9.5): photos, the three verdicts (fit, rent
 * check, scam risk), price, the rent check with its scale, Right now, commute with the stops
 * map, Around this flat, why the risk is low (or what to ask), and the description. On phones:
 * compact verdict tiles, six measures first, and a bar with the rent and Request viewing.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getListingAround, getListingDetail } from "@/lib/api";
import type { ListingDetailResponse, PlaceProfile, SimilarItem } from "@/lib/types";
import { euro, euro2, rooms } from "@/lib/format";
import { backLabel, fitLabel, readLastSearch, type LastSearch } from "@/lib/listing/lastSearch";
import { riskChecks } from "@/lib/listing/riskChecks";
import { useSaved } from "@/lib/useSaved";
import { Button, buttonClass, VerdictCard } from "@/components/ui/primitives";
import { RentScale } from "@/components/ui/RentScale";
import { AroundGrid } from "@/components/place/AroundGrid";
import { RightNowCard } from "@/components/place/RightNowCard";
import { PhotoGallery } from "@/components/listing/PhotoGallery";
import { ViewingDialog } from "@/components/listing/ViewingDialog";
import { CommuteCard } from "@/components/listing/CommuteCard";
import { SimilarFlats } from "@/components/listing/SimilarFlats";
import { CompareWith } from "@/components/listing/CompareWith";

const RISK_WORD = { low: "Low", caution: "Worth asking", high: "High" } as const;

function factsLine(l: ListingDetailResponse["listing"]): string {
  const parts = [rooms(l.rooms), `${l.size_m2} m²`];
  if (l.floor != null) {
    const floor = l.floor === 0 ? "ground floor" : `${l.floor}${["th", "st", "nd", "rd"][l.floor] ?? "th"} floor`;
    parts.push(l.total_floors ? `${floor} of ${l.total_floors}` : floor);
  }
  if (l.year_built) parts.push(`built ${l.year_built}`);
  if (l.available_from) {
    parts.push(`available ${new Date(l.available_from).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`);
  }
  if (l.furnished) parts.push("furnished");
  parts.push(l.anmeldung_possible ? "Anmeldung possible" : "no Anmeldung");
  return parts.join(" · ");
}

export default function ListingPage() {
  const params = useParams();
  const id = Array.isArray(params.id) ? params.id[0] : (params.id as string);
  const [data, setData] = useState<ListingDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [around, setAround] = useState<PlaceProfile | null>(null);
  const [last, setLast] = useState<LastSearch | null>(null);
  const [viewing, setViewing] = useState(false);
  const [allMeasures, setAllMeasures] = useState(false);
  const [shared, setShared] = useState(false);
  const [similar, setSimilar] = useState<SimilarItem[]>([]);
  const [comparing, setComparing] = useState(false);
  const saved = useSaved();

  useEffect(() => {
    if (!id) return;
    setLast(readLastSearch());
    getListingDetail(id).then(setData).catch((e) => setError(e instanceof Error ? e.message : "Couldn't load this listing"));
    getListingAround(id).then(setAround).catch(() => {});
  }, [id]);

  async function share() {
    const url = window.location.href;
    try {
      if (navigator.share) await navigator.share({ title: data?.listing.title, url });
      else {
        await navigator.clipboard.writeText(url);
        setShared(true);
        setTimeout(() => setShared(false), 2500);
      }
    } catch {
      /* cancelled */
    }
  }

  const backHref = last?.url ?? "/";

  if (error) {
    return (
      <div className="mx-auto max-w-page px-[18px] py-10 md:px-8">
        <Link href="/" className="text-[15px] text-accent underline">← Back to search</Link>
        <p role="alert" className="mt-6 rounded-md bg-warn-bg px-4 py-3 text-[15px] text-warn">{error}</p>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="mx-auto max-w-page px-[18px] py-8 md:px-8" aria-busy="true">
        <div className="h-[300px] animate-pulse rounded-xl bg-chip md:h-[440px]" />
        <div className="mt-6 h-10 w-2/3 animate-pulse rounded bg-chip" />
      </div>
    );
  }

  const { listing, risk, rent, location } = data;
  const fit = last?.fit[listing.id];
  const checks = riskChecks(risk, rent, listing.anmeldung_possible);
  const coldPerM2 = listing.kaltmiete_eur / listing.size_m2;
  const mapLat = location?.lat ?? listing.lat;
  const mapLng = location?.lng ?? listing.lng;
  const rentTone = rent?.verdict === "within_limit" ? "ok" : rent?.verdict === "above_limit" || rent?.verdict === "below_index" ? "warn" : "neutral";
  const rentDetail =
    rent?.asked != null
      ? `${euro2(rent.asked)}/m² cold${rent.limit != null ? ` · limit ${euro2(rent.limit)}` : ""}`
      : undefined;
  const riskDetail = risk
    ? risk.band === "low"
      ? risk.signals.length ? `${risk.signals.length} minor signal${risk.signals.length > 1 ? "s" : ""}` : "No warning signs found"
      : `${risk.signals.length} signal${risk.signals.length === 1 ? "" : "s"}: see what to ask`
    : undefined;
  const isSaved = saved.has(listing.id);

  return (
    <div className="pb-24 md:pb-0">
      {/* Top bar */}
      <div className="no-print hidden border-b border-line bg-surface md:block">
        <div className="mx-auto flex max-w-page items-center justify-between gap-3 px-8 py-2">
          <Link href={backHref} className="inline-flex min-h-tap items-center gap-1.5 text-[14px] text-text-body hover:text-text" data-testid="back-link">
            <span aria-hidden="true">‹</span> {backLabel(last)}
          </Link>
          <div className="flex gap-2">
            <Button variant="outline" onClick={share}>{shared ? "Link copied" : "Share"}</Button>
            <Button variant="outline" onClick={() => window.print()}>Print / PDF</Button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-page px-[18px] md:px-8 md:pt-6">
        <PhotoGallery photos={listing.photos} title={listing.title} backHref={backHref} onShare={share} />

        <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
          {/* ── Main column ── */}
          <div className="flex min-w-0 flex-col gap-6">
            <div>
              <p className="text-[14px] text-text-muted" data-testid="listing-location">
                {[location?.district ?? listing.district, location?.planning_area, location?.street].filter(Boolean).join(" · ") || listing.kiez}
              </p>
              <h1 className="mt-1 text-[26px] font-bold leading-tight tracking-[-0.03em] text-text md:text-[38px]">{listing.title}</h1>
              <p className="mt-2 text-[15px] text-text-body md:text-[16px]">{factsLine(listing)}</p>
            </div>

            {/* Three verdicts */}
            <div className="grid grid-cols-3 gap-2 sm:gap-3" data-testid="verdicts">
              <VerdictCard
                tone="ink"
                label="Fit for your search"
                value={fit ? Math.round(fit.score * 100) : "–"}
                detail={
                  fit ? (
                    <span className="hidden sm:inline">{fitLabel(fit.score)}</span>
                  ) : (
                    <Link href="/" className="underline underline-offset-2">Search to see the fit</Link>
                  )
                }
              />
              <VerdictCard
                tone={rentTone}
                label="Rent check"
                value={<span className="text-[17px] sm:text-[22px]">{rent ? <><span className="sm:hidden">{rent.verdict === "within_limit" ? "Fair" : rent.verdict === "above_limit" ? "Above limit" : rent.verdict === "below_index" ? "Below index" : "No limit"}</span><span className="hidden sm:inline">{rent.verdict_text}</span></> : "–"}</span>}
                detail={rentDetail && <span className="hidden sm:inline">{rentDetail}</span>}
              />
              <VerdictCard
                label="Scam risk"
                value={<span className="text-[17px] sm:text-[22px]">{risk ? <>{RISK_WORD[risk.band]}<span className="hidden sm:inline"> · {risk.score}/100</span></> : "–"}</span>}
                detail={riskDetail && <span className="hidden sm:inline">{riskDetail}</span>}
              />
            </div>

            {/* Rent check */}
            {rent && (
              <section className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-5 sm:p-6" aria-labelledby="rent-heading" data-testid="rent-panel">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h2 id="rent-heading" className="text-[20px] font-semibold text-text">Rent check</h2>
                  <Link href="/rent-check" className="text-[14px] text-accent underline underline-offset-2">Open the full rent check</Link>
                </div>
                <p className="text-[15px] leading-relaxed text-text-body">{rent.explanation}</p>
                {rent.covered && rent.low != null && rent.mean != null && rent.high != null && (
                  <RentScale low={rent.low} mean={rent.mean} high={rent.high} limit={rent.limit} asked={rent.asked} />
                )}
                <p className="text-[13px] text-text-muted">
                  The flat&apos;s features aren&apos;t known, so the estimate is the index mean. The full rent check places a flat within the range with the Mietspiegel checklist.
                </p>
                <p className="text-[13px] leading-relaxed text-text-muted">
                  Estimate from the official rent index, not legal advice. For a binding check, contact a tenants&apos; association or the Mietpreisprüfstelle. New buildings first let after 1 October 2014 aren&apos;t covered by the rent brake. Nor is the first letting after a comprehensive modernisation. A landlord may keep a previous tenant&apos;s rent if it was already higher. Modernisation in the last three years can justify a surcharge.
                </p>
                {location && (
                  <p className="text-[12px] text-text-muted">
                    Location class of the nearest registered address, {location.street} (Wohnlagenverzeichnis 2026). The house number isn&apos;t shown: the listing is synthetic.
                  </p>
                )}
              </section>
            )}

            {/* Right now: on phones it comes right after the rent check */}
            <div className="lg:hidden">
              <RightNowCard lat={mapLat} lng={mapLng} />
            </div>

            {/* Around this flat */}
            <section className="flex flex-col gap-4 rounded-lg border border-line bg-surface p-5 sm:p-6" aria-labelledby="around-heading">
              <div>
                <h2 id="around-heading" className="text-[20px] font-semibold text-text">Around this flat</h2>
                <p className="text-[13px] text-text-muted">
                  {[around?.district, around?.planning_area, around?.district_region].filter(Boolean).join(" · ")}
                  {around ? ". " : ""}Compared with Berlin&apos;s 542 planning areas; differences are described, not judged.
                </p>
              </div>
              {around ? (
                <>
                  <div className="hidden sm:block">
                    <AroundGrid measures={around.measures} />
                  </div>
                  <div className="sm:hidden">
                    <AroundGrid measures={around.measures} limit={allMeasures ? undefined : 6} />
                    {!allMeasures && around.measures.length > 6 && (
                      <Button variant="outline" className="mt-3 w-full" onClick={() => setAllMeasures(true)}>
                        All {around.measures.length} measures
                      </Button>
                    )}
                  </div>
                </>
              ) : (
                <div className="h-64 animate-pulse rounded-md bg-chip" />
              )}
            </section>

            {/* Risk */}
            <section className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-5 sm:p-6" aria-labelledby="risk-heading" data-testid="risk-panel">
              <h2 id="risk-heading" className="text-[20px] font-semibold text-text">{checks.title}</h2>
              {checks.flagged.length > 0 && (
                <ul className="flex flex-col gap-2">
                  {checks.flagged.map((f) => (
                    <li key={f} className="flex gap-2.5 rounded-md bg-warn-bg px-3 py-2 text-[15px] leading-snug text-warn">
                      <span aria-hidden="true" className="font-bold">!</span>
                      {f}
                    </li>
                  ))}
                </ul>
              )}
              <ul className="flex flex-col gap-2">
                {checks.passed.map((p) => (
                  <li key={p} className="flex gap-2.5 text-[15px] leading-snug text-text-body">
                    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-ok-text)" strokeWidth="2.4" className="mt-0.5 shrink-0">
                      <path d="M5 12.5l4.5 4.5L19 7.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    {p}
                  </li>
                ))}
              </ul>
              <p className="text-[13px] text-text-muted">{checks.checked}</p>
            </section>

            <section className="rounded-lg border border-line bg-surface p-5 sm:p-6" aria-labelledby="about-heading">
              <h2 id="about-heading" className="text-[20px] font-semibold text-text">About this flat</h2>
              <p className="mt-2 text-[15px] leading-relaxed text-text-body">{listing.description}</p>
              <p className="mt-3 text-[13px] text-text-muted">Sample listing: synthetic, generated for this demo.</p>
            </section>
          </div>

          {/* ── Side column ── */}
          <aside className="flex flex-col gap-6 lg:sticky lg:top-24">
            <section className="hidden flex-col gap-4 rounded-lg border border-line bg-surface p-5 md:flex" aria-label="Price" data-testid="price-card">
              <p>
                <span className="text-[34px] font-bold tabular-nums text-text">{euro(listing.warmmiete_eur)}</span>{" "}
                <span className="text-[14px] text-text-muted">warm / month</span>
              </p>
              <dl className="grid grid-cols-[1fr_auto] gap-y-1.5 text-[14px]">
                <dt className="text-text-muted">Cold rent</dt><dd className="text-right tabular-nums text-text">{euro(listing.kaltmiete_eur)}</dd>
                <dt className="text-text-muted">Service charges</dt><dd className="text-right tabular-nums text-text">{euro(listing.nebenkosten_eur)}</dd>
                {listing.deposit_eur != null && (<><dt className="text-text-muted">Deposit</dt><dd className="text-right tabular-nums text-text">{euro(listing.deposit_eur)}</dd></>)}
                <dt className="text-text-muted">Per m² cold</dt><dd className="text-right tabular-nums text-text">{euro2(coldPerM2)}</dd>
              </dl>
              <Button onClick={() => setViewing(true)}>Request a viewing</Button>
              <div className="grid grid-cols-2 gap-2">
                <Button variant="outline" aria-pressed={isSaved} onClick={() => saved.toggle(listing.id)}>{isSaved ? "Saved" : "Save"}</Button>
                <Button variant="outline" onClick={() => setComparing(true)} data-testid="compare-with">Compare</Button>
              </div>
              <Link href="/rent-check" className={buttonClass("ghost")}>Check this rent</Link>
            </section>
            <div className="hidden lg:block">
              <RightNowCard lat={mapLat} lng={mapLng} />
            </div>
            <CommuteCard listingId={listing.id} lat={mapLat} lng={mapLng} />
          </aside>
        </div>
        <div className="mt-10 flex flex-col gap-3">
          <Button variant="outline" className="self-start md:hidden" onClick={() => setComparing(true)}>
            Compare with another flat
          </Button>
          <SimilarFlats listingId={listing.id} onLoaded={(d) => setSimilar(d.items)} />
        </div>
      </div>

      {/* Phone bar */}
      <div className="no-print fixed inset-x-0 bottom-0 z-[1050] flex items-center justify-between gap-3 border-t border-line bg-surface px-[18px] py-3 md:hidden" data-testid="phone-bar">
        <p>
          <span className="block text-[20px] font-bold tabular-nums text-text">{euro(listing.warmmiete_eur)}</span>
          <span className="text-[12.5px] text-text-muted">warm / month</span>
        </p>
        <div className="flex gap-2">
          <Button variant="outline" aria-pressed={isSaved} onClick={() => saved.toggle(listing.id)} aria-label={isSaved ? "Saved" : "Save"}>
            {isSaved ? "Saved" : "Save"}
          </Button>
          <Button onClick={() => setViewing(true)}>Request viewing</Button>
        </div>
      </div>

      {viewing && <ViewingDialog onClose={() => setViewing(false)} />}
      {comparing && <CompareWith listingId={listing.id} similar={similar} onClose={() => setComparing(false)} />}
    </div>
  );
}
