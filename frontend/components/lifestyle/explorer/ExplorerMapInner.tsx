"use client";

import { useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import { GeoJSON, MapContainer, Marker, Tooltip, ZoomControl, useMap } from "react-leaflet";
import type { Layer, PathOptions } from "leaflet";
import { OfflineBasemap } from "@/components/map/OfflineBasemap";
import { EXCLUDED_COLOR, scoreColor } from "@/lib/lifestyle/results";
import type { ExplorerMapProps } from "./ExplorerMap";

const BERLIN: L.LatLngBoundsExpression = [
  [52.34, 13.09],
  [52.68, 13.76],
];

function rankIcon(rank: number, active: boolean): L.DivIcon {
  return L.divIcon({
    className: "wq-marker",
    html: `<span class="lm-rank${active ? " lm-rank--active" : ""}">${rank}</span>`,
    iconSize: [0, 0],
  });
}

const DEST_ICON = L.divIcon({
  className: "wq-marker",
  html: `<span class="lm-dest" aria-hidden="true"></span>`,
  iconSize: [0, 0],
});

/** Frames the top 10 (or all of Berlin) whenever the ranking or the mode changes. */
function Frame({ points, mode, ready }: { points: [number, number][]; mode: "top" | "all"; ready: boolean }) {
  const map = useMap();
  const key = `${mode}|${points.map((p) => p.join(",")).join(";")}`;
  useEffect(() => {
    if (!ready) return;
    if (mode === "all" || points.length < 2) map.fitBounds(BERLIN, { padding: [8, 8] });
    else map.fitBounds(L.latLngBounds(points), { padding: [36, 36], maxZoom: 13 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, ready, map]);
  return null;
}

export default function ExplorerMapInner({
  shapes,
  scores,
  excluded,
  top,
  mode,
  hovered,
  selected,
  onHover,
  onSelect,
  destination,
  height = 420,
}: ExplorerMapProps) {
  const layers = useRef(new Map<string, L.Path>());
  const styleFor = useMemo(
    () =>
      (key: string): PathOptions => {
        const isExcluded = excluded.has(key);
        const s = scores.get(key);
        const emphasised = key === hovered || key === selected;
        return {
          color: emphasised ? "#0D1321" : "#FFFFFF",
          weight: emphasised ? 2.5 : 0.8,
          fillColor: isExcluded ? EXCLUDED_COLOR : scoreColor(s ?? null),
          fillOpacity: isExcluded ? 0.5 : s == null ? 0.25 : 0.72,
        };
      },
    [scores, excluded, hovered, selected],
  );

  // Restyle in place (GeoJSON data stays the same object).
  useEffect(() => {
    for (const [key, layer] of layers.current) {
      layer.setStyle(styleFor(key));
      if (key === hovered || key === selected) layer.bringToFront();
    }
  }, [styleFor, hovered, selected]);

  const points = top.filter((r) => r.centroid).map((r) => r.centroid as [number, number]);

  return (
    <MapContainer
      bounds={BERLIN}
      zoomControl={false}
      scrollWheelZoom={false}
      style={{ height, width: "100%" }}
      data-testid="explorer-map"
    >
      <OfflineBasemap attributionSuffix="areas: LOR 2021" />
      <ZoomControl position="bottomright" />
      <Frame points={points} mode={mode} ready={top.length > 0} />
      {shapes && (
        <GeoJSON
          data={shapes as unknown as GeoJSON.FeatureCollection}
          style={(f) => styleFor(String(f?.properties?.key))}
          onEachFeature={(f, layer: Layer) => {
            const key = String(f.properties.key);
            layers.current.set(key, layer as L.Path);
            layer.on({
              mouseover: () => onHover(key),
              mouseout: () => onHover(null),
              click: () => onSelect(key),
            });
            (layer as L.Path).bindTooltip(String(f.properties.name), { sticky: true, direction: "top" });
          }}
        />
      )}
      {top.map((r) =>
        r.centroid ? (
          <Marker
            key={r.key}
            position={r.centroid}
            icon={rankIcon(r.rank, r.key === selected || r.key === hovered)}
            zIndexOffset={r.key === selected ? 1000 : 500 - r.rank}
            eventHandlers={{ click: () => onSelect(r.key), mouseover: () => onHover(r.key), mouseout: () => onHover(null) }}
            title={`${r.rank}. ${r.name}: ${Math.round(r.score)} match`}
          />
        ) : null,
      )}
      {destination && destination.lat != null && destination.lng != null && (
        <Marker position={[destination.lat, destination.lng]} icon={DEST_ICON} keyboard={false}>
          <Tooltip direction="right" offset={[10, 0]} permanent className="lm-dest-label">
            {destination.short}
          </Tooltip>
        </Marker>
      )}
    </MapContainer>
  );
}
