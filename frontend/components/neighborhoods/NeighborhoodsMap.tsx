"use client";

// Shaded map of all 143 areas for the current ranking (same OSM tiles + LOR outlines as
// Lifestyle Match). Click an area → onSelect (the list scrolls to it); hovering a list
// row highlights its outline here.

import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import { GeoJSON, MapContainer, Marker, Tooltip, useMap } from "react-leaflet";
import type { AreaCollection, RankedArea } from "@/lib/neighborhoods/types";
import { BANDS, MUTED_COLOR, rankColor, rankTextColor } from "@/lib/neighborhoods/logic";
import { OfflineBasemap } from "@/components/map/OfflineBasemap";

const TILE_TIMEOUT_MS = 4000; // no tile by then → outlines on a plain background

interface Props {
  shapes: AreaCollection;
  areas: RankedArea[]; // the full ranking (every area)
  visible: Set<string>; // areas passing the list filter; the rest are greyed out
  markers: RankedArea[]; // numbered pins (first rows of the list as ordered)
  selected: string | null;
  hovered: string | null;
  bestLabel: string | null;
  worstLabel: string | null;
  onSelect: (key: string) => void;
}

interface StyleInput {
  byKey: Record<string, RankedArea>;
  total: number;
  visible: Set<string>;
  selected: string | null;
  hovered: string | null;
}

function styleFor(key: string, s: StyleInput): L.PathOptions {
  const a = s.byKey[key];
  const shown = s.visible.has(key);
  const active = key === s.selected;
  const hover = key === s.hovered;
  return {
    color: active ? "#0D1321" : hover ? "#2747E6" : "#ffffff",
    weight: active ? 3 : hover ? 2.5 : 0.8,
    fillColor: a && shown ? rankColor(a.rank, s.total) : MUTED_COLOR,
    fillOpacity: shown ? (active || hover ? 0.9 : 0.72) : 0.25,
  };
}

/** Frame all of Berlin, or zoom to the selected area. */
function FitView({ shapes, selected, showAll }: { shapes: AreaCollection; selected: string | null; showAll: boolean }) {
  const map = useMap();
  const target = useRef<{ selected: string | null; showAll: boolean }>({
    selected,
    showAll,
  });
  target.current = { selected, showAll };

  useEffect(() => {
    const frame = (animate: boolean) => {
      map.invalidateSize();
      let bounds = L.geoJSON(shapes as GeoJSON.FeatureCollection).getBounds();
      const { selected: sel, showAll: all } = target.current;
      if (sel && !all) {
        const feature = shapes.features.find((f) => f.properties.key === sel);
        if (feature)
          bounds = L.geoJSON(feature as GeoJSON.Feature)
            .getBounds()
            .pad(0.6);
      }
      if (!bounds.isValid()) return;
      if (animate)
        map.flyToBounds(bounds, {
          padding: [12, 12],
          maxZoom: 14,
          duration: 0.6,
        });
      else map.fitBounds(bounds, { padding: [12, 12], maxZoom: 13.5 });
    };
    frame(true);
    // The container only gets its final size after layout (sticky column, viewport
    // height): re-frame whenever it resizes, so Berlin always fits.
    const observer = new ResizeObserver(() => frame(false));
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map, shapes, selected, showAll]);
  return null;
}

function rankIcon(rank: number, total: number, active: boolean) {
  const size = active ? 32 : 24;
  const bg = active ? "#0D1321" : rankColor(rank, total);
  const fg = active ? "#ffffff" : rankTextColor(rank, total);
  return L.divIcon({
    className: "",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `<div style="width:${size}px;height:${size}px;border-radius:9999px;display:flex;align-items:center;justify-content:center;font:700 ${
      active ? 13 : 11
    }px system-ui;color:${fg};background:${bg};border:2px solid #fff;box-shadow:0 4px 10px rgba(17,24,39,.3)">${rank}</div>`,
  });
}

