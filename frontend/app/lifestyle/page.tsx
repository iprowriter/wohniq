"use client";

/**
 * Lifestyle match explorer (design B in two columns, T9.6): settings on the left; the map
 * with "Best areas for you" under it on the right. Every change re-ranks live. Ranking is
 * the backend's deterministic engine (ADR-0011); answers stay in this tab (ADR-0012).
 */

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Answers, Catalog, MatchResponse, PresetOut, RegionCollection, RegionResult } from "@/lib/lifestyle/types";
import { getCatalog, getMatches, getRegionShapes } from "@/lib/lifestyle/api";
import { clearState, fromPreset, loadState, saveState } from "@/lib/lifestyle/logic";
import { addExcluded, loadAdjustments, removeExcluded, saveAdjustments, SCORE_BANDS, sourceIndex } from "@/lib/lifestyle/results";
import { liveSummary, MAX_COMPARE, PAGE, tripLabel } from "@/lib/lifestyle/explorer";
import { euro } from "@/lib/format";
import { ExplorerMap } from "@/components/lifestyle/explorer/ExplorerMap";
import { SettingsPanel } from "@/components/lifestyle/explorer/SettingsPanel";
import { CompareAreas, RankingList } from "@/components/lifestyle/explorer/RankingList";
import { ProfileIcon } from "@/components/lifestyle/explorer/icons";
import { ListingsPanel } from "@/components/lifestyle/ListingsPanel";
import { Button } from "@/components/ui/primitives";

const DEBOUNCE_MS = 250;

