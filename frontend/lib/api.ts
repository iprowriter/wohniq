import type {
  AddressOut,
  ListingDetailResponse,
  ListingOut,
  MapStop,
  PlaceProfile,
  RightNowOut,
  SearchResponse,
} from "./types";
import type { RentIndex } from "./rent/index.ts";
import type { MapListing } from "./map/listingsMap";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Photo URLs are absolute (Pexels CDN), or backend-relative in offline demo mode
 * (`/demo-photos/...`, served by the API) — resolve those against the API origin. */
export function photoSrc(url: string): string {
  return url.startsWith("/") ? `${API_BASE}${url}` : url;
}

/** `maxWarmRent` overrides the budget parsed from the query ("raise budget to €X"). */
export async function search(
  query: string,
  limit = 6,
  maxWarmRent?: number,
): Promise<SearchResponse> {
  const body: Record<string, unknown> = { query, limit };
  if (maxWarmRent !== undefined) body.max_warm_rent = maxWarmRent;
  const res = await fetch(`${API_BASE}/api/v1/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`Search failed (${res.status})`);
  }
  return res.json();
}

export async function getRandomListings(n = 6): Promise<ListingOut[]> {
  const res = await fetch(`${API_BASE}/api/v1/listings/random?n=${n}`);
  if (!res.ok) {
    throw new Error(`Failed to load listings (${res.status})`);
  }
  return res.json();
}

export async function getListingDetail(id: string): Promise<ListingDetailResponse> {
  const res = await fetch(`${API_BASE}/api/v1/listings/${id}`);
  if (!res.ok) {
    throw new Error(`Listing not found (${res.status})`);
  }
  return res.json();
}

/** Every listing as a map point (homepage "See on the map"). */
export async function getMapListings(): Promise<MapListing[]> {
  const res = await fetch(`${API_BASE}/api/v1/listings/map`);
  if (!res.ok) {
    throw new Error(`Failed to load the map (${res.status})`);
  }
  return res.json();
}

async function getJson<T>(path: string, what: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`Couldn't load ${what} (${res.status})`);
  return res.json();
}

const qs = (params: Record<string, string | number>) =>
  new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString();

/** Everything the browser needs to run the rent check locally (table, checklist, texts). */
export const getRentIndex = () => getJson<RentIndex>("/api/v1/rent/index", "the rent index");

export const searchAddresses = (q: string, limit = 8) =>
  getJson<AddressOut[]>(`/api/v1/rent/addresses?${qs({ q, limit })}`, "addresses");

export const getAddress = (id: number, sizeM2?: number) =>
  getJson<AddressOut>(
    `/api/v1/rent/addresses/${id}${sizeM2 ? `?${qs({ size_m2: sizeM2 })}` : ""}`,
    "the address",
  );

export const getPlaceProfile = (lat: number, lng: number, locationClass?: string) =>
  getJson<PlaceProfile>(
    `/api/v1/place?${qs(locationClass ? { lat, lng, location_class: locationClass } : { lat, lng })}`,
    "the area profile",
  );

export const getListingAround = (id: string) =>
  getJson<PlaceProfile>(`/api/v1/listings/${id}/around`, "the area profile");

export const getRightNow = (lat: number, lng: number) =>
  getJson<RightNowOut>(`/api/v1/right-now?${qs({ lat, lng })}`, "departures");

export type Box = { south: number; west: number; north: number; east: number };

export const getStopsInView = (b: Box) =>
  getJson<MapStop[]>(`/api/v1/stops?${qs(b)}`, "stops");

export const getParksInView = (b: Box) =>
  getJson<GeoJSON.FeatureCollection>(`/api/v1/parks?${qs(b)}`, "parks");