export function NeighborhoodsMap({
  shapes,
  areas,
  visible,
  markers,
  selected,
  hovered,
  bestLabel,
  worstLabel,
  onSelect,
}: Props) {
  const [tilesOk, setTilesOk] = useState<boolean | null>(null);
  const [showAll, setShowAll] = useState(false);
  const anyTile = useRef(false);
  const layer = useRef<L.GeoJSON | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const byKey = useMemo(() => Object.fromEntries(areas.map((a) => [a.key, a])), [areas]);
  const input: StyleInput = {
    byKey,
    total: areas.length,
    visible,
    selected,
    hovered,
  };
  const inputRef = useRef(input);
  inputRef.current = input;

  useEffect(() => {
    const t = setTimeout(() => !anyTile.current && setTilesOk(false), TILE_TIMEOUT_MS);
    return () => clearTimeout(t);
  }, []);

  // A new selection zooms in (unless the user chose "All of Berlin" since).
  useEffect(() => {
    if (selected) setShowAll(false);
  }, [selected]);

  // Restyle in place (GeoJSON layers don't re-style on prop changes).
  useEffect(() => {
    layer.current?.setStyle((f) => styleFor(f?.properties?.key as string, inputRef.current));
    const front = [hovered, selected].filter(Boolean);
    layer.current?.eachLayer((l) => {
      const key = ((l as L.Polygon).feature as GeoJSON.Feature | undefined)?.properties?.key;
      if (front.includes(key)) (l as L.Polygon).bringToFront();
    });
  }, [byKey, visible, selected, hovered]);

  const offline = tilesOk === false;
  return (
    <div className={`relative h-full ${offline ? "wohniq-map-offline" : ""}`} data-testid="neighborhoods-map">
      <MapContainer
        center={[52.52, 13.405]}
        zoom={10}
        style={{
          height: "100%",
          minHeight: 320,
          width: "100%",
          borderRadius: 16,
        }}
        scrollWheelZoom={false}
        zoomSnap={0.1}
        attributionControl
      >
        <OfflineBasemap attributionSuffix="areas: LOR 2021"
          onStatus={(ok) => {
            anyTile.current = ok;
            setTilesOk(ok);
          }}
        />
        <GeoJSON
          ref={layer}
          data={shapes as GeoJSON.FeatureCollection}
          style={(f) => ({
            ...styleFor(f?.properties?.key as string, inputRef.current),
            // Stable hook for tests and styling: each outline is tagged with its area key.
            className: `nbh-area nbh-area-${f?.properties?.key}`,
          })}
          onEachFeature={(feature, l) => {
            const key = feature.properties?.key as string;
            l.bindTooltip(
              () => {
                const a = inputRef.current.byKey[key];
                const rank = a ? `#${a.rank} of ${inputRef.current.total}` : "";
                return `<strong>${feature.properties?.name}</strong><br/><span style="color:#5B6478">${feature.properties?.district}</span>${
                  rank ? `<br/>${rank} · score ${Math.round(a.score)}` : ""
                }`;
              },
              { sticky: true },
            );
            l.on("click", () => onSelectRef.current(key));
          }}
        />
        {markers.map((a) => (
          <Marker
            key={a.key}
            position={a.centroid}
            icon={rankIcon(a.rank, areas.length, a.key === selected)}
            zIndexOffset={a.key === selected ? 1000 : 500 - a.rank}
            eventHandlers={{ click: () => onSelectRef.current(a.key) }}
          >
            <Tooltip direction="top" offset={[0, -12]}>
              #{a.rank} {a.name}
            </Tooltip>
          </Marker>
        ))}
        <FitView shapes={shapes} selected={selected} showAll={showAll} />
      </MapContainer>
      <button
        type="button"
        onClick={() => setShowAll(true)}
        className="absolute right-3 top-3 z-[400] rounded-full bg-white/95 px-3 py-1.5 text-xs font-medium text-text-body shadow hover:text-accent"
      >
        All of Berlin
      </button>
      <div className="pointer-events-none absolute bottom-2 left-2 z-[400] max-w-[calc(100%-1rem)] rounded-lg bg-white/95 px-2 py-1.5 text-[10px] text-text-body shadow sm:bottom-3 sm:left-3 sm:px-2.5 sm:py-2">
        <div className="flex items-center gap-1.5 whitespace-nowrap">
          <span className="font-semibold text-accent">{bestLabel ?? "Best"}</span>
          {BANDS.map((b) => (
            <span
              key={b.label}
              className="inline-block h-2 w-3.5 rounded-sm sm:h-2.5 sm:w-5"
              style={{ background: b.color }}
              title={b.label}
            />
          ))}
          <span className="font-semibold text-text-body">{worstLabel ?? "Worst"}</span>
        </div>
        <p className="mt-0.5 hidden text-text-muted sm:block">
          Colour = rank among Berlin&apos;s {areas.length} areas (fifths)
        </p>
      </div>
    </div>
  );
}
