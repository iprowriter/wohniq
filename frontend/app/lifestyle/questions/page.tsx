"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Answers, Catalog, PresetOut, ProfileResponse } from "@/lib/lifestyle/types";
import { getCatalog, getProfile } from "@/lib/lifestyle/api";
import {
  SUMMARY,
  WELCOME,
  clearState,
  defaultAnswers,
  fromPreset,
  hasAnyPreference,
  loadState,
  nextStep,
  pageIssues,
  prevStep,
  saveState,
  stepsFor,
} from "@/lib/lifestyle/logic";
import { StepProgress } from "@/components/lifestyle/StepProgress";
import { PresetCards } from "@/components/lifestyle/PresetCards";
import { OptionGroup } from "@/components/lifestyle/OptionGroup";
import { BudgetFields } from "@/components/lifestyle/BudgetFields";
import { DestinationPicker } from "@/components/lifestyle/DestinationPicker";
import { PersonaCard } from "@/components/lifestyle/PersonaCard";
import { ChoicesSummary } from "@/components/lifestyle/ChoicesSummary";
import { WeightBars } from "@/components/lifestyle/WeightBars";
import { PrivacyNote } from "@/components/lifestyle/PrivacyNote";

const HOW_IT_WORKS = [
  { title: "Tell us how you live", body: "Four short pages. No sign-up, no address, nothing stored." },
  { title: "We score every area", body: "Official Berlin data on rent, safety, noise, green space and more." },
  { title: "You stay in control", body: "See why each area fits, tune the weights, remove areas." },
];

