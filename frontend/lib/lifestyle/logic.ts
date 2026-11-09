// Pure questionnaire logic for Lifestyle Match: no React, no fetch, no DOM.
// Everything here is unit-tested with Node's built-in test runner (tests/lifestyle-logic.test.ts).
//
// Privacy (ADR-0012): answers live only in memory and in *sessionStorage* for the
// current tab (cleared when it closes). Never localStorage, cookies or the URL.

import type {
  Answers,
  Catalog,
  CityFigure,
  DestinationOut,
  MultiQuestionId,
  OptionOut,
  PresetOut,
  QuestionOut,
  SingleQuestionId,
} from "./types";

// --- Steps ---------------------------------------------------------------------------

export const WELCOME = "welcome";
export const SUMMARY = "summary";

/** welcome → one step per catalog page → summary */
export function stepsFor(catalog: Pick<Catalog, "pages">): string[] {
  return [WELCOME, ...catalog.pages.map((p) => p.id), SUMMARY];
}

export function stepIndex(steps: string[], step: string): number {
  const i = steps.indexOf(step);
  return i < 0 ? 0 : i;
}

export function nextStep(steps: string[], step: string): string {
  return steps[Math.min(stepIndex(steps, step) + 1, steps.length - 1)];
}

export function prevStep(steps: string[], step: string): string {
  return steps[Math.max(stepIndex(steps, step) - 1, 0)];
}

/** 0 on the welcome screen, 1 on the summary. */
export function progress(steps: string[], step: string): number {
  return steps.length <= 1 ? 1 : stepIndex(steps, step) / (steps.length - 1);
}

// --- Bounds (mirror backend Answers validation) ---------------------------------------

export const LIMITS = {
  budget: { min: 200, max: 10_000, sliderMin: 300, sliderMax: 4000, step: 10 },
  size: { min: 10, max: 250, sliderMin: 15, sliderMax: 160, step: 1 },
  rooms: { min: 1, max: 8, step: 0.5 },
  commute: { min: 10, max: 120, sliderMax: 90, step: 5 },
} as const;

export const SINGLE_QUESTIONS: SingleQuestionId[] = [
  "household",
  "budget_strictness",
  "frequency",
  "work_style",
  "getting_around",
  "evenings",
  "neighbours",
  "safety",
];
export const MULTI_QUESTIONS: MultiQuestionId[] = ["weekends", "extras"];

export function clampNumber(value: number, min: number, max: number, step = 1): number {
  if (!Number.isFinite(value)) return min;
  const stepped = Math.round(value / step) * step;
  return Math.min(max, Math.max(min, Number(stepped.toFixed(2))));
}

// --- Answers ------------------------------------------------------------------------

export function defaultAnswers(): Answers {
  return {
    household: null,
    budget_eur: 1200,
    size_m2: 50,
    rooms: 2,
    budget_strictness: null,
    destination: null,
    frequency: null,
    max_commute_min: 45,
    work_style: null,
    getting_around: null,
    evenings: null,
    weekends: [],
    neighbours: null,
    safety: null,
    extras: [],
  };
}

/** Fresh copy of a preset's answers (the user can change every one of them). */
export function fromPreset(preset: PresetOut): Answers {
  return normalizeAnswers(preset.answers) ?? defaultAnswers();
}

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === "object" && x !== null && !Array.isArray(x);
}

/**
 * Coerce untrusted data (e.g. restored from sessionStorage) into valid Answers.
 * Unknown keys are dropped; out-of-range numbers are clamped; returns null if the
 * required numbers are missing.
 */
