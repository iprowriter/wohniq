"use client";

import { useEffect, useRef, useState } from "react";
import { getRandomListings, search } from "@/lib/api";
import type { ListingOut, SearchResponse } from "@/lib/types";
import { CriteriaChips } from "@/components/CriteriaChips";
import { ResultCard } from "@/components/ResultCard";
import { FeaturedCard } from "@/components/FeaturedCard";

const EXAMPLE =
  "I work near Alexanderplatz, budget €1,500, quiet neighborhood, good transport, cafes nearby";

const CACHE_KEY = "wohniq_last_search";
const NAV_FLAG = "wohniq_navigating_to_listing";

function popCache(): { query: string; data: SearchResponse } | null {
  try {
    const navigated = sessionStorage.getItem(NAV_FLAG);
    sessionStorage.removeItem(NAV_FLAG);
    if (!navigated) return null;
    const raw = sessionStorage.getItem(CACHE_KEY);
    return raw ? (JSON.parse(raw) as { query: string; data: SearchResponse }) : null;
  } catch {
    return null;
  }
}

function saveCache(query: string, data: SearchResponse) {
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify({ query, data }));
  } catch {
    // storage full or unavailable — ignore
  }
}

function MarketingCard({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="flex gap-4 rounded-2xl border border-gray-200 bg-white p-6">
      <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
        {icon}
      </div>
      <div>
        <h3 className="mb-1 font-semibold text-gray-900">{title}</h3>
        <p className="text-sm leading-relaxed text-gray-500">{body}</p>
      </div>
    </div>
  );
}

export default function Home() {
  const [query, setQuery] = useState("");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [featured, setFeatured] = useState<ListingOut[]>([]);
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const cached = popCache();
    if (cached) {
      setQuery(cached.query);
      setData(cached.data);
    }
    getRandomListings(6)
      .then(setFeatured)
      .catch(() => {/* silently ignore — featured listings are best-effort */});
  }, []);

  async function runSearch(q: string) {
    const trimmed = q.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      const result = await search(trimmed);
      setData(result);
      saveCache(trimmed, result);
      setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* ── Hero ── */}
      <section className="bg-gray-950 px-4 py-20 text-white">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="mb-3 text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
            Find your Berlin flat,{" "}
            <span className="text-indigo-400">smarter.</span>
          </h1>
          <p className="mb-8 text-base text-gray-400 sm:text-lg">
            Describe what you need in plain language — we rank, explain, and
            flag every listing.
          </p>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              void runSearch(query);
            }}
            className="flex gap-2"
          >
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. quiet 2-room near Mitte, budget €1,400, good cafes"
              className="flex-1 rounded-full border border-gray-700 bg-gray-800 px-5 py-3 text-sm text-white placeholder-gray-500 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            />
            <button
              type="submit"
              disabled={loading}
              className="rounded-full bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {loading ? "Searching…" : "Search"}
            </button>
          </form>

          <button
            type="button"
            onClick={() => {
              setQuery(EXAMPLE);
              void runSearch(EXAMPLE);
            }}
            className="mt-3 text-xs text-gray-500 hover:text-gray-300"
          >
            Try an example →
          </button>
        </div>
      </section>

      {/* ── Main content ── */}
      <div className="mx-auto max-w-6xl px-4">

        {/* Error */}
        {error && (
          <p className="mt-8 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
        )}

        {/* ── Search results ── */}
        {data ? (
          <section ref={resultsRef} className="py-10">
            <div className="mb-4">
              <CriteriaChips criteria={data.criteria} />
            </div>
            <div className="mb-4 flex items-center justify-between">
              <p className="text-sm text-gray-500">
                {data.results.length} result{data.results.length === 1 ? "" : "s"} · ranked by fit
              </p>
              <button
                type="button"
                onClick={() => { setData(null); setQuery(""); }}
                className="text-xs text-gray-400 hover:text-gray-700"
              >
                ✕ Clear search
              </button>
            </div>
            <div className="space-y-4">
              {data.results.map((item) => (
                <ResultCard key={item.listing.id} item={item} />
              ))}
            </div>
          </section>
        ) : (
          <>
            {/* ── Marketing cards ── */}
            <section id="how-it-works" className="grid gap-4 py-10 sm:grid-cols-2">
              <MarketingCard
                icon={
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 16v-4M12 8h.01" />
                  </svg>
                }
                title="AI-Powered Matching"
                body="Describe what matters to you — commute, budget, quiet street, local cafes. We parse your criteria and rank every listing by real fit, not just keywords."
              />
              <MarketingCard
                icon={
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                }
                title="Built-in Scam Protection"
                body="Every listing is risk-scored before it reaches you. Suspicious pricing, ghost addresses, and pressure tactics are automatically detected and flagged."
              />
            </section>

            {/* ── Featured listings ── */}
            <section className="pb-12">
              <div className="mb-5 flex items-center justify-between">
                <h2 className="text-lg font-semibold">Explore Berlin</h2>
                <button
                  type="button"
                  onClick={() => getRandomListings(6).then(setFeatured).catch(() => {})}
                  className="text-xs text-gray-400 hover:text-gray-700"
                >
                  Refresh ↻
                </button>
              </div>

              {featured.length === 0 ? (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="h-64 animate-pulse rounded-2xl bg-gray-100" />
                  ))}
                </div>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {featured.map((listing) => (
                    <FeaturedCard key={listing.id} listing={listing} />
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </>
  );
}
