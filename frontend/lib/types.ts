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
  changes?: number | null; // null for offline estimates (minutes only)
  walk_minutes?: number | null;
  estimated?: boolean; // offline estimate, not a live BVG/VBB journey
  source?: "live" | "network" | "distance"; // network = routed over the VBB peak timetable
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
  commute_note?: string | null;
}

// Detail page types
export interface PoiOut {
  category: string;
  name: string;
  lat: number;
  lng: number;
}

export interface ListingDetailOut extends ListingOut {
  description: string;
  lat: number;
  lng: number;
  floor?: number | null;
  total_floors?: number | null;
  anmeldung_possible: boolean;
}

export interface NeighborhoodDetailOut {
  summary?: string | null;
  counts: Record<string, number>;
  pois: PoiOut[];
  radius_m?: number; // amenity search radius in metres
}

export interface ListingDetailResponse {
  listing: ListingDetailOut;
  risk?: RiskOut | null;
  neighborhood?: NeighborhoodDetailOut | null;
}
