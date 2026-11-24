"use client";

/**
 * The offline base map as a react-leaflet child (ADR-0019). Replaces every online
 * tile layer: draws the local berlin.pmtiles in Berlin Ink colours with protomaps-leaflet.
 *
 * `onStatus(true | false)` reports whether the map file is reachable, so a map can keep its
 * existing fallback (area outlines on a plain background) for a server without the build.
 */

import { useEffect } from "react";
import { useMap } from "react-leaflet";
import type L from "leaflet";
import {
  BASEMAP_ATTRIBUTION,
  BASEMAP_MAX_DATA_ZOOM,
  BERLIN_INK_FLAVOR,
  basemapAvailable,
  basemapUrl,
} from "@/lib/map/basemap";

type Props = {
  onStatus?: (available: boolean) => void;
  /** Extra attribution after the base map's (e.g. "areas: LOR 2021"). */
  attributionSuffix?: string;
};

export function OfflineBasemap({ onStatus, attributionSuffix }: Props) {
  const map = useMap();

  useEffect(() => {
    let layer: L.Layer | null = null;
    let cancelled = false;
    const url = basemapUrl();

    (async () => {
      const available = await basemapAvailable(url);
      if (cancelled) return;
      onStatus?.(available);
      if (!available) return;
      // protomaps-leaflet touches `window` on import: load it only in the browser.
      const { leafletLayer, paintRules, labelRules } = await import("protomaps-leaflet");
      if (cancelled) return;
      const flavor = BERLIN_INK_FLAVOR as unknown as Parameters<typeof paintRules>[0];
      layer = leafletLayer({
        url,
        paintRules: paintRules(flavor),
        labelRules: labelRules(flavor, "de"),
        backgroundColor: BERLIN_INK_FLAVOR.background,
        maxDataZoom: BASEMAP_MAX_DATA_ZOOM,
        attribution: attributionSuffix
          ? `${BASEMAP_ATTRIBUTION} · ${attributionSuffix}`
          : BASEMAP_ATTRIBUTION,
      }) as unknown as L.Layer;
      layer.addTo(map);
      // Keep overlays (outlines, markers) above the base map.
      (layer as L.GridLayer).bringToBack?.();
    })();

    return () => {
      cancelled = true;
      if (layer) map.removeLayer(layer);
    };
    // The map instance and URL are fixed for the component's life.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);

  return null;
}