export default function LifestyleExplorer() {
  const [ready, setReady] = useState(false); // tab state read (avoids a first-visit flash)
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [shapes, setShapes] = useState<RegionCollection | null>(null);
  const [answers, setAnswers] = useState<Answers | null>(null);
  const [presetId, setPresetId] = useState<string | null>(null);
  const [overrides, setOverrides] = useState<Record<string, number>>({});
  const [excluded, setExcluded] = useState<string[]>([]);
  const [limit, setLimit] = useState(PAGE);
  const [data, setData] = useState<MatchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [mode, setMode] = useState<"top" | "all">("top");
  const [compare, setCompare] = useState<string[]>([]);
  const [flatsFor, setFlatsFor] = useState<{ key: string; name: string } | null>(null);
  const [adjust, setAdjust] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    const saved = loadState(window.sessionStorage);
    if (saved) {
      setAnswers(saved.answers);
      setPresetId(saved.presetId);
      const adj = loadAdjustments(window.sessionStorage, saved.answers);
      setOverrides(adj.overrides);
      setExcluded(adj.excluded);
    }
    setReady(true);
    getCatalog().then(setCatalog).catch((e: Error) => setError(e.message));
    getRegionShapes().then(setShapes).catch(() => {});
  }, []);

  // Re-rank on every change (debounced); keep the last ranking on screen meanwhile.
  useEffect(() => {
    if (!answers) return;
    saveState(window.sessionStorage, { answers, step: "explorer", presetId });
    saveAdjustments(window.sessionStorage, { overrides, excluded }, answers);
    const n = ++seq.current;
    setLoading(true);
    const t = setTimeout(() => {
      getMatches(answers, { weights: overrides, excluded, limit })
        .then((d) => {
          if (n !== seq.current) return;
          setData(d);
          setError(null);
        })
        .catch((e: Error) => n === seq.current && setError(e.message))
        .finally(() => n === seq.current && setLoading(false));
    }, DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [answers, presetId, overrides, excluded, limit]);

  const names = useMemo(
    () => Object.fromEntries((shapes?.features ?? []).map((f) => [f.properties.key, f.properties.name])),
    [shapes],
  );
  const scores = useMemo(() => new Map((data?.scores ?? []).map((s) => [s.key, s.score])), [data]);
  const sources = useMemo(() => sourceIndex(catalog?.sources ?? []), [catalog]);
  const destination = catalog?.destinations.find((d) => d.id === answers?.destination) ?? null;
  const results = data?.results ?? [];
  const top = results.slice(0, 10);
  // Weights as shown: the server's, with the user's latest changes on top (instant feedback).
  const weights = useMemo(
    () => (data?.weights ?? []).map((w) => (w.attribute in overrides ? { ...w, value: overrides[w.attribute], overridden: true } : w)),
    [data, overrides],
  );

  function pickPreset(p: PresetOut) {
    setAnswers(fromPreset(p));
    setPresetId(p.id);
    setOverrides({});
    setLimit(PAGE);
    setOpen(null);
  }

  function resetProfile() {
    const p = catalog?.presets.find((x) => x.id === presetId);
    if (p) pickPreset(p);
  }

  function clearAll() {
    clearState(window.sessionStorage);
    setAnswers(null);
    setPresetId(null);
    setOverrides({});
    setExcluded([]);
    setData(null);
    setCompare([]);
    setOpen(null);
  }

  const openArea = useCallback(
    (key: string, scroll = false) => {
      const s = data?.scores.find((x) => x.key === key);
      if (s && s.rank > limit) setLimit(Math.ceil(s.rank / PAGE) * PAGE);
      setOpen(key);
      if (scroll) setTimeout(() => document.getElementById(`area-${key}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 120);
    },
    [data, limit],
  );

  function exclude(key: string) {
    setExcluded((e) => addExcluded(e, key));
    setCompare((c) => c.filter((k) => k !== key));
    if (open === key) setOpen(null);
  }

  const selected = open ? (results.find((r) => r.key === open) ?? null) : null;
  const selectedScore = open ? data?.scores.find((s) => s.key === open) : undefined;
  const comparing = compare.map((k) => results.find((r) => r.key === k)).filter(Boolean) as RegionResult[];

  const settings =
    catalog && answers ? (
      <SettingsPanel
        catalog={catalog}
        answers={answers}
        presetId={presetId}
        weights={weights}
        removed={excluded.map((k) => ({ key: k, name: names[k] ?? k }))}
        onPreset={pickPreset}
        onAnswers={(a) => setAnswers(a)}
        onWeight={(attr, v) => setOverrides((o) => ({ ...o, [attr]: v }))}
        onResetProfile={resetProfile}
        onRestore={(k) => setExcluded((e) => removeExcluded(e, k))}
        onClear={clearAll}
      />
    ) : null;

  return (
    <div className="mx-auto max-w-[1440px] px-[18px] py-6 md:px-6">
      <div className="grid items-start gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
        {/* Settings: left column on desktop */}
        <aside className="hidden rounded-lg border border-line bg-surface p-5 lg:sticky lg:top-24 lg:block lg:max-h-[calc(100vh-7rem)] lg:overflow-y-auto">
          {settings ?? <FirstVisitIntro catalog={catalog} />}
        </aside>

        <div className="flex min-w-0 flex-col gap-4">
          {/* Phone: settings behind "Adjust" */}
          <div className="flex items-center justify-between gap-3 lg:hidden">
            <h1 className="text-[22px] font-bold tracking-tight text-text">Lifestyle match</h1>
            {answers && <Button variant="outline" onClick={() => setAdjust(true)}>Adjust</Button>}
          </div>

          {/* Map */}
          <section className="relative overflow-hidden rounded-lg border border-line bg-surface" aria-label="Map of Berlin's areas by match">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2 text-[13px]">
              <span className="text-text-body" aria-live="polite" data-testid="live-summary">
                {data ? (
                  <>
                    <span className="mr-1.5 inline-flex items-center gap-1 font-semibold text-ok"><span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-live" />Live</span>
                    {liveSummary(data, !!answers?.destination)}
                    {loading && <span className="ml-2 text-text-muted">updating…</span>}
                  </>
                ) : answers ? "Ranking Berlin's 143 areas…" : "Pick a profile to rank Berlin's 143 areas."}
              </span>
              <div className="flex gap-1" role="group" aria-label="Map view">
                {(["top", "all"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    aria-pressed={mode === m}
                    onClick={() => setMode(m)}
                    className={`min-h-[34px] rounded-md px-3 ${mode === m ? "bg-accent-tint font-semibold text-accent" : "text-text-body hover:bg-ground"}`}
                  >
                    {m === "top" ? "Top 10" : "All of Berlin"}
                  </button>
                ))}
              </div>
            </div>
            <div className="relative">
              <ExplorerMap
                shapes={shapes}
                scores={scores}
                excluded={new Set(excluded)}
                top={top}
                mode={mode}
                hovered={hovered}
                selected={open}
                onHover={setHovered}
                onSelect={(k) => openArea(k)}
                destination={destination}
                height={360}
              />
              {open && selectedScore && (
                <div className="absolute left-3 right-3 top-3 z-[500] flex items-center gap-3 rounded-md bg-surface px-3 py-2 shadow-md sm:right-auto sm:max-w-[320px]" data-testid="map-card">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ink text-[12px] font-bold text-white">{selectedScore.rank}</span>
                  <span className="min-w-0 text-[13px]">
                    <span className="block truncate font-semibold text-text">{names[open] ?? open}</span>
                    <span className="block text-text-muted">
                      {Math.round(selectedScore.score)} match
                      {selected ? ` · ${euro(selected.warm_rent_eur)}` : ""}
                      {selected && tripLabel(selected) ? ` · ${tripLabel(selected)}` : ""}
                    </span>
                  </span>
                  <Button variant="ghost" className="shrink-0 !min-h-[36px] !px-2 text-[13px]" onClick={() => openArea(open, true)}>
                    Details below
                  </Button>
                </div>
              )}
              {data && (
                <div className="pointer-events-none absolute bottom-2 left-2 z-[500] flex items-center gap-1.5 rounded-sm bg-surface/95 px-2 py-1 text-[11px] text-text-muted shadow-sm">
                  Match
                  {SCORE_BANDS.map((b) => (
                    <span key={b.label} className="inline-flex items-center gap-1">
                      <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-[2px]" style={{ background: b.color }} />
                      {b.label}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </section>

          {error && (
            <p role="alert" className="rounded-md bg-warn-bg px-4 py-3 text-[14px] text-warn">
              {error}
            </p>
          )}
          {data && Object.values(data.unscored).map((msg) => (
            <p key={msg} className="rounded-md bg-chip px-4 py-2 text-[13px] text-text-body">{msg}</p>
          ))}

          {ready && !answers && catalog && <ProfileCards catalog={catalog} onPick={pickPreset} />}
          {answers && !data && !error && <div className="h-80 animate-pulse rounded-lg bg-chip" aria-busy="true" />}
          {data && (
            <div className={loading ? "opacity-80 transition-opacity" : ""}>
              <RankingList
                results={results}
                weights={weights}
                persona={data.persona}
                sources={sources}
                destination={destination?.short}
                open={open}
                hovered={hovered}
                compare={compare}
                remaining={(data.scores.length ?? 0) - results.length}
                onOpen={setOpen}
                onHover={setHovered}
                onToggleCompare={(k) => setCompare((c) => (c.includes(k) ? c.filter((x) => x !== k) : c.length < MAX_COMPARE ? [...c, k] : c))}
                onExclude={exclude}
                onSeeFlats={(key, name) => setFlatsFor({ key, name })}
                onMore={() => setLimit((l) => l + PAGE)}
              />
            </div>
          )}
          {comparing.length >= 2 && (
            <CompareAreas regions={comparing} weights={weights} destination={destination?.short} onRemove={(k) => setCompare((c) => c.filter((x) => x !== k))} />
          )}
          {compare.length === 1 && <p className="text-[13px] text-text-muted">Pick one or two more areas to compare them side by side.</p>}
        </div>
      </div>

      {/* Phone settings drawer */}
      {adjust && settings && (
        <div className="fixed inset-0 z-[1200] bg-[rgba(13,19,33,0.5)] lg:hidden" onClick={() => setAdjust(false)}>
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Adjust your match"
            className="absolute inset-x-0 bottom-0 max-h-[88vh] overflow-y-auto rounded-t-xl bg-surface p-5"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.key === "Escape" && setAdjust(false)}
          >
            <div className="mb-3 flex justify-end">
              <Button onClick={() => setAdjust(false)}>Show results</Button>
            </div>
            {settings}
          </div>
        </div>
      )}

      <ListingsPanel region={flatsFor} budget={answers?.budget_eur ?? 0} onClose={() => setFlatsFor(null)} />
    </div>
  );
}

function FirstVisitIntro({ catalog }: { catalog: Catalog | null }) {
  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-[20px] font-bold tracking-tight text-text">Lifestyle match</h1>
      <p className="text-[14px] leading-relaxed text-text-body">
        Pick a profile under the map, then change anything: budget, where you go, what matters. The
        map and the ranking of all {catalog?.region_count ?? 143} areas update as you go.
      </p>
      <Link href="/lifestyle/questions" className="inline-flex min-h-tap items-center justify-center rounded-md border border-line-strong px-3 text-[14px] font-medium text-text hover:bg-ground">
        Answer questions instead
      </Link>
      {catalog && <p className="text-[12.5px] leading-relaxed text-text-muted">{catalog.privacy}</p>}
    </div>
  );
}

function ProfileCards({ catalog, onPick }: { catalog: Catalog; onPick: (p: PresetOut) => void }) {
  return (
    <section aria-labelledby="profiles-heading" className="rounded-lg border border-line bg-surface p-5" data-testid="profile-cards">
      <h2 id="profiles-heading" className="text-[20px] font-semibold text-text">Start with a profile</h2>
      <p className="text-[14px] text-text-muted">You can change everything afterwards.</p>
      <ul className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {catalog.presets.map((p) => (
          <li key={p.id}>
            <button
              type="button"
              onClick={() => onPick(p)}
              className="flex h-full w-full flex-col gap-1.5 rounded-md border border-line p-4 text-left hover:border-accent hover:bg-accent-tint/40"
            >
              <span className="flex items-center gap-2 text-[16px] font-semibold text-text">
                <span className="flex h-8 w-8 items-center justify-center rounded-md bg-accent-tint text-accent"><ProfileIcon id={p.id} /></span>
                {p.label}
              </span>
              <span className="text-[13.5px] leading-snug text-text-muted">{p.blurb}</span>
              <span className="text-[12.5px] text-text-muted">Budget {euro(p.answers.budget_eur)} warm · {p.answers.size_m2} m²</span>
            </button>
          </li>
        ))}
      </ul>
      <Link href="/lifestyle/questions" className="mt-4 inline-block text-[14px] text-accent underline underline-offset-2">
        Answer questions instead
      </Link>
    </section>
  );
}