export function normalizeAnswers(raw: unknown): Answers | null {
  if (!isRecord(raw)) return null;
  const num = (k: string) => (typeof raw[k] === "number" ? (raw[k] as number) : NaN);
  if (!Number.isFinite(num("budget_eur")) || !Number.isFinite(num("size_m2"))) return null;
  const out = defaultAnswers();
  out.budget_eur = clampNumber(num("budget_eur"), LIMITS.budget.min, LIMITS.budget.max);
  out.size_m2 = clampNumber(num("size_m2"), LIMITS.size.min, LIMITS.size.max);
  if (Number.isFinite(num("rooms"))) {
    out.rooms = clampNumber(num("rooms"), LIMITS.rooms.min, LIMITS.rooms.max, LIMITS.rooms.step);
  }
  if (Number.isFinite(num("max_commute_min"))) {
    out.max_commute_min = clampNumber(num("max_commute_min"), LIMITS.commute.min, LIMITS.commute.max);
  }
  const str = (k: string) => (typeof raw[k] === "string" ? (raw[k] as string) : null);
  for (const q of SINGLE_QUESTIONS) out[q] = str(q);
  out.destination = str("destination");
  for (const q of MULTI_QUESTIONS) {
    const v = raw[q];
    out[q] = Array.isArray(v) ? Array.from(new Set(v.filter((x) => typeof x === "string"))) : [];
  }
  return out;
}

/** Pick an option of a single-choice question; picking the chosen one clears it. */
export function chooseSingle(a: Answers, q: SingleQuestionId, optionId: string): Answers {
  return { ...a, [q]: a[q] === optionId ? null : optionId };
}

/** Toggle an option of a multi-choice question, never exceeding `max` choices. */
export function toggleMulti(a: Answers, q: MultiQuestionId, optionId: string, max: number): Answers {
  const current = a[q];
  if (current.includes(optionId)) return { ...a, [q]: current.filter((x) => x !== optionId) };
  if (current.length >= max) return a; // full: the UI disables the remaining options
  return { ...a, [q]: [...current, optionId] };
}

export function isChosen(a: Answers, q: QuestionOut, optionId: string): boolean {
  if (q.multi) return (a[q.id as MultiQuestionId] ?? []).includes(optionId);
  return a[q.id as SingleQuestionId] === optionId;
}

/** Choosing "no destination" also clears how often you'd go there. */
export function setDestination(a: Answers, destination: string | null): Answers {
  if (!destination) return { ...a, destination: null, frequency: null };
  return { ...a, destination, frequency: a.frequency ?? "daily" };
}

/** Blocking problems for a page (only bounded numbers can be invalid). */
export function pageIssues(pageId: string, a: Answers): string[] {
  const issues: string[] = [];
  if (pageId === "move") {
    if (a.budget_eur < LIMITS.budget.min || a.budget_eur > LIMITS.budget.max)
      issues.push(`Budget must be between €${LIMITS.budget.min} and €${LIMITS.budget.max.toLocaleString("en")}.`);
    if (a.size_m2 < LIMITS.size.min || a.size_m2 > LIMITS.size.max)
      issues.push(`Size must be between ${LIMITS.size.min} and ${LIMITS.size.max} m².`);
  }
  if (pageId === "days" && (a.max_commute_min < LIMITS.commute.min || a.max_commute_min > LIMITS.commute.max))
    issues.push(`Maximum commute must be between ${LIMITS.commute.min} and ${LIMITS.commute.max} minutes.`);
  return issues;
}

/** Does any answer set a lifestyle weight? (Matching needs at least one.) */
export function hasAnyPreference(a: Answers, catalog: Pick<Catalog, "questions">): boolean {
  return catalog.questions.some((q) =>
    q.options.some(
      (o) =>
        isChosen(a, q, o.id) &&
        Object.values(o.sets).some((v) => v > 0) &&
        (q.id !== "frequency" || Boolean(a.destination)),
    ),
  );
}

