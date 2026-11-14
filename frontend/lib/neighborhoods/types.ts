// Berlin Neighborhoods API shapes (backend: app/routers/neighborhoods.py).
// tests/neighborhoods.test.ts checks these against real responses exported by the backend.

export type Tier = "best" | "middle" | "worst";

export interface MetricInfo {
  id: string;
  label: string;
  unit: string;
  higher_is_better: boolean;
  weight: number;
  description: string;
  level: "region" | "district";
  available: boolean;
  requires: string | null;
  berlin: number | null;
  berlin_text: string | null;
  berlin_method: string | null;
  city_text: string | null; // Berlin-wide figure for a metric not published per area
  city_note: string | null;
  city_source_id: string | null;
}

export interface CategoryInfo {
  id: string;
  label: string;
  emoji: string;
  question: string;
  best_label: string;
  worst_label: string;
  default_weight: number;
  caveat: string;
  metrics: MetricInfo[];
}

export interface SourceInfo {
  id: string;
  title: string;
  publisher: string;
  url: string | null;
  licence: string | null;
  data_year: string;
  used_for: string;
  caveat: string | null;
}

export interface NeighborhoodCatalog {
  overall: { id: string; label: string; description: string };
  categories: CategoryInfo[];
  sources: SourceInfo[];
  area_count: number;
  max_weight: number;
  districts: string[];
}

export interface Headline {
  metric: string;
  label: string;
  raw: number;
  text: string;
}

export interface RankedArea {
  key: string;
  name: string;
  district: string;
  area_group: string;
  rank: number;
  score: number;
  tier: Tier;
  centroid: [number, number];
  headline: Headline | null;
}

export interface Ranking {
  category: string;
  label: string;
  best_label: string | null;
  worst_label: string | null;
  weights: Record<string, number> | null;
  total: number;
  areas: RankedArea[];
}

export interface HighlightOut {
  category: string;
  label: string;
  rank: number;
  text: string;
  source_id: string;
}

export interface MetricValue {
  id: string;
  label: string;
  unit: string;
  raw: number;
  text: string;
  berlin_text: string;
  score: number;
  weight: number;
  higher_is_better: boolean;
  level: "region" | "district";
  source_id: string;
  year: string;
  method: string;
  count: number | null;
  shares: Record<string, number> | null;
}

export interface CategoryDetail {
  id: string;
  label: string;
  emoji: string;
  score: number;
  rank: number;
  tier: Tier;
  tier_label: string | null;
  metrics: MetricValue[];
}

export interface AreaDetail {
  key: string;
  name: string;
  district: string;
  area_group: string;
  population: number;
  area_km2: number;
  centroid: [number, number];
  rent_range: [number, number] | null;
  overall: CategoryDetail;
  summary: string;
  strengths: HighlightOut[];
  watch_outs: HighlightOut[];
  categories: CategoryDetail[];
  total: number;
}

export interface AreaFeature {
  type: "Feature";
  properties: { key: string; name: string; district: string };
  geometry: { type: "Polygon" | "MultiPolygon"; coordinates: unknown };
}

export interface AreaCollection {
  type: "FeatureCollection";
  features: AreaFeature[];
}
