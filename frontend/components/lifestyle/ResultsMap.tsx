"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import { GeoJSON, MapContainer, Marker, TileLayer, Tooltip, useMap } from "react-leaflet";
import type { RegionCollection, RegionResult, RegionScore } from "@/lib/lifestyle/types";
import { EXCLUDED_COLOR, SCORE_BANDS, scoreColor } from "@/lib/lifestyle/results";

const TILE_TIMEOUT_MS = 4000; // no tile by then → show outlines on a plain background

interface Props {
  shapes: RegionCollection;
  scores: RegionScore[];
  top: RegionResult[];
  selected: string | null;
  onSelect: (key: string) => void;
}

function styleFor(key: string, current: Record<string, RegionScore>, sel: string | null): L.PathOptions {
  const s = current[key];
  const active = key === sel;
  return {
    color: active ? "#111827" : "#ffffff",
    weight: active ? 3 : 0.8,
    fillColor: s ? scoreColor(s.score) : EXCLUDED_COLOR,
    fillOpacity: s ? 0.78 : 0.35,
  };
}

/**
 * Frame the view: the top results (where the user will look first), or all of Berlin.
 * invalidateSize first — the container only gets its final size after the map mounts.
 */
function FitView({ shapes, top, showAll }: { shapes: RegionCollection; top: RegionResult[]; showAll: boolean }) {
  const map = useMap();
  const topKey = top.map((r) => r.key).join(",");
  useEffect(() => {
    map.invalidateSize();
    const points = top.filter((r) => r.centroid).map((r) => r.centroid as [number, number]);
    const bounds =
      showAll || points.length < 2
        ? L.geoJSON(shapes as GeoJSON.FeatureCollection).getBounds()
        : L.latLngBounds(points).pad(0.35);
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [12, 12], maxZoom: 13 });
    // Re-frame when the set of top results changes, not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, shapes, topKey, showAll]);
  return null;
}

function rankIcon(rank: number, active: boolean) {
  const size = active ? 34 : 26;
  return L.divIcon({
    className: "",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `<div style="width:${size}px;height:${size}px;border-radius:9999px;display:flex;align-items:center;justify-content:center;font:700 ${
      active ? 14 : 12
    }px system-ui;color:#fff;background:${active ? "#111827" : "#4f46e5"};border:2px solid #fff;box-shadow:0 4px 10px rgba(17,24,39,.3)">${rank}</div>`,
  });
}

export function ResultsMap({ shapes, scores, top, selected, onSelect }: Props) {
  const [tilesOk, setTilesOk] = useState<boolean | null>(null);
  const [showAll, setShowAll] = useState(false);
  const anyTile = useRef(false);
  const layer = useRef<L.GeoJSON | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const byKey = useMemo(() => Object.fromEntries(scores.map((s) => [s.key, s])), [scores]);
  const byKeyRef = useRef(byKey);
  byKeyRef.current = byKey;


  useEffect(() => {
    const t = setTimeout(() => !anyTile.current && setTilesOk(false), TILE_TIMEOUT_MS);
    return () => clearTimeout(t);
  }, []);

  // Restyle in place when scores or the selection change (GeoJSON doesn't re-style on props).
  useEffect(() => {
    layer.current?.setStyle((feature) => styleFor(feature?.properties?.key as string, byKey, selected));
    if (selected) {
      layer.current?.eachLayer((l) => {
        const f = (l as L.Polygon).feature as GeoJSON.Feature | undefined;
        if (f?.properties?.key === selected) (l as L.Polygon).bringToFront();
      });
    }
  }, [byKey, selected]);

  const offline = tilesOk === false;
  return (
    <div className={`relative ${offline ? "wohniq-map-offline" : ""}`}>
      <MapContainer
        center={[52.52, 13.405]}
        zoom={10}
        style={{ height: "100%", minHeight: 360, width: "100%", borderRadius: 16 }}
        scrollWheelZoom={false}
        zoomSnap={0.1}
        attributionControl
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · areas: LOR 2021'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          opacity={0.45}
          eventHandlers={{
            tileload: () => {
              anyTile.current = true;
              setTilesOk(true);
            },
          }}
        />
        <GeoJSON
          ref={layer}
          data={shapes as GeoJSON.FeatureCollection}
          style={(feature) => styleFor(feature?.properties?.key as string, byKeyRef.current, selected)}
          onEachFeature={(feature, l) => {
            const key = feature.properties?.key as string;
            l.bindTooltip(() => {
              const s = byKeyRef.current[key];
              return `<strong>${feature.properties?.name}</strong><br/>${
                s ? `#${s.rank} · score ${s.score}` : "removed"
              }`;
            }, { sticky: true });
            l.on("click", () => onSelectRef.current(key));
          }}
        />
        {top
          .filter((r) => r.centroid)
          .map((r) => (
            <Marker
              key={r.key}
              position={r.centroid as [number, number]}
              icon={rankIcon(r.rank, r.key === selected)}
              zIndexOffset={r.key === selected ? 1000 : 500 - r.rank}
              eventHandlers={{ click: () => onSelectRef.current(r.key) }}
            >
              <Tooltip direction="top" offset={[0, -14]}>
                #{r.rank} {r.name} · {r.score}
              </Tooltip>
            </Marker>
          ))}
        <FitView shapes={shapes} top={top} showAll={showAll} />
      </MapContainer>
      <button
        type="button"
        onClick={() => setShowAll((v) => !v)}
        className="absolute right-3 top-3 z-[400] rounded-full bg-white/95 px-3 py-1.5 text-xs font-medium text-gray-700 shadow hover:text-indigo-700"
      >
        {showAll ? "Zoom to my matches" : "All of Berlin"}
      </button>
      <div className="pointer-events-none absolute bottom-3 left-3 z-[400] rounded-lg bg-white/90 px-2 py-1.5 text-[10px] text-gray-600 shadow">
        <p className="mb-0.5 font-semibold text-gray-800">Match score</p>
        <div className="flex gap-1.5">
          {SCORE_BANDS.map((b) => (
            <span key={b.label} className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: b.color }} />
              {b.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
