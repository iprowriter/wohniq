import type { ListingDetailResponse, ListingOut, SearchResponse } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Photo URLs are absolute (Pexels CDN), or backend-relative in offline demo mode
 * (`/demo-photos/...`, served by the API) — resolve those against the API origin. */
export function photoSrc(url: string): string {
  return url.startsWith("/") ? `${API_BASE}${url}` : url;
}

export async function search(query: string, limit = 6): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE}/api/v1/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit }),
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
