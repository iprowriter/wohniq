import type { ListingDetailResponse, ListingOut, SearchResponse } from "./types";
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
