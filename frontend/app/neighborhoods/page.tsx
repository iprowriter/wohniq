"use client";

// Berlin Neighborhoods: all 143 areas ranked by a category (or a weighted overall score),
// list on the left, shaded OSM map on the right. Clicking an area on the map selects it
// in the list; switching category re-ranks both. State lives in the URL
// (?category=safety&area=011001&w=…), so every view can be shared.

import dynamic from "next/dynamic";
import Link from "next/link";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { AreaCollection, AreaDetail, NeighborhoodCatalog, Ranking } from "@/lib/neighborhoods/types";
import { getArea, getAreaShapes, getNeighborhoodCatalog, getRanking } from "@/lib/neighborhoods/api";
import {
  OVERALL,
  type ListFilter,
  type Order,
  type PageState,
  categoryById,
  changedWeights,
  defaultWeights,
  filterAreas,
  orderAreas,
  orderLabel,
  pageQuery,
  parsePageState,
  setWeight,
  sourceMap,
} from "@/lib/neighborhoods/logic";
import { CategoryIcon } from "@/components/lifestyle/explorer/icons";
import { CategoryTabs } from "@/components/neighborhoods/CategoryTabs";
import { AreaRow } from "@/components/neighborhoods/AreaRow";
import { AreaDetailPanel } from "@/components/neighborhoods/AreaDetailPanel";
import { WeightsPanel } from "@/components/neighborhoods/WeightsPanel";

const NeighborhoodsMap = dynamic(
  () => import("@/components/neighborhoods/NeighborhoodsMap").then((m) => m.NeighborhoodsMap),
  {
    ssr: false,
    loading: () => <div className="h-full min-h-[320px] animate-pulse rounded-2xl bg-chip" />,
  },
);

const MARKERS = 10;

export default function NeighborhoodsPageRoute() {
  return (
    <Suspense fallback={<div className="mx-auto h-96 max-w-7xl animate-pulse px-4 py-10" />}>
      <NeighborhoodsPage />
    </Suspense>
  );
}

function NeighborhoodsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const [catalog, setCatalog] = useState<NeighborhoodCatalog | null>(null);
  const [shapes, setShapes] = useState<AreaCollection | null>(null);
  const [state, setState] = useState<PageState | null>(null);
  const [draft, setDraft] = useState<Record<string, number>>({});
  const [ranking, setRanking] = useState<Ranking | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<AreaDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [filter, setFilter] = useState<ListFilter>({ query: "", district: "" });
  const [order, setOrder] = useState<Order>("best");
  const [hovered, setHovered] = useState<string | null>(null);
  const [showWeights, setShowWeights] = useState(false);
  const [scrollTo, setScrollTo] = useState<{
    key: string;
    block: ScrollLogicalPosition;
  } | null>(null);
  const rankingReq = useRef(0);
  const detailReq = useRef(0);

  // --- Load the catalog (then the URL state) and the outlines -----------------------------
  const loadCatalog = useCallback(() => {
    setError(null);
    getNeighborhoodCatalog()
      .then((c) => {
        setCatalog(c);
        const initial = parsePageState(new URLSearchParams(params.toString()), c);
        setState(initial);
        setDraft(initial.weights ?? defaultWeights(c));
        if (initial.area) setScrollTo({ key: initial.area, block: "start" });
      })
      .catch((e: Error) => setError(e.message));
    // Read the URL once, on load; afterwards the page writes it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadCatalog();
    getAreaShapes()
      .then(setShapes)
      .catch(() => setShapes({ type: "FeatureCollection", features: [] }));
  }, [loadCatalog]);

  // --- Ranking for the current category / weights ----------------------------------------------
  const category = state?.category ?? OVERALL;
  const weights = state?.weights ?? null;
  const weightsKey = weights ? JSON.stringify(weights) : "";

  const fetchRanking = useCallback(() => {
    if (!state) return;
    const id = ++rankingReq.current;
    setLoading(true);
    setError(null);
    getRanking(state.category, state.category === OVERALL ? state.weights : null)
      .then((r) => id === rankingReq.current && setRanking(r))
      .catch((e: Error) => id === rankingReq.current && setError(e.message))
      .finally(() => id === rankingReq.current && setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, weightsKey, state !== null]);

  useEffect(fetchRanking, [fetchRanking]);

  // --- Detail of the selected area ---------------------------------------------------------------
  const selected = state?.area ?? null;
  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    const id = ++detailReq.current;
    setDetailError(null);
    getArea(selected, weights)
      .then((d) => id === detailReq.current && setDetail(d))
      .catch((e: Error) => id === detailReq.current && setDetailError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, weightsKey]);

  // --- Keep the URL in sync (shareable views) ------------------------------------------------------
  useEffect(() => {
    if (!state || !catalog) return;
    const next = `${pathname}${pageQuery(state, catalog)}`;
    if (next !== `${pathname}${params.toString() ? `?${params}` : ""}`) router.replace(next, { scroll: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, catalog]);

  // --- Scroll the list to a selected row (after it has rendered) -----------------------------------------
  useEffect(() => {
    if (!scrollTo || !ranking) return;
    const el = document.getElementById(`area-${scrollTo.key}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: scrollTo.block });
      setScrollTo(null);
    }
  }, [scrollTo, ranking, filter, order]);

  // --- Derived list -------------------------------------------------------------------------------------
  const sources = useMemo(() => sourceMap(catalog?.sources ?? []), [catalog]);
  const info = catalog ? categoryById(catalog, category) : undefined;
  const list = useMemo(
    () => (ranking ? orderAreas(filterAreas(ranking.areas, filter), order) : []),
    [ranking, filter, order],
  );
  const visible = useMemo(() => new Set(list.map((a) => a.key)), [list]);
  const markers = list.slice(0, MARKERS);
  const total = ranking?.total ?? catalog?.area_count ?? 143;
  const pending = state && catalog ? changedWeights(state.weights ?? defaultWeights(catalog), draft) : 0;
  const customWeights = category === OVERALL && state?.weights != null;

  // --- Actions ------------------------------------------------------------------------------------------
  function setCategory(id: string) {
    setState((s) => (s ? { ...s, category: id } : s));
    if (selected) setScrollTo({ key: selected, block: "start" });
  }
  function select(key: string, fromMap = false) {
    if (!fromMap && key === selected) {
      setState((s) => (s ? { ...s, area: null } : s)); // tap again to collapse
      return;
    }
    if (fromMap && !visible.has(key)) setFilter({ query: "", district: "" }); // make sure it's listed
    setState((s) => (s ? { ...s, area: key } : s));
    setScrollTo({ key, block: fromMap ? "start" : "nearest" });
  }
  const selectFromMap = useCallback((key: string) => select(key, true), [visible, selected]); // eslint-disable-line react-hooks/exhaustive-deps
  function applyWeights() {
    setState((s) => (s ? { ...s, category: OVERALL, weights: draft } : s));
  }
  function resetWeights() {
    if (!catalog) return;
    setDraft(defaultWeights(catalog));
    setState((s) => (s ? { ...s, weights: null } : s));
  }

  const bestLabel = ranking?.best_label ?? null;
  const worstLabel = ranking?.worst_label ?? null;

  return (
    <>
      {/* ── Header ── */}
      <section className="relative overflow-hidden bg-ink px-4 py-10 text-white">
        <div className="relative mx-auto max-w-7xl">
          <p className="text-xs uppercase tracking-[0.2em] text-text-on-ink-muted">Berlin Neighborhoods</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">
            Compare all of Berlin&apos;s neighborhoods
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-text-on-ink-soft">
            Every area ranked on official and open data: crime, road safety, schools, healthcare, parks, transport and
            more. Pick a category to re-rank the list and the map; every number shows its source.
          </p>
          {catalog && (
            <div className="mt-4 flex flex-wrap gap-2 text-xs">
              <span className="rounded-full border border-white/15 bg-white/10 px-2.5 py-1">
                {catalog.area_count} areas
              </span>
              <span className="rounded-full border border-white/15 bg-white/10 px-2.5 py-1">
                {catalog.categories.length} categories
              </span>
              <span className="rounded-full border border-white/15 bg-white/10 px-2.5 py-1">
                {catalog.categories.reduce((n, c) => n + c.metrics.filter((m) => m.available).length, 0)} measures
              </span>
              <span className="rounded-full border border-white/15 bg-white/10 px-2.5 py-1">
                {catalog.sources.length} sources
              </span>
            </div>
          )}
        </div>
      </section>

      {/* ── Category switcher (sticky) ── */}
      <div className="sticky top-[57px] z-40 border-b border-line bg-ground/95 px-4 py-3 backdrop-blur-sm">
        <div className="mx-auto max-w-7xl">
          {catalog ? (
            <CategoryTabs catalog={catalog} active={category} onChange={setCategory} />
          ) : (
            <div className="h-10 animate-pulse rounded-full bg-chip" />
          )}
        </div>
      </div>

      {error && !catalog && (
        <div className="mx-auto max-w-xl px-4 py-16 text-center" role="alert">
          <p className="text-4xl" aria-hidden="true">
            🛰️
          </p>
          <p className="mt-3 text-text-body">{error}</p>
          <button
            type="button"
            onClick={loadCatalog}
            className="mt-4 rounded-full bg-accent px-5 py-2 text-sm font-semibold text-white hover:bg-accent-hover"
          >
            Try again
          </button>
        </div>
      )}

      {catalog && (
        <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[minmax(0,460px)_minmax(0,1fr)]">
          {/* ── Map (first on mobile, sticky on the right on desktop) ── */}
          <aside className="min-w-0 lg:order-2">
            <div className="isolate h-72 overflow-hidden rounded-2xl border border-line bg-white sm:h-96 lg:sticky lg:top-[8.5rem] lg:h-[calc(100vh-10rem)]">
              {shapes && ranking ? (
                <NeighborhoodsMap
                  shapes={shapes}
                  areas={ranking.areas}
                  visible={visible}
                  markers={markers}
                  selected={selected}
                  hovered={hovered}
                  bestLabel={bestLabel}
                  worstLabel={worstLabel}
                  onSelect={selectFromMap}
                />
              ) : (
                <div className="h-full animate-pulse bg-chip" />
              )}
            </div>
          </aside>

          {/* ── Ranked list ── */}
          <div className="min-w-0 lg:order-1" aria-busy={loading}>
            <div className="mb-3">
              <h2 className="text-lg font-semibold text-text">
                {info ? (
                  <>
                    <CategoryIcon id={info.id} size={16} /> {info.question}
                  </>
                ) : (
                  <>⭐ {customWeights ? "Your weighted ranking" : "Overall ranking"}</>
                )}
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-text-muted">
                {info ? info.caveat : catalog.overall.description}
              </p>
            </div>

            {category === OVERALL && (
              <div className="mb-3">
                <button
                  type="button"
                  aria-expanded={showWeights}
                  onClick={() => setShowWeights((v) => !v)}
                  className="rounded-full border border-line bg-white px-3.5 py-1.5 text-xs font-medium text-text-body hover:border-accent/50 hover:text-accent"
                >
                  ⚖️ {showWeights ? "Hide weights" : "Adjust what matters"}
                  {customWeights && (
                    <span className="ml-1.5 rounded-full bg-accent-tint px-1.5 text-[10px] text-accent">custom</span>
                  )}
                </button>
                {showWeights && (
                  <div className="animate-fade-up mt-3">
                    <WeightsPanel
                      catalog={catalog}
                      draft={draft}
                      pending={pending}
                      updating={loading}
                      canUpdate={Object.values(draft).some((v) => v > 0)}
                      onChange={(id, v) => setDraft((d) => setWeight(d, id, v, catalog.max_weight))}
                      onUpdate={applyWeights}
                      onReset={resetWeights}
                    />
                  </div>
                )}
              </div>
            )}

            {/* Filters */}
            <div className="mb-3 flex flex-wrap gap-2">
              <label className="relative min-w-[10rem] flex-1">
                <span className="sr-only">Find an area</span>
                <input
                  type="search"
                  value={filter.query}
                  onChange={(e) => setFilter((f) => ({ ...f, query: e.target.value }))}
                  placeholder="Find an area…"
                  className="w-full rounded-full border border-line bg-white px-4 py-2 text-sm placeholder:text-text-faint focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
                />
              </label>
              <label>
                <span className="sr-only">District</span>
                <select
                  value={filter.district}
                  onChange={(e) => setFilter((f) => ({ ...f, district: e.target.value }))}
                  className="rounded-full border border-line bg-white px-3 py-2 text-sm text-text-body focus:border-accent focus:outline-none"
                >
                  <option value="">All districts</option>
                  {catalog.districts.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="mb-3 flex items-center justify-between gap-2">
              <p className="text-xs text-text-muted" aria-live="polite">
                {ranking ? (
                  <>
                    Showing {list.length} of {total} · ranks are Berlin-wide
                    {loading && <span className="ml-2 text-accent">Updating…</span>}
                  </>
                ) : (
                  "Ranking Berlin's areas…"
                )}
              </p>
              <div className="flex rounded-full bg-chip p-0.5 text-xs font-medium" role="group" aria-label="Order">
                {(["best", "worst"] as Order[]).map((o) => (
                  <button
                    key={o}
                    type="button"
                    aria-pressed={order === o}
                    onClick={() => setOrder(o)}
                    className={`rounded-full px-3 py-1 transition ${order === o ? "bg-white text-text shadow" : "text-text-muted hover:text-text"}`}
                  >
                    {orderLabel(o, info ? bestLabel : null, info ? worstLabel : null)}
                  </button>
                ))}
              </div>
            </div>

            {error && catalog && (
              <div className="mb-3 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
                {error}{" "}
                <button type="button" onClick={fetchRanking} className="font-semibold underline">
                  Try again
                </button>
              </div>
            )}

            {!ranking && !error && (
              <div className="space-y-2" aria-busy="true">
                {Array.from({ length: 6 }, (_, i) => (
                  <div key={i} className="h-20 animate-pulse rounded-2xl bg-chip" />
                ))}
              </div>
            )}

            {ranking && list.length === 0 && (
              <div className="rounded-2xl border border-dashed border-line-strong p-8 text-center text-sm text-text-muted">
                No area matches “{filter.query}”{filter.district ? ` in ${filter.district}` : ""}.{" "}
                <button
                  type="button"
                  onClick={() => setFilter({ query: "", district: "" })}
                  className="font-semibold text-accent hover:underline"
                >
                  Clear filters
                </button>
              </div>
            )}

            <ol
              className={`space-y-2 transition-opacity ${loading && ranking ? "opacity-60" : ""}`}
              aria-label="Ranked neighborhoods"
            >
              {list.map((a) => (
                <AreaRow
                  key={a.key}
                  area={a}
                  total={total}
                  bestLabel={bestLabel}
                  worstLabel={worstLabel}
                  selected={a.key === selected}
                  onSelect={select}
                  onHover={setHovered}
                >
                  {detail && detail.key === a.key ? (
                    <AreaDetailPanel
                      detail={detail}
                      catalog={catalog}
                      category={category}
                      sources={sources}
                      onCategory={setCategory}
                    />
                  ) : detailError ? (
                    <p className="mt-3 text-xs text-red-600">{detailError}</p>
                  ) : (
                    <div className="mt-3 h-24 animate-pulse rounded-xl bg-ground" />
                  )}
                </AreaRow>
              ))}
            </ol>

            <p className="mt-6 text-xs leading-relaxed text-text-muted">
              Areas are Berlin&apos;s 143 official LOR <em>Bezirksregionen</em>. Scores are percentiles against all of
              Berlin (100 = best); the badges mark the top and bottom 20%. Looking for a flat?{" "}
              <Link href="/lifestyle" className="text-accent hover:underline">
                Try Lifestyle Match
              </Link>{" "}
              or{" "}
              <Link href="/" className="text-accent hover:underline">
                search listings
              </Link>
              .
            </p>
          </div>
        </div>
      )}
    </>
  );
}