export default function LifestylePage() {
  const router = useRouter();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Answers>(defaultAnswers);
  const [presetId, setPresetId] = useState<string | null>(null);
  const [step, setStep] = useState<string>(WELCOME);
  const [visited, setVisited] = useState<Set<string>>(new Set([WELCOME]));
  const [restored, setRestored] = useState(false);
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  const loadCatalog = useCallback(() => {
    setCatalogError(null);
    getCatalog()
      .then(setCatalog)
      .catch((e: Error) => setCatalogError(e.message));
  }, []);

  // Restore this tab's answers (sessionStorage only), then load the questionnaire.
  useEffect(() => {
    const saved = loadState(window.sessionStorage);
    if (saved) {
      setAnswers(saved.answers);
      setStep(saved.step);
      setPresetId(saved.presetId);
      setVisited(new Set([WELCOME, saved.step]));
    }
    setRestored(true);
    loadCatalog();
  }, [loadCatalog]);

  useEffect(() => {
    if (restored) saveState(window.sessionStorage, { answers, step, presetId });
  }, [answers, step, presetId, restored]);

  const steps = useMemo(() => (catalog ? stepsFor(catalog) : [WELCOME, SUMMARY]), [catalog]);

  // A step restored from an older session may no longer exist: start over gracefully.
  useEffect(() => {
    if (catalog && !steps.includes(step)) setStep(WELCOME);
  }, [catalog, steps, step]);
  const labels = useMemo(
    () => Object.fromEntries((catalog?.attributes ?? []).map((a) => [a.id, a.label])),
    [catalog],
  );
  const stepLabels = useMemo(
    () => [
      { id: WELCOME, label: "Start" },
      ...(catalog?.pages ?? []).map((p) => ({ id: p.id, label: p.title })),
      { id: SUMMARY, label: "Your match profile" },
    ],
    [catalog],
  );

  // The summary shows what the server derived from the answers (weights, persona).
  useEffect(() => {
    if (step !== SUMMARY || !catalog) return;
    let cancelled = false;
    setProfileError(null);
    getProfile(answers)
      .then((p) => !cancelled && setProfile(p))
      .catch((e: Error) => !cancelled && setProfileError(e.message));
    return () => {
      cancelled = true;
    };
  }, [step, answers, catalog]);

  function go(target: string) {
    setStep(target);
    setVisited((v) => new Set(v).add(target));
    cardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function pickPreset(p: PresetOut) {
    setAnswers(fromPreset(p));
    setPresetId(p.id);
    setProfile(null);
    go(steps[1]);
  }

  function startFromScratch() {
    setAnswers(defaultAnswers());
    setPresetId(null);
    setProfile(null);
    go(steps[1]);
  }

  function clearAll() {
    clearState(window.sessionStorage);
    setAnswers(defaultAnswers());
    setPresetId(null);
    setProfile(null);
    setVisited(new Set([WELCOME]));
    setStep(WELCOME);
  }

  function update(next: Answers) {
    setAnswers(next);
    setProfile(null);
  }

  const page = catalog?.pages.find((p) => p.id === step);
  const issues = page ? pageIssues(page.id, answers) : [];
  const anyPreference = catalog ? hasAnyPreference(answers, catalog) : false;
  const presetLabel = catalog?.presets.find((p) => p.id === presetId)?.label;

  function pageForQuestion(question: string): string | null {
    if (question === "Budget (warm)" || question === "Flat") return "move";
    if (question === "Where you go most") return "days";
    return catalog?.questions.find((q) => q.prompt === question)?.page ?? null;
  }

  return (
    <>
      {/* ── Hero ── */}
      <section className="relative overflow-hidden bg-ink px-4 pb-28 pt-14 text-white">
        <div className="relative mx-auto max-w-3xl text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-text-on-ink-soft">
            Lifestyle match · questions
          </span>
          <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">
            Find the Berlin neighbourhood that{" "}
            <span className="whitespace-nowrap text-accent-on-ink">
              fits your life.
            </span>
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-base text-text-muted sm:text-lg">
            Tell us how you live. We match you to {catalog?.region_count ?? 143} Berlin areas using official
            data — and show you exactly why.
          </p>
        </div>
      </section>

      {/* ── Questionnaire card ── */}
      <div ref={cardRef} className="relative mx-auto -mt-20 max-w-3xl scroll-mt-24 px-4 pb-16">
        <div className="rounded-lg border border-line bg-white p-5 shadow-md sm:p-8">
          {catalogError ? (
            <div className="py-10 text-center">
              <p className="mt-3 font-semibold text-text">The questionnaire didn&apos;t load</p>
              <p className="mt-1 text-sm text-text-muted">{catalogError}</p>
              <button
                type="button"
                onClick={loadCatalog}
                className="mt-5 rounded-full bg-accent px-5 py-2 text-sm font-semibold text-white hover:bg-accent-hover"
              >
                Try again
              </button>
            </div>
          ) : !catalog ? (
            <div className="space-y-4 py-4" aria-busy="true" aria-label="Loading the questionnaire">
              <div className="h-1.5 animate-pulse rounded-full bg-chip" />
              <div className="h-8 w-2/3 animate-pulse rounded-lg bg-chip" />
              <div className="grid gap-3 sm:grid-cols-3">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="h-36 animate-pulse rounded-2xl bg-chip" />
                ))}
              </div>
            </div>
          ) : (
            <>
              <StepProgress steps={stepLabels} current={step} visited={visited} onJump={go} />

              <div key={step} className="animate-fade-up mt-8">
                {/* ── Welcome ── */}
                {step === WELCOME && (
                  <div className="space-y-8">
                    <div className="grid gap-4 sm:grid-cols-3">
                      {HOW_IT_WORKS.map((h) => (
                        <div key={h.title} className="rounded-2xl bg-ground p-4">
                                                    <p className="mt-2 text-sm font-semibold text-text">{h.title}</p>
                          <p className="mt-1 text-xs leading-relaxed text-text-muted">{h.body}</p>
                        </div>
                      ))}
                    </div>
                    <div>
                      <h2 className="text-xl font-semibold text-text">Start with a profile that sounds like you</h2>
                      <p className="mt-1 text-sm text-text-muted">
                        It pre-fills the questions — you can change every answer.
                      </p>
                      <div className="mt-4">
                        <PresetCards
                          presets={catalog.presets}
                          selected={presetId}
                          onPick={pickPreset}
                          onScratch={startFromScratch}
                        />
                      </div>
                    </div>
                    <PrivacyNote text={catalog.privacy} compact />
                  </div>
                )}

                {/* ── Question pages ── */}
                {page && (
                  <div className="space-y-8">
                    <div>
                      <h2 className="text-2xl font-bold tracking-tight text-text">{page.title}</h2>
                      <p className="mt-1 text-sm text-text-muted">{page.subtitle}</p>
                      {presetLabel && (
                        <p className="mt-3 inline-flex flex-wrap items-center gap-2 rounded-full bg-accent-tint px-3 py-1 text-xs text-accent">
                          Pre-filled from “{presetLabel}” — adjust anything, or
                          <button type="button" className="font-semibold underline" onClick={() => go(SUMMARY)}>
                            skip to your profile
                          </button>
                        </p>
                      )}
                    </div>
                    {page.id === "move" && <BudgetFields answers={answers} city={catalog.city} onChange={update} />}
                    {page.id === "days" && (
                      <DestinationPicker
                        answers={answers}
                        destinations={catalog.destinations}
                        frequency={catalog.questions.find((q) => q.id === "frequency")}
                        labels={labels}
                        onChange={update}
                      />
                    )}
                    {catalog.questions
                      .filter((q) => q.page === page.id && q.id !== "frequency")
                      .map((q) => (
                        <OptionGroup key={q.id} question={q} answers={answers} labels={labels} onChange={update} />
                      ))}
                    {issues.length > 0 && (
                      <ul className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
                        {issues.map((i) => (
                          <li key={i}>{i}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                {/* ── Summary ── */}
                {step === SUMMARY && (
                  <div className="space-y-8">
                    <div>
                      <h2 className="text-2xl font-bold tracking-tight text-text">Here&apos;s what we heard</h2>
                      <p className="mt-1 text-sm text-text-muted">
                        Did we capture your lifestyle? Change anything before we match you.
                      </p>
                    </div>
                    {profileError && (
                      <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
                        {profileError}
                      </p>
                    )}
                    {!profile && !profileError && (
                      <div className="grid gap-6 md:grid-cols-2" aria-busy="true">
                        <div className="h-72 animate-pulse rounded-lg bg-chip" />
                        <div className="h-72 animate-pulse rounded-2xl bg-chip" />
                      </div>
                    )}
                    {profile && (
                      <div className="grid gap-6 md:grid-cols-2">
                        <div className="min-w-0 space-y-6">
                          <PersonaCard persona={profile.persona} />
                          {profile.weights.some((w) => w.value > 0) && (
                            <div>
                              <p className="mb-3 text-sm font-semibold text-text">How we&apos;ll weigh things</p>
                              <WeightBars weights={profile.weights} />
                            </div>
                          )}
                        </div>
                        <div className="min-w-0 space-y-4">
                          <p className="text-sm font-semibold text-text">You told us</p>
                          <ChoicesSummary
                            choices={profile.choices}
                            pageFor={pageForQuestion}
                            pageTitle={(id) => catalog.pages.find((p) => p.id === id)?.title ?? id}
                            onEdit={go}
                          />
                          {Object.values(profile.unscored).map((msg) => (
                            <p key={msg} className="rounded-xl bg-warn-bg px-3 py-2 text-xs text-warn">
                              {msg}
                            </p>
                          ))}
                        </div>
                      </div>
                    )}
                    {profile && !anyPreference && (
                      <p className="rounded-xl bg-warn-bg px-4 py-3 text-sm text-warn" role="status">
                        Tell us at least one thing you care about (evenings, weekends, neighbourhood…) so we can
                        match you.
                      </p>
                    )}
                    <div className="flex flex-col-reverse items-stretch gap-3 border-t border-line pt-6 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex flex-wrap justify-center gap-1 sm:justify-start">
                        <button
                          type="button"
                          onClick={() => go(steps[1])}
                          className="whitespace-nowrap rounded-full px-4 py-2.5 text-sm font-medium text-text-body hover:bg-chip"
                        >
                          ← Change answers
                        </button>
                        <button
                          type="button"
                          onClick={clearAll}
                          className="whitespace-nowrap rounded-full px-4 py-2.5 text-sm text-text-muted hover:bg-chip hover:text-gray-600"
                        >
                          Clear my answers
                        </button>
                      </div>
                      <button
                        type="button"
                        disabled={!profile || !anyPreference}
                        onClick={() => router.push("/lifestyle")}
                        className="group whitespace-nowrap rounded-md bg-accent px-6 py-3 text-sm font-semibold text-white transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        Yes, that&apos;s me — show my areas{" "}
                        <span className="inline-block transition-transform group-hover:translate-x-1">→</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* ── Back / Next for the question pages ── */}
              {page && (
                <div className="mt-10 flex items-center justify-between border-t border-line pt-6">
                  <button
                    type="button"
                    onClick={() => go(prevStep(steps, step))}
                    className="rounded-full px-4 py-2.5 text-sm font-medium text-text-body hover:bg-chip"
                  >
                    ← Back
                  </button>
                  <button
                    type="button"
                    disabled={issues.length > 0}
                    onClick={() => go(nextStep(steps, step))}
                    className="rounded-full bg-gray-900 px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-700 disabled:opacity-40"
                  >
                    {nextStep(steps, step) === SUMMARY ? "See my lifestyle →" : "Next →"}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
