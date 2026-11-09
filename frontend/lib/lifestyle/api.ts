// Lifestyle Match API client. Answers are only ever sent in POST bodies — never in
// URLs — so they can't end up in access logs or browser history (ADR-0012).

import { API_BASE } from "@/lib/api";
import type {
  Answers,
  Catalog,
  MatchResponse,
  ProfileResponse,
  RegionCollection,
  RegionListingsResponse,
} from "./types";
import { toRequestAnswers } from "./logic";

const BASE = `${API_BASE}/api/v1/lifestyle`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new Error("Can't reach WohnIQ right now. The server may be waking up — try again in a moment.");
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body?.detail === "string" ? body.detail : "";
    } catch {
      // not JSON
    }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
}

export function getCatalog(): Promise<Catalog> {
  return request<Catalog>("/catalog");
}

export function getProfile(answers: Answers, weights?: Record<string, number>): Promise<ProfileResponse> {
  return post<ProfileResponse>("/profile", { answers: toRequestAnswers(answers), weights: weights ?? null });
}

export function getMatches(
  answers: Answers,
  options: { weights?: Record<string, number>; excluded?: string[]; limit?: number } = {},
): Promise<MatchResponse> {
  return post<MatchResponse>("/match", {
    answers: toRequestAnswers(answers),
    weights: options.weights ?? null,
    excluded: options.excluded ?? [],
    limit: options.limit ?? 10,
  });
}

export function getRegionShapes(): Promise<RegionCollection> {
  return request<RegionCollection>("/regions.geojson");
}

/** WohnIQ listings located inside a region. Sends only region, budget and min rooms. */
export function getRegionListings(
  regionKey: string,
  budgetEur: number,
  limit = 12,
): Promise<RegionListingsResponse> {
  return post<RegionListingsResponse>("/listings", {
    region_key: regionKey,
    budget_eur: Math.round(budgetEur),
    limit,
  });
}
