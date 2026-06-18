// Mirrors the backend response models in app/routers/search.py.
// Keep in sync if the API changes.

export interface PhotoOut {
  url: string;
  room_type: string;
  attribution?: string | null;
}

export interface FactorOut {
  name: string;
  score: number;
  weight: number;
  detail: string;
}

export interface CommuteOut {
  minutes: number;
  changes: number;
  walk_minutes?: number | null;
}

export interface NeighborhoodOut {
  summary?: string | null;
  counts: Record<string, number>;
}

export interface RiskSignalOut {
  name: string;
  source: string;
  evidence: string;
  severity: number;
}

export type RiskBand = "low" | "caution" | "high";

export interface RiskOut {
  band: RiskBand;
  score: number;
  signals: RiskSignalOut[];
}

export interface ListingOut {
  id: string;
  title: string;
  address: string;
  kiez: string;
  district?: string | null;
  rooms: number;
  size_m2: number;
  kaltmiete_eur: number;
  nebenkosten_eur: number;
  warmmiete_eur: number;
  deposit_eur?: number | null;
  furnished: boolean;
  available_from?: string | null;
  photos: PhotoOut[];
}

export interface Explanation {
  summary: string;
  reasons: string[];
  caveats: string[];
}

export interface SearchResultItem {
  listing: ListingOut;
  score: number;
  factors: FactorOut[];
  explanation: Explanation;
  commute?: CommuteOut | null;
  neighborhood?: NeighborhoodOut | null;
  risk?: RiskOut | null;
}

export interface SearchCriteria {
  max_warm_rent?: number | null;
  min_rooms?: number | null;
  min_size_m2?: number | null;
  work_location?: string | null;
  transport_priority: boolean;
  quiet_priority: boolean;
  desired_amenities: string[];
  furnished?: boolean | null;
  notes?: string | null;
}

export interface SearchResponse {
  criteria: SearchCriteria;
  results: SearchResultItem[];
}
