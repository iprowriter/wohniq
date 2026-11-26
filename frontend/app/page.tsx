"use client";

/**
 * Home (Berlin Ink, T9.4): hero search, "Every listing, checked", three entry cards, Explore
 * Berlin + the big map (kept, owner's decision), How WohnIQ works. With ?q= the same page shows
 * the results: what we understood, sort / only fair rents / share, result cards and a sticky
 * map with layers. Searches live in the URL, so they can be shared and reloaded.
 */

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { getMapListings, getRandomListings, search } from "@/lib/api";
import type { ListingOut, SearchResponse } from "@/lib/types";
import type { Bounds, MapListing } from "@/lib/map/listingsMap";
import {
  EXPLORE_COUNT,
  exploreSubtitle,
  listingsForView,
  mapToCardsNote,
  pickExploreCards,
  type ExploreCard,
  type ExploreStatus,
} from "@/lib/map/exploreCards";
import {
  readParams,
  resultsHeading,
  SORT_LABELS,
  toQuery,
  visibleResults,
  type SearchParams,
  type SortKey,
} from "@/lib/results";
import { isFairRent } from "@/lib/listing/chips";
import { useSaved } from "@/lib/useSaved";
import { useCompare } from "@/lib/compare/useCompare";
import { useSavedSearches } from "@/lib/useSavedSearches";
import { addSearch, findSearch, readSearches, recordRun, removeSearch, writeSearches, searchHref } from "@/lib/savedSearches";
import { saveLastSearch } from "@/lib/listing/lastSearch";
import { CriteriaChips } from "@/components/CriteriaChips";
import { SearchNotices } from "@/components/SearchNotices";
import { ResultCard } from "@/components/ResultCard";
import { FeaturedCard, type CardListing } from "@/components/FeaturedCard";
import { ListingsMapSection } from "@/components/map/ListingsMapSection";
import { SearchForm } from "@/components/home/SearchForm";
import { CheckedCard, EntryCards, HowItWorks } from "@/components/home/HomeSections";
import { ResultsMap } from "@/components/results/ResultsMap";
import { Button } from "@/components/ui/primitives";

const EXAMPLES = [
  "Quiet 2 rooms in Mitte near a park",
  "Family flat, good schools, under €1,800",
  "Furnished, 20 min to TU Berlin",
];
const CACHE_PREFIX = "wohniq_search:";
const EXPLORE_POOL = 12;
const RESULTS_LIMIT = 20;

function cacheGet(key: string): SearchResponse | null {
  try {
    const raw = sessionStorage.getItem(CACHE_PREFIX + key);
    return raw ? (JSON.parse(raw) as SearchResponse) : null;
  } catch {
    return null;
  }
}

function cacheSet(key: string, data: SearchResponse) {
  try {
    sessionStorage.setItem(CACHE_PREFIX + key, JSON.stringify(data));
  } catch {
    /* storage full or unavailable */
  }
}

/** "Your saved searches" under the home search box: one click runs a search again. */
function SavedSearchRow() {
  const { searches } = useSavedSearches();
  if (!searches.length) return null;
  return (
    <nav aria-label="Your saved searches" className="mt-5 flex flex-wrap items-center gap-2" data-testid="saved-searches-row">
      <span className="text-[14px] font-semibold text-white">Your saved searches:</span>
      {searches.slice(0, 4).map((s) => (
        <Link
          key={s.id}
          href={searchHref(s)}
          className="inline-flex min-h-[36px] max-w-[260px] items-center truncate rounded-full bg-white/10 px-3 text-[14px] text-white hover:bg-white/20"
        >
          <span className="truncate">{s.name}</span>
        </Link>
      ))}
      <Link href="/saved?tab=searches" className="inline-flex min-h-[36px] items-center px-1 text-[14px] text-accent-on-ink underline underline-offset-2">
        Manage
      </Link>
    </nav>
  );
}

export default function Home() {
  return (
    <Suspense fallback={<div className="min-h-[60vh] bg-ink" />}>
      <HomeInner />
    </Suspense>
  );
}

function HomeInner() {
  const router = useRouter();
  const urlParams = useSearchParams();
  const params = useMemo(() => readParams(new URLSearchParams(urlParams.toString())), [urlParams]);

  const [mapListings, setMapListings] = useState<MapListing[] | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);

  useEffect(() => {
    getMapListings()
      .then(setMapListings)
      .catch((e) => setMapError(e instanceof Error ? e.message : "Failed to load the map"));
  }, []);

  function go(next: SearchParams | null, replace = false) {
    const url = next ? `/${toQuery(next)}` : "/";
    if (replace) router.replace(url, { scroll: false });
    else router.push(url, { scroll: false });
  }

  return params ? (
    <Results params={params} go={go} mapListings={mapListings} />
  ) : (
    <HomeView go={go} mapListings={mapListings} mapError={mapError} />
  );
}

