// Mirrors the backend models in backend/app/routers/lifestyle.py and
// backend/lifestyle/questionnaire.py. Keep in sync if the API changes.

import type { ListingOut, RiskOut } from "../types";

export interface Answers {
  household?: string | null;
  budget_eur: number;
  size_m2: number;
  rooms: number;
  budget_strictness?: string | null;
  destination?: string | null;
  frequency?: string | null;
  max_commute_min: number;
  work_style?: string | null;
  getting_around?: string | null;
  evenings?: string | null;
  weekends: string[];
  neighbours?: string | null;
  safety?: string | null;
  extras: string[];
}

/** Questions whose answer is one option id (or none). */
export type SingleQuestionId =
  | "household"
  | "budget_strictness"
  | "frequency"
  | "work_style"
  | "getting_around"
  | "evenings"
  | "neighbours"
  | "safety";

/** Questions whose answer is a list of option ids. */
export type MultiQuestionId = "weekends" | "extras";

export interface OptionOut {
  id: string;
  label: string;
  hint?: string | null;
  sets: Record<string, number>;
}

export interface QuestionOut {
  id: string;
  page: string;
  prompt: string;
  help?: string | null;
  multi: boolean;
  max_choices: number;
  options: OptionOut[];
}

export interface PageOut {
  id: string;
  title: string;
  subtitle: string;
  questions: string[];
}

export interface PresetOut {
  id: string;
  label: string;
  blurb: string;
  answers: Answers;
}

export interface AttributeOut {
  id: string;
  label: string;
  description: string;
  kind: "area" | "personal";
  available: boolean;
}

export interface DestinationOut {
  id: string;
  name: string;
  short: string;
  kind: "university" | "hub";
}

export interface SourceOut {
  id: string;
  title: string;
  publisher: string;
  url?: string | null;
  licence?: string | null;
  data_year: string;
  used_for: string;
  caveat?: string | null;
}

export interface CityFigure {
  value: number;
  unit: string;
  source_id: string;
  year: string;
  note?: string | null;
}

export interface Catalog {
  pages: PageOut[];
  questions: QuestionOut[];
  presets: PresetOut[];
  attributes: AttributeOut[];
  destinations: DestinationOut[];
  sources: SourceOut[];
  city: Record<string, CityFigure>;
  region_count: number;
  privacy: string;
}

export interface WeightOut {
  attribute: string;
  label: string;
  value: number;
  reasons: string[];
  overridden: boolean;
}

export interface Persona {
  id: string;
  title: string;
  emoji: string;
  tagline: string;
  priorities: string[];
  summary: string;
  disclaimer: string;
}

export interface Choice {
  question: string;
  answer: string;
}

export interface ProfileResponse {
  persona: Persona;
  weights: WeightOut[];
  choices: Choice[];
  unscored: Record<string, string>;
}

export interface Evidence {
  attribute: string;
  label: string;
  text: string;
  source_id: string;
  score: number;
  weight: number;
}

export interface Factor {
  attribute: string;
  label: string;
  weight: number;
  score: number;
  contribution: number;
  raw: number;
  unit: string;
  berlin?: number | null;
  source_id: string;
  year: string;
}

export interface RegionCommute {
  destination: string;
  minutes: number;
  changes?: number | null;
  estimated: boolean;
}

export interface RegionResult {
  rank: number;
  key: string;
  name: string;
  district: string;
  score: number;
  fits_budget: boolean;
  warm_rent_eur: number;
  within_commute: boolean | null;
  commute: RegionCommute | null;
  centroid: [number, number] | null;
  population: number;
  headline: string;
  reasons: Evidence[];
  caveats: string[]; // trade-offs of this area for you
  notes: string[]; // caveats about the data itself
  evidence: Evidence[];
  factors: Factor[];
}

export interface RegionScore {
  key: string;
  rank: number;
  score: number;
  fits_budget: boolean;
  within_commute: boolean | null;
}

export interface MatchResponse {
  persona: Persona;
  weights: WeightOut[];
  results: RegionResult[];
  scores: RegionScore[];
  unscored: Record<string, string>;
  excluded: string[];
  total_regions: number;
}

// --- Listings hand-off (POST /lifestyle/listings) -------------------------------------


export interface RegionListing {
  listing: ListingOut;
  fits_budget: boolean | null;
  risk?: RiskOut | null;
}

export interface RegionListingsResponse {
  region_key: string;
  region_name: string;
  count: number;
  listings: RegionListing[];
}

// --- Region outlines (GET /lifestyle/regions.geojson) --------------------------------

export interface RegionFeature {
  type: "Feature";
  properties: { key: string; name: string; district: string };
  geometry: { type: "MultiPolygon"; coordinates: number[][][][] };
}

export interface RegionCollection {
  type: "FeatureCollection";
  features: RegionFeature[];
}
