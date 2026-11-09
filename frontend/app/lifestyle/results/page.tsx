"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Answers, Catalog, MatchResponse, RegionCollection, WeightOut } from "@/lib/lifestyle/types";
import { getCatalog, getMatches, getProfile, getRegionShapes } from "@/lib/lifestyle/api";
import { clearState, loadState } from "@/lib/lifestyle/logic";
import {
  activeCount,
  addExcluded,
  loadAdjustments,
  pendingChanges,
  removeExcluded,
  saveAdjustments,
  setWeight,
  sourceIndex,
  weightMap,
  weightOverrides,
} from "@/lib/lifestyle/results";
import { RegionCard } from "@/components/lifestyle/RegionCard";
import { TunePanel } from "@/components/lifestyle/TunePanel";
import { ListingsPanel } from "@/components/lifestyle/ListingsPanel";
import { PrivacyNote } from "@/components/lifestyle/PrivacyNote";

const ResultsMap = dynamic(() => import("@/components/lifestyle/ResultsMap").then((m) => m.ResultsMap), {
  ssr: false,
  loading: () => <div className="h-full min-h-[360px] animate-pulse rounded-2xl bg-gray-100" />,
});

const PAGE = 10;

export default function LifestyleResultsPage() {
  const router = useRouter();
  const [answers, setAnswers] = useState<Answers | null | undefined>(undefined);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [shapes, setShapes] = useState<RegionCollection | null>(null);
  const [base, setBase] = useState<WeightOut[] | null>(null); // weights implied by the answers
  const [draft, setDraft] = useState<Record<string, number>>({});
  const [applied, setApplied] = useState<{ overrides: Record<string, number>; excluded: string[] }>({
    overrides: {},
    excluded: [],
  });
  const [limit, setLimit] = useState(PAGE);
  const [data, setData] = useState<MatchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [flatsFor, setFlatsFor] = useState<{ key: string; name: string } | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});

  // 1. Answers + adjustments from this tab only.
  useEffect(() => {
    const saved = loadState(window.sessionStorage);
    setAnswers(saved?.answers ?? null);
    if (saved) setApplied(loadAdjustments(window.sessionStorage, saved.answers));
  }, []);

  // 2. Static data (catalog, outlines) + the weights the answers imply.
  useEffect(() => {
    if (!answers) return;
    Promise.all([getCatalog(), getRegionShapes(), getProfile(answers)])
      .then(([c, s, p]) => {
        setCatalog(c);
        setShapes(s);
        setNames(Object.fromEntries(s.features.map((f) => [f.properties.key, f.properties.name])));
        setBase(p.weights);
      })
      .catch((e: Error) => setError(e.message));
  }, [answers]);

  // Sliders start from the answers plus any saved adjustments.
  useEffect(() => {
    if (base) setDraft({ ...weightMap(base), ...applied.overrides });
    // Only when the base weights arrive; later edits live in `draft`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base]);

  // 3. Ranked areas for the applied adjustments.
  const fetchMatches = useCallback(() => {
    if (!answers || !base) return;
    setLoading(true);
    setError(null);
    getMatches(answers, { weights: applied.overrides, excluded: applied.excluded, limit })
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [answers, base, applied, limit]);

  useEffect(fetchMatches, [fetchMatches]);

  useEffect(() => {
    if (answers) saveAdjustments(window.sessionStorage, applied, answers);
  }, [applied, answers]);

  const baseMap = useMemo(() => (base ? weightMap(base) : {}), [base]);
  const appliedMap = useMemo(() => ({ ...baseMap, ...applied.overrides }), [baseMap, applied.overrides]);
  const pending = pendingChanges(appliedMap, draft);
  const sources = useMemo(() => sourceIndex(catalog?.sources ?? []), [catalog]);
  const destinationName = catalog?.destinations.find((d) => d.id === answers?.destination)?.short;

  function update() {
    setApplied((a) => ({ ...a, overrides: weightOverrides(baseMap, draft) }));
  }

  function exclude(key: string) {
    setApplied((a) => ({ ...a, excluded: addExcluded(a.excluded, key) }));
    if (selected === key) setSelected(null);
  }

  function restore(key: string) {
    setApplied((a) => ({ ...a, excluded: removeExcluded(a.excluded, key) }));
  }

  function selectFromMap(key: string) {
    setSelected(key);
    document.getElementById(`region-${key}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function clearAll() {
    clearState(window.sessionStorage);
    router.push("/lifestyle");
  }

  const closeFlats = useCallback(() => setFlatsFor(null), []);

  if (answers === null) {
    return (
      <div className="mx-auto max-w-xl px-4 py-24 text-center">
        <p className="text-4xl" aria-hidden="true">🧭</p>
        <h1 className="mt-4 text-2xl font-bold">Let&apos;s get to know you first</h1>
        <p className="mt-2 text-gray-500">Answer a few questions and we&apos;ll match you to Berlin neighbourhoods.</p>
        <Link
          href="/lifestyle"
          className="mt-6 inline-block rounded-full bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-500"
        >
          Start Lifestyle Match
        </Link>
      </div>
    );
  }

  const persona = data?.persona;
  const shown = data?.results ?? [];
  const remaining = (data?.scores.length ?? 0) - shown.length;

  return (
    <>
      {/* ── Header ── */}
      <section className="relative overflow-hidden bg-gray-950 px-4 py-10 text-white">
        <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-fuchsia-600/25 blur-3xl" aria-hidden="true" />
        <div className="relative mx-auto flex max-w-7xl flex-wrap items-end justify-between gap-6">
          <div className="flex items-center gap-4">
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/10 text-4xl" aria-hidden="true">
              {persona?.emoji ?? "🧭"}
            </span>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-indigo-300">Lifestyle Match · your results</p>
              <h1 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">
                {persona ? persona.title : "Matching you to Berlin…"}
              </h1>
              {persona && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {persona.priorities.map((p) => (
                    <span key={p} className="rounded-full border border-white/15 bg-white/10 px-2.5 py-0.5 text-xs">
                      {p}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            <Link href="/lifestyle" className="rounded-full border border-white/20 px-4 py-2 text-sm hover:bg-white/10">
              ← Change answers
            </Link>
            <button type="button" onClick={clearAll} className="rounded-full px-4 py-2 text-sm text-gray-400 hover:bg-white/10 hover:text-white">
              Clear my answers
            </button>
          </div>
        </div>
      </section>

      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-8 lg:grid-cols-[minmax(0,1fr)_420px]">
        {/* ── Map + controls (first on mobile, sticky sidebar on desktop) ── */}
        <aside className="min-w-0 space-y-5 lg:order-2">
          <div className="space-y-5 lg:sticky lg:top-20">
            <div className="h-72 overflow-hidden rounded-2xl border border-gray-200 bg-white lg:h-[360px]">
              {shapes && data ? (
                <ResultsMap shapes={shapes} scores={data.scores} top={shown} selected={selected} onSelect={selectFromMap} />
              ) : (
                <div className="h-full animate-pulse bg-gray-100" />
              )}
            </div>
            {catalog && base && (
              <TunePanel
                attributes={catalog.attributes}
                base={base}
                draft={draft}
                pending={pending}
                canUpdate={pending > 0 && activeCount(draft) > 0}
                updating={loading}
                unscored={data?.unscored ?? {}}
                removed={applied.excluded.map((k) => ({ key: k, name: names[k] ?? k }))}
                onChange={(attr, v) => setDraft((d) => setWeight(d, attr, v))}
                onReset={() => setDraft(weightMap(base))}
                onUpdate={update}
                onRestore={restore}
              />
            )}
            {activeCount(draft) === 0 && base && (
              <p className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800">Turn at least one slider up to rank areas.</p>
            )}
          </div>
        </aside>

        {/* ── Ranked areas ── */}
        <main className="min-w-0 lg:order-1" aria-busy={loading}>
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-xl font-semibold text-gray-900">
              {data ? `Your top ${shown.length} of ${data.scores.length} Berlin areas` : "Ranking Berlin's areas…"}
            </h2>
            {loading && data && <span className="text-xs text-indigo-600">Updating…</span>}
          </div>
          <p className="mb-5 text-sm text-gray-500">
            Areas where a typical flat fits your budget come first; the rest follow, ranked lower. Every number links to
            its source.
          </p>

          {error && (
            <div className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
              {error}{" "}
              <button type="button" onClick={fetchMatches} className="font-semibold underline">
                Try again
              </button>
            </div>
          )}
          {data &&
            Object.entries(data.unscored).map(([attr, msg]) => (
              <p key={attr} className="mb-4 rounded-xl bg-amber-50 px-4 py-2 text-sm text-amber-800">
                {msg}
              </p>
            ))}

          {!data && !error && (
            <div className="space-y-4" aria-busy="true">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-48 animate-pulse rounded-2xl bg-gray-100" />
              ))}
            </div>
          )}

          <div className={`space-y-4 transition-opacity ${loading && data ? "opacity-60" : ""}`}>
            {shown.map((r, i) => (
              <RegionCard
                key={r.key}
                result={r}
                sources={sources}
                destinationName={destinationName}
                selected={selected === r.key}
                onSelect={setSelected}
                onExclude={exclude}
                onSeeFlats={(key, name) => setFlatsFor({ key, name })}
                style={{ animationDelay: `${Math.min(i, 8) * 40}ms` }}
              />
            ))}
          </div>

          {data && remaining > 0 && (
            <div className="mt-6 text-center">
              <button
                type="button"
                onClick={() => setLimit((l) => l + PAGE)}
                className="rounded-full border border-gray-300 px-5 py-2.5 text-sm font-semibold text-gray-700 hover:border-indigo-400 hover:text-indigo-700"
              >
                Show {Math.min(PAGE, remaining)} more areas
              </button>
            </div>
          )}
          {catalog && (
            <div className="mt-8">
              <PrivacyNote text={catalog.privacy} compact />
            </div>
          )}
        </main>
      </div>

      <ListingsPanel region={flatsFor} budget={answers?.budget_eur ?? 0} onClose={closeFlats} />
    </>
  );
}