// ── Home ────────────────────────────────────────────────────────────────────────────────

function HomeView({
  go,
  mapListings,
  mapError,
}: {
  go: (p: SearchParams) => void;
  mapListings: MapListing[] | null;
  mapError: string | null;
}) {
  const [pool, setPool] = useState<CardListing[]>([]);
  const [cards, setCards] = useState<ExploreCard<CardListing>[]>([]);
  const [exploreStatus, setExploreStatus] = useState<ExploreStatus>({ kind: "random" });
  const lastView = useRef<{ bounds: Bounds; zoom: number } | null>(null);
  const exploreRef = useRef<HTMLElement>(null);
  const latest = useRef({ pool, cards, mapListings });
  latest.current = { pool, cards, mapListings };

  useEffect(loadRandomCards, []);
  const run = (q: string) => go({ q, fair: false, sort: "fit" });

  /** Fresh random pool; shows its first cards, or re-picks for the current map area. */
  function loadRandomCards() {
    getRandomListings(EXPLORE_POOL)
      .then((fresh) => {
        setPool(fresh);
        if (lastView.current && latest.current.mapListings) {
          syncCardsToMap(lastView.current.bounds, lastView.current.zoom, fresh, []);
        } else {
          setCards(fresh.slice(0, EXPLORE_COUNT).map((listing) => ({ listing, tag: null })));
          setExploreStatus({ kind: "random" });
        }
      })
      .catch(() => {});
  }

  function syncCardsToMap(
    bounds: Bounds,
    zoom: number,
    fillers: CardListing[] = latest.current.pool,
    previous: ExploreCard<CardListing>[] = latest.current.cards,
  ) {
    const all = latest.current.mapListings;
    if (!all) return;
    lastView.current = { bounds, zoom };
    const { cards: next, status } = pickExploreCards<CardListing>({
      inView: listingsForView(all, bounds, zoom),
      pool: fillers,
      all,
      previous,
    });
    setCards(next);
    setExploreStatus(status);
  }

  // "Every listing, checked": a real listing with a fair rent, low risk, near the U/S-Bahn.
  const risk = useMemo(() => new Map(mapListings?.map((m) => [m.id, m.risk_band]) ?? []), [mapListings]);
  const showcase = useMemo(() => {
    const full = pool as ListingOut[];
    const good = full.filter(
      (l) =>
        isFairRent(l.rent) &&
        risk.get(l.id) === "low" &&
        (l.location?.rail_modes ?? []).some((m) => m === "ubahn" || m === "sbahn") &&
        (l.location?.rail_walk_minutes ?? 99) <= 8,
    );
    return good[0] ?? full.find((l) => isFairRent(l.rent)) ?? full[0] ?? null;
  }, [pool, risk]);

  const shownInView = cards.filter((c) => c.tag === "in-view").length;

  return (
    <>
      <section className="bg-ink text-text-on-ink">
        <div className="mx-auto grid max-w-page items-center gap-12 px-[18px] pb-20 pt-14 md:px-8 lg:grid-cols-[minmax(0,1fr)_400px] lg:pt-[72px]">
          <div className="min-w-0">
            <p className="text-[14px] font-semibold uppercase tracking-[0.08em] text-accent-on-ink">
              Berlin flat search you can trust
            </p>
            <h1 className="mt-3.5 text-[40px] font-bold leading-[1.03] tracking-[-0.04em] text-white sm:text-[56px] xl:text-[64px]">
              Find your Berlin flat. Know it&apos;s fair before you call.
            </h1>
            <p className="mt-5 max-w-[600px] text-[17px] leading-relaxed text-text-on-ink-muted sm:text-[19px]">
              Say what you need in plain words. WohnIQ ranks the flats, checks each rent against the
              official Mietspiegel and flags likely scams, and tells you why.
            </p>
            <div className="mt-9">
              <SearchForm onSearch={run} />
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="text-[14px] text-text-on-ink-muted">Try:</span>
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => run(ex)}
                  className="min-h-[36px] rounded-full border border-white/20 px-3 text-[14px] text-text-on-ink-soft hover:border-white/40 hover:text-white"
                >
                  {ex}
                </button>
              ))}
            </div>
            <SavedSearchRow />
          </div>
          <CheckedCard listing={showcase} lowRisk={!!showcase && risk.get(showcase.id) === "low"} />
        </div>
      </section>

      <div className="mx-auto flex max-w-page flex-col gap-14 px-[18px] py-14 md:px-8">
        <EntryCards />

        <div>
          <section ref={exploreRef} className="scroll-mt-20 pb-8" data-testid="explore" aria-labelledby="explore-heading">
            <div className="mb-5 flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <h2 id="explore-heading" className="text-[26px] font-bold tracking-tight text-text">
                  Explore Berlin
                </h2>
                <p
                  className="mt-1 line-clamp-2 h-10 text-[15px] text-text-muted sm:line-clamp-1 sm:h-6"
                  aria-live="polite"
                  data-testid="explore-subtitle"
                >
                  {exploreSubtitle(exploreStatus, shownInView)}
                </p>
              </div>
              <Button variant="outline" onClick={loadRandomCards}>
                Show others
              </Button>
            </div>
            {cards.length === 0 ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {Array.from({ length: EXPLORE_COUNT }).map((_, i) => (
                  <div key={i} className="h-72 animate-pulse rounded-lg bg-chip" />
                ))}
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {cards.map((c) => (
                  <FeaturedCard key={c.listing.id} listing={c.listing} tag={c.tag} />
                ))}
              </div>
            )}
          </section>

          <ListingsMapSection
            listings={mapListings}
            error={mapError}
            onUserViewChange={(bounds, zoom) => syncCardsToMap(bounds, zoom)}
            cardsNote={mapToCardsNote(exploreStatus, shownInView)}
            onCardsNoteClick={() => exploreRef.current?.scrollIntoView({ behavior: "smooth" })}
          />
        </div>

        <HowItWorks />
      </div>
    </>
  );
}

