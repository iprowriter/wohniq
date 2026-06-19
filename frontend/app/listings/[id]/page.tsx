"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { getListingDetail } from "@/lib/api";
import type { ListingDetailResponse } from "@/lib/types";
import { RiskBadge } from "@/components/RiskBadge";

const NeighborhoodMap = dynamic(
  () => import("@/components/NeighborhoodMap").then((m) => m.NeighborhoodMap),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse rounded-xl bg-gray-100" /> }
);

function euro(n: number) {
  return `€${n.toLocaleString("de-DE")}`;
}

function Skeleton() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <div className="animate-pulse space-y-4">
        <div className="h-56 rounded-xl bg-gray-100" />
        <div className="h-5 w-2/3 rounded bg-gray-100" />
        <div className="h-4 w-1/3 rounded bg-gray-100" />
        <div className="h-32 rounded-xl bg-gray-100" />
        <div className="h-24 rounded-xl bg-gray-100" />
      </div>
    </main>
  );
}

export default function ListingDetailPage() {
  const params = useParams();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const [data, setData] = useState<ListingDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  const photos = data?.listing.photos ?? [];

  const closeLightbox = useCallback(() => setLightboxIndex(null), []);

  const goPrev = useCallback(() =>
    setLightboxIndex((i) => (i !== null && i > 0 ? i - 1 : i)), []);

  const goNext = useCallback(() =>
    setLightboxIndex((i) => (i !== null && i < photos.length - 1 ? i + 1 : i)), [photos.length]);

  useEffect(() => {
    if (lightboxIndex === null) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") closeLightbox();
      if (e.key === "ArrowLeft") goPrev();
      if (e.key === "ArrowRight") goNext();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lightboxIndex, closeLightbox, goPrev, goNext]);

  useEffect(() => {
    if (!id) return;
    getListingDetail(id)
      .then(setData)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load listing")
      );
  }, [id]);

  if (error) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-10">
        <Link href="/" className="inline-flex items-center gap-1 text-sm text-gray-400 hover:text-gray-700">
          ← Back to search
        </Link>
        <p className="mt-6 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      </main>
    );
  }

  if (!data) return <Skeleton />;

  const { listing, risk, neighborhood } = data;
  const isHighRisk = risk?.band === "high";

  const detailRows: [string, string][] = [
    ["Size", `${listing.size_m2} m²`],
    ["Rooms", String(listing.rooms)],
    ...(listing.floor != null
      ? [["Floor", listing.total_floors ? `${listing.floor} of ${listing.total_floors}` : String(listing.floor)] as [string, string]]
      : []),
    ["Furnished", listing.furnished ? "Yes" : "No"],
    ["Anmeldung", listing.anmeldung_possible ? "Possible" : "Not possible"],
    ...(listing.available_from ? [["Available from", listing.available_from] as [string, string]] : []),
  ];

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <div className="mb-5">
        <Link href="/" className="inline-flex items-center gap-1 text-sm text-gray-400 hover:text-gray-700">
          ← Back to search
        </Link>
      </div>

      {/* Photo gallery */}
      {listing.photos.length > 0 && (
        <div className="mb-6 flex gap-2 overflow-x-auto pb-1">
          {listing.photos.map((p, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setLightboxIndex(i)}
              className={`group relative flex-shrink-0 overflow-hidden rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                i === 0 ? "h-56 w-80" : "h-56 w-48"
              }`}
              title="Click to enlarge"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={p.url}
                alt={p.room_type}
                className="h-full w-full object-cover transition-transform duration-200 group-hover:scale-105"
              />
              <div className="absolute inset-0 flex items-center justify-center bg-black/0 transition-colors duration-200 group-hover:bg-black/20">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-8 w-8 text-white opacity-0 drop-shadow transition-opacity duration-200 group-hover:opacity-100"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5v-4m0 4h-4m4 0l-5-5" />
                </svg>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Title + risk badge */}
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-medium leading-snug">{listing.title}</h1>
          <p className="mt-0.5 text-sm text-gray-500">{listing.address}</p>
          <p className="text-sm text-gray-400">
            {listing.kiez}
            {listing.district ? `, ${listing.district}` : ""}
          </p>
        </div>
        <RiskBadge risk={risk} />
      </div>

      {/* Price breakdown */}
      <div
        className={`mb-4 rounded-xl border bg-white p-4 ${
          isHighRisk ? "border-red-200" : "border-gray-200"
        }`}
      >
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Kaltmiete</span>
          <span>{euro(listing.kaltmiete_eur)}</span>
        </div>
        <div className="mt-1.5 flex justify-between text-sm">
          <span className="text-gray-500">Nebenkosten</span>
          <span>{euro(listing.nebenkosten_eur)}</span>
        </div>
        <div className="mt-2 flex justify-between border-t border-gray-100 pt-2 font-medium">
          <span>Warmmiete</span>
          <span>{euro(listing.warmmiete_eur)}</span>
        </div>
        {listing.deposit_eur != null && (
          <div className="mt-1.5 flex justify-between text-sm text-gray-500">
            <span>Kaution</span>
            <span>{euro(listing.deposit_eur)}</span>
          </div>
        )}
      </div>

      {/* Details grid */}
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {detailRows.map(([label, value]) => (
          <div key={label} className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2.5">
            <p className="text-xs text-gray-400">{label}</p>
            <p className="mt-0.5 text-sm font-medium">{value}</p>
          </div>
        ))}
      </div>

      {/* Description */}
      {listing.description && (
        <div className="mb-4 rounded-xl border border-gray-200 bg-white p-4">
          <h2 className="mb-1.5 text-sm font-medium text-gray-700">Description</h2>
          <p className="text-sm leading-relaxed text-gray-600">{listing.description}</p>
        </div>
      )}

      {/* Risk signals */}
      {risk && risk.band !== "low" && risk.signals.length > 0 && (
        <div
          className={`mb-4 rounded-xl border p-4 ${
            isHighRisk ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50"
          }`}
        >
          <h2
            className={`mb-2 text-sm font-medium ${
              isHighRisk ? "text-red-800" : "text-amber-800"
            }`}
          >
            Risk signals
          </h2>
          <ul className="space-y-2">
            {risk.signals.map((s) => (
              <li key={s.name}>
                <span
                  className={`text-sm font-medium ${
                    isHighRisk ? "text-red-700" : "text-amber-700"
                  }`}
                >
                  {s.name}
                </span>
                <span className="text-sm text-gray-600"> — {s.evidence}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Neighborhood */}
      {neighborhood && (
        <div className="mb-4">
          <h2 className="mb-2 text-sm font-medium text-gray-700">Neighborhood</h2>
          {neighborhood.summary && (
            <p className="mb-3 text-sm text-gray-600">{neighborhood.summary}</p>
          )}
          <div className="mb-3 flex flex-wrap gap-2">
            {Object.entries(neighborhood.counts)
              .filter(([, n]) => n > 0)
              .sort(([, a], [, b]) => b - a)
              .map(([cat, n]) => (
                <span
                  key={cat}
                  className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600"
                >
                  {cat} · {n}
                </span>
              ))}
          </div>
          <NeighborhoodMap lat={listing.lat} lng={listing.lng} pois={neighborhood.pois} />
        </div>
      )}

      {/* Lightbox */}
      {lightboxIndex !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          onClick={closeLightbox}
        >
          <div
            className="relative flex max-h-full max-w-5xl flex-col items-center"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close */}
            <button
              type="button"
              onClick={closeLightbox}
              className="absolute -top-10 right-0 text-white/70 hover:text-white"
              aria-label="Close"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            {/* Image */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={photos[lightboxIndex].url}
              alt={photos[lightboxIndex].room_type}
              className="max-h-[80vh] max-w-full rounded-xl object-contain"
            />

            {/* Room label + counter */}
            <p className="mt-2 text-sm text-white/70">
              {photos[lightboxIndex].room_type && (
                <span className="capitalize">{photos[lightboxIndex].room_type} · </span>
              )}
              {lightboxIndex + 1} / {photos.length}
            </p>

            {/* Prev / Next */}
            {lightboxIndex > 0 && (
              <button
                type="button"
                onClick={goPrev}
                className="absolute left-0 top-1/2 -translate-x-12 -translate-y-1/2 rounded-full bg-white/10 p-2 text-white hover:bg-white/25"
                aria-label="Previous image"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                </svg>
              </button>
            )}
            {lightboxIndex < photos.length - 1 && (
              <button
                type="button"
                onClick={goNext}
                className="absolute right-0 top-1/2 translate-x-12 -translate-y-1/2 rounded-full bg-white/10 p-2 text-white hover:bg-white/25"
                aria-label="Next image"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </button>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