/** The exact body we send: the fixed fields only, nothing else. */
export function toRequestAnswers(a: Answers): Answers {
  return {
    household: a.household ?? null,
    budget_eur: Math.round(a.budget_eur),
    size_m2: Math.round(a.size_m2),
    rooms: a.rooms,
    budget_strictness: a.budget_strictness ?? null,
    destination: a.destination ?? null,
    frequency: a.destination ? (a.frequency ?? null) : null,
    max_commute_min: Math.round(a.max_commute_min),
    work_style: a.work_style ?? null,
    getting_around: a.getting_around ?? null,
    evenings: a.evenings ?? null,
    weekends: [...a.weekends],
    neighbours: a.neighbours ?? null,
    safety: a.safety ?? null,
    extras: [...a.extras],
  };
}

// --- Presentation helpers -------------------------------------------------------------

/** "Sets Nightlife to 5/5" — shown as a tooltip so the mapping is transparent. */
export function optionEffect(option: OptionOut, labels: Record<string, string>): string {
  const parts = Object.entries(option.sets)
    .filter(([, v]) => v > 0)
    .map(([attr, v]) => `${labels[attr] ?? attr} ${v}/5`);
  return parts.length ? `Sets importance: ${parts.join(", ")}` : "Doesn't change any weights";
}

export function groupDestinations(destinations: DestinationOut[]): {
  university: DestinationOut[];
  hub: DestinationOut[];
} {
  return {
    university: destinations.filter((d) => d.kind === "university"),
    hub: destinations.filter((d) => d.kind === "hub"),
  };
}

/** Typical warm rent in Berlin for a flat size: median asking rent + running costs. */
export function typicalBerlinWarmRent(city: Record<string, CityFigure>, sizeM2: number): number | null {
  const median = city.asking_rent_median?.value;
  const cold = city.operating_costs_cold?.value;
  const warm = city.operating_costs_warm?.value;
  if (median == null || cold == null || warm == null) return null;
  return Math.round((median + cold + warm) * sizeM2);
}

export interface BudgetReference {
  label: string;
  value: number;
}

/** Reference points shown next to the budget input, all from cited sources. */
export function budgetReferences(city: Record<string, CityFigure>, sizeM2: number): BudgetReference[] {
  const refs: BudgetReference[] = [];
  if (city.bafoeg_housing_allowance)
    refs.push({ label: "BAföG housing allowance", value: city.bafoeg_housing_allowance.value });
  if (city.student_room_berlin) refs.push({ label: "Avg. Berlin WG room", value: city.student_room_berlin.value });
  const typical = typicalBerlinWarmRent(city, sizeM2);
  if (typical != null) refs.push({ label: `Typical ${sizeM2} m² flat in Berlin`, value: typical });
  return refs;
}

export function euro(n: number): string {
  return `€${Math.round(n).toLocaleString("en-US")}`;
}

// --- Session storage (current tab only) ------------------------------------------------

export const STORAGE_KEY = "wohniq_lifestyle";
export const STORAGE_VERSION = 1;

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface SavedState {
  answers: Answers;
  step: string;
  presetId: string | null;
}

export function saveState(storage: StorageLike, state: SavedState): void {
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify({ v: STORAGE_VERSION, ...state }));
  } catch {
    // storage full or disabled: the questionnaire still works in memory
  }
}

export function loadState(storage: StorageLike): SavedState | null {
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data: unknown = JSON.parse(raw);
    if (!isRecord(data) || data.v !== STORAGE_VERSION) return null;
    const answers = normalizeAnswers(data.answers);
    if (!answers) return null;
    return {
      answers,
      step: typeof data.step === "string" ? data.step : WELCOME,
      presetId: typeof data.presetId === "string" ? data.presetId : null,
    };
  } catch {
    return null;
  }
}

/** Forget everything Lifestyle Match keeps in this tab (answers and adjustments). */
export function clearState(storage: StorageLike): void {
  // "wohniq_lifestyle_results" = results.ts RESULTS_KEY (a test keeps them in sync).
  for (const key of [STORAGE_KEY, "wohniq_lifestyle_results"]) {
    try {
      storage.removeItem(key);
    } catch {
      // nothing to clear
    }
  }
}
