// Berlin Neighborhoods API client. Requests carry only a category and optional weights
// (no personal data), so they are plain cacheable GETs.

import { API_BASE } from "@/lib/api";
import type { AreaCollection, AreaDetail, NeighborhoodCatalog, Ranking } from "./types";
import { OVERALL, weightsParam } from "./logic";

const BASE = `${API_BASE}/api/v1/neighborhoods`;

async function get<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`);
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

export function getNeighborhoodCatalog(): Promise<NeighborhoodCatalog> {
  return get<NeighborhoodCatalog>("/catalog");
}

export function getRanking(category: string, weights?: Record<string, number> | null): Promise<Ranking> {
  const params = new URLSearchParams({ category });
  if (category === OVERALL && weights) params.set("weights", weightsParam(weights));
  return get<Ranking>(`/ranking?${params}`);
}

export function getArea(key: string, weights?: Record<string, number> | null): Promise<AreaDetail> {
  const params = new URLSearchParams();
  if (weights) params.set("weights", weightsParam(weights));
  const q = params.toString();
  return get<AreaDetail>(`/areas/${encodeURIComponent(key)}${q ? `?${q}` : ""}`);
}

export function getAreaShapes(): Promise<AreaCollection> {
  return get<AreaCollection>("/regions.geojson");
}
