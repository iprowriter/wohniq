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
  highlight?: string; // short phrase used in the summary
}

/** Where a result lies relative to the areas the user asked for. */
export interface AreaMatchOut {
  status: "in_area" | "nearby" | "outside";
  area: string; // requested area it's in, or the nearest one
  distance_km?: number | null; // from that area's centre (nearby/outside only)
  label: string; // "In Mitte", "Near Mitte · 2.1 km"
}

export type NoticeKind =
  | "budget_too_low"
  | "budget_too_low_in_some_areas"
  | "nearby_results"
  | "no_listings_in_area"
  | "no_results";

/** Why results are missing or come from elsewhere, with a concrete way forward. */
export interface SearchNotice {
  kind: NoticeKind;
  title: string;
  message: string;
  suggested_budget?: number | null; // minimum warm rent that shows at least one flat
  comfortable_budget?: number | null; // shows a few flats to choose from
  options_at_suggested?: number | null;
  options_at_comfortable?: number | null;
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

/** Listing matched to its nearest real address (ADR-0016). Street only, no number. */
export interface ListingLocationOut {
  street: string;
  postcode: string;
  district: string;
  planning_area?: string | null;
  district_region?: string | null;
  location_class: "simple" | "medium" | "good";
  east: boolean;
  rail_stop?: string | null;
  rail_modes: string[];
  rail_walk_minutes?: number | null;
  lat?: number | null;
  lng?: number | null;
  address_id?: number | null; // matched address: prefill for the rent check
}

export type RentVerdict =
  | "within_limit"
  | "above_limit"
  | "below_index"
  | "new_build"
  | "not_covered"
  | "unknown";

/** Rent check against the Mietspiegel 2026 (ADR-0017); an estimate for listings. */
export interface RentOut {
  verdict: RentVerdict;
  verdict_text: string;
  explanation: string;
  estimate: boolean;
  covered: boolean;
  asked?: number | null;
  low?: number | null;
  mean?: number | null;
  high?: number | null;
  limit?: number | null;
  over_per_m2?: number | null;
  over_per_month?: number | null;
  row?: number | null;
  period?: string | null;
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
  year_built?: number | null;
  location?: ListingLocationOut | null;
  rent?: RentOut | null;
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
  area_match?: AreaMatchOut | null;
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
  areas?: string[]; // Berlin areas to live in (hard filter)
  excluded_areas?: string[];
  notes?: string | null;
}

export interface SearchResponse {
  criteria: SearchCriteria;
  results: SearchResultItem[];
  commute_note?: string | null;
  notices?: SearchNotice[];
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
  location?: ListingLocationOut | null;
  rent?: RentOut | null;
}

// --- Berlin data (rent check, Around this flat, Right now) ---

export interface AddressOut {
  id: number;
  label: string;
  street: string;
  house_number: string;
  postcode: string;
  district: string;
  location_class: "simple" | "medium" | "good";
  east: boolean;
  lat: number;
  lng: number;
  planning_area?: string | null;
  district_region?: string | null;
  location_class_share_300m?: number;
  mean_by_period?: { period: string; label: string; mean: number; row: number }[];
}

export interface Measure {
  key: string;
  label: string;
  source: string;
  headline: string;
  position: number;
  comparison: string;
  detail: string;
  value?: number | null;
}

export interface PlaceProfile {
  lat: number;
  lng: number;
  planning_area?: string | null;
  district_region?: string | null;
  district?: string | null;
  measures: Measure[];
}

export interface StopOut {
  id: string;
  name: string;
  modes: string[];
  distance_m: number;
  walk_minutes: number;
  lat: number;
  lng: number;
}

export interface DepartureOut {
  line: string;
  mode: string;
  direction: string;
  stop: string;
  when?: string | null;
  planned?: string | null;
  delay_minutes?: number | null;
  platform?: string | null;
  cancelled: boolean;
}

export interface RightNowOut {
  status: "live" | "offline";
  note: string;
  stops: StopOut[];
  departures: DepartureOut[];
  fetched_at?: string | null;
}

export interface MapStop {
  id: string;
  name: string;
  modes: string[];
  lat: number;
  lng: number;
}

// --- Similar apartments (T9.7) ---

export interface SimilarItem {
  listing: ListingOut;
  risk?: RiskOut | null;
  score: number;
  distance_km: number;
  reasons: string[];
}

export interface SimilarResponse {
  within_limit_first: boolean;
  items: SimilarItem[];
}