// ── Results ─────────────────────────────────────────────────────────────────────────────

function Results({
  params,
  go,
  mapListings,
}: {
  params: SearchParams;
  go: (p: SearchParams | null, replace?: boolean) => void;
  mapListings: MapListing[] | null;
}) {
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const compare = useCompare(); // shared list (T9.7): bar + /compare page
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const saved = useSaved();
  const savedSearches = useSavedSearches();
  const thisSaved = findSearch(savedSearches.searches, params);
  const [news, setNews] = useState<{ key: string; ids: string[]; since: string } | null>(null);
  // After a search, scroll so "We understood:" sits just under the sticky header and the
  // results follow below it (the chips are never hidden behind the header).
  const chipsRef = useRef<HTMLDivElement>(null);
  const cacheKey = `${params.q}|${params.budget ?? ""}`;

  useEffect(() => {
    let cancelled = false;
    const cached = cacheGet(cacheKey);
    if (cached) {
      setData(cached);
      return;
    }
    setLoading(true);
    setError(null);
    search(params.q, RESULTS_LIMIT, params.budget)
      .then((res) => {
        if (cancelled) return;
        setData(res);
        cacheSet(cacheKey, res);
        setTimeout(() => chipsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
      })
      .catch((e) => !cancelled && (setError(e instanceof Error ? e.message : "Something went wrong"), setData(null)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [cacheKey, params.q, params.budget]);

  const areas = data?.criteria.areas ?? [];
  const results = data?.results ?? [];
  const shown = visibleResults(results, params.fair, params.sort);
  const fairCount = results.filter((r) => isFairRent(r.listing.rent)).length;

  // Remember this view for the listing pages opened from it (fit score, "Back to …").
  useEffect(() => {
    if (!data) return;
    saveLastSearch({
      url: `${window.location.pathname}${window.location.search}`,
      heading: resultsHeading(shown.length, areas),
      count: shown.length,
      areas,
      fit: Object.fromEntries(results.map((r) => [r.listing.id, { score: r.score, summary: r.explanation.summary }])),
      items: shown.slice(0, 20).map((r) => ({ id: r.listing.id, title: r.listing.title, warm: r.listing.warmmiete_eur, kiez: r.listing.kiez })),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, params.fair, params.sort]);

  // A saved search ran again: mark what's new since the previous run, then remember this run.
  useEffect(() => {
    if (!data) return;
    const list = readSearches();
    const hit = findSearch(list, params);
    if (!hit) return;
    const ids = (data.results ?? []).map((r) => r.listing.id);
    const run = recordRun(list, hit.id, ids);
    if (!run) return;
    setNews({ key: cacheKey, ids: run.newIds, since: run.previousRunAt });
    writeSearches(run.searches);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);
  const newIds = news?.key === cacheKey ? news.ids : [];

  function toggleSaveSearch() {
    const ids = results.map((r) => r.listing.id);
    savedSearches.update((list) => (thisSaved ? removeSearch(list, thisSaved.id) : addSearch(list, params, ids)));
    if (thisSaved) setNews(null);
  }


  async function share() {
    const url = window.location.href;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      window.prompt("Copy this link", url);
    }
  }

  return (
    <>
      <section className="bg-ink text-text-on-ink">
        <div className="mx-auto max-w-page px-[18px] pb-12 pt-12 md:px-8">
          <p className="text-[14px] font-semibold uppercase tracking-[0.08em] text-accent-on-ink">
            Berlin flat search you can trust
          </p>
          <h1 className="mt-3 max-w-4xl text-[34px] font-bold leading-[1.05] tracking-[-0.035em] text-white sm:text-[48px]">
            Describe the flat you want. We check the rent, the area and the risk.
          </h1>
          <p className="mt-4 max-w-[640px] text-[17px] leading-relaxed text-text-on-ink-muted">
            Every result is ranked by fit, measured against Berlin&apos;s official rent index and
            screened for scams, with the reasons spelled out.
          </p>
          <div className="mt-8 max-w-[940px]">
            <SearchForm initial={params.q} busy={loading} onSearch={(q) => go({ q, fair: params.fair, sort: params.sort })} />
          </div>
          <div ref={chipsRef} className="mt-4 scroll-mt-24">
            {data && <CriteriaChips criteria={data.criteria} />}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-page px-[18px] py-10 md:px-8" aria-labelledby="results-heading">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <h2 id="results-heading" className="text-[26px] font-bold tracking-tight text-text" data-testid="results-heading">
              {loading && !data ? "Searching…" : resultsHeading(shown.length, areas)}
            </h2>
            <p className="mt-1 text-[15px] text-text-muted">
              Sorted by {params.sort === "fit" ? "fit" : SORT_LABELS[params.sort].toLowerCase()}. Rent checked against the Berliner Mietspiegel 2026.
            </p>
            {data?.commute_note && <p className="mt-1 text-[13px] text-text-muted">{data.commute_note}</p>}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex min-h-tap items-center gap-2 rounded-md border border-line-strong bg-surface px-3 text-[14px] text-text">
              Sort:
              <select
                className="bg-transparent font-medium outline-none"
                value={params.sort}
                onChange={(e) => go({ ...params, sort: e.target.value as SortKey }, true)}
              >
                {Object.entries(SORT_LABELS).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <Button
              variant={params.fair ? "dark" : "outline"}
              aria-pressed={params.fair}
              onClick={() => go({ ...params, fair: !params.fair }, true)}
              data-testid="fair-toggle"
            >
              Only fair rents ({fairCount})
            </Button>
            <Button
              variant={thisSaved ? "dark" : "outline"}
              aria-pressed={!!thisSaved}
              onClick={toggleSaveSearch}
              disabled={!data}
              data-testid="save-search"
            >
              {thisSaved ? "Search saved" : "Save search"}
            </Button>
            <Button variant="outline" onClick={share}>
              {copied ? "Link copied" : "Share search"}
            </Button>
            <button type="button" onClick={() => go(null)} className="min-h-tap px-2 text-[14px] text-text-muted underline underline-offset-2 hover:text-text">
              Clear search
            </button>
          </div>
        </div>

        {error && <p role="alert" className="mb-4 rounded-md bg-warn-bg px-4 py-3 text-[14px] text-warn">{error}</p>}
        {thisSaved && news?.key === cacheKey && (
          <p className="mb-4 rounded-md bg-accent-tint px-4 py-3 text-[14px] text-text-body" data-testid="new-since" role="status">
            {newIds.length === 0
              ? "No new flats since you last ran this saved search"
              : `${newIds.length} new flat${newIds.length > 1 ? "s" : ""} since you last ran this saved search`}{" "}
            ({new Date(news.since).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}).
          </p>
        )}
        {data && (
          <SearchNotices
            notices={data.notices ?? []}
            busy={loading}
            onRaiseBudget={(budget) => go({ ...params, budget })}
          />
        )}
        {params.fair && data && fairCount === 0 && results.length > 0 && (
          <p className="mb-4 rounded-md bg-chip px-4 py-3 text-[14px] text-text-body">
            None of these {results.length} flats is within the rent-brake limit.{" "}
            <button type="button" className="font-semibold text-accent underline" onClick={() => go({ ...params, fair: false }, true)}>
              Show all
            </button>
          </p>
        )}

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
          <div className="flex min-w-0 flex-col gap-4">
            {shown.map((item) => (
              <ResultCard
                key={item.listing.id}
                item={item}
                compared={compare.has(item.listing.id)}
                onToggleCompare={compare.toggle}
                compareDisabled={compare.full}
                saved={saved.has(item.listing.id)}
                onToggleSave={saved.toggle}
                highlighted={highlighted === item.listing.id}
                onHover={setHighlighted}
                isNew={newIds.includes(item.listing.id)}
              />
            ))}
            {loading && !data && Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-64 animate-pulse rounded-lg bg-chip" />)}
          </div>
          <div className="lg:sticky lg:top-24">
            {data && (
              <ResultsMap
                results={shown}
                areas={areas}
                allListings={mapListings}
                highlighted={highlighted}
                onHighlight={setHighlighted}
              />
            )}
          </div>
        </div>
      </section>

    </>
  );
}
