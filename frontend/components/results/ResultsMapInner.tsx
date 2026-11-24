"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import { renderToStaticMarkup } from "react-dom/server";
import { GeoJSON, MapContainer, Marker, Tooltip, ZoomControl, useMap, useMapEvents } from "react-leaflet";
import { OfflineBasemap } from "@/components/map/OfflineBasemap";
import { StopModes } from "@/components/ui/TransitIcon";
import { getParksInView, getStopsInView, type Box } from "@/lib/api";
import { getAreaShapes } from "@/lib/neighborhoods/api";
import type { AreaCollection } from "@/lib/neighborhoods/types";
import { areaMarkers, formatEuro } from "@/lib/map/listingsMap";
import type { MapStop } from "@/lib/types";
import type { ResultsMapProps } from "./ResultsMap";

type Layer = "listings" | "median" | "transit" | "green";
const LAYERS: { id: Layer; label: string }[] = [
  { id: "listings", label: "Listings" },
  { id: "median", label: "Median rent" },
  { id: "transit", label: "Transit" },
  { id: "green", label: "Green" },
];
const TRANSIT_MIN_ZOOM = 14;
const GREEN_MIN_ZOOM = 13;

function pillIcon(price: number, active: boolean): L.DivIcon {
  return L.divIcon({
    className: "wq-marker",
    html: `<span class="wq-pill ${active ? "wq-pill--selected" : "wq-pill--default"}">${formatEuro(price)}</span>`,
    iconSize: [0, 0],
  });
}

function areaIcon(name: string, median: number, count: number): L.DivIcon {
  return L.divIcon({
    className: "wq-marker",
    html: `<span class="wq-area"><span class="wq-area__name">${name}</span><span class="wq-area__price">${formatEuro(median)}</span><span class="wq-area__meta">median · ${count} flats</span></span>`,
    iconSize: [0, 0],
  });
}

function stopIcon(s: MapStop): L.DivIcon {
  return L.divIcon({
    className: "wq-marker",
    html: `<span class="wq-stop">${renderToStaticMarkup(<StopModes modes={s.modes} size={14} />)}</span>`,
    iconSize: [0, 0],
  });
}

function boxOf(b: L.LatLngBounds): Box {
  return { south: b.getSouth(), west: b.getWest(), north: b.getNorth(), east: b.getEast() };
}

/** Fits the map to the results once they change. */
function FitResults({ points }: { points: [number, number][] }) {
  const map = useMap();
  const key = points.map((p) => p.join(",")).join(";");
  useEffect(() => {
    if (!points.length) return;
    map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 15 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, map]);
  return null;
}

/** Loads stops / parks for the visible area when those layers are on and zoomed in. */
function ViewLayers({ transit, green, onStops, onParks, onZoom }: {
  transit: boolean;
  green: boolean;
  onStops: (s: MapStop[]) => void;
  onParks: (p: GeoJSON.FeatureCollection | null) => void;
  onZoom: (z: number) => void;
}) {
  const map = useMap();
  const seq = useRef(0);
  function load() {
    const z = map.getZoom();
    onZoom(z);
    const n = ++seq.current;
    const box = boxOf(map.getBounds());
    if (transit && z >= TRANSIT_MIN_ZOOM) {
      getStopsInView(box).then((s) => n === seq.current && onStops(s)).catch(() => onStops([]));
    } else onStops([]);
    if (green && z >= GREEN_MIN_ZOOM) {
      getParksInView(box).then((p) => n === seq.current && onParks(p)).catch(() => onParks(null));
    } else onParks(null);
  }
  useMapEvents({ moveend: load });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [transit, green]);
  return null;
}

export default function ResultsMapInner({ results, areas, allListings, highlighted, onHighlight }: ResultsMapProps) {
  const [layers, setLayers] = useState<Set<Layer>>(new Set(["listings"]));
  const [shapes, setShapes] = useState<AreaCollection | null>(null);
  const [stops, setStops] = useState<MapStop[]>([]);
  const [parks, setParks] = useState<GeoJSON.FeatureCollection | null>(null);
  const [zoom, setZoom] = useState(13);
  const on = (l: Layer) => layers.has(l);

  useEffect(() => {
    getAreaShapes().then(setShapes).catch(() => {});
  }, []);

  const placed = results
    .map((r) => ({ r, lat: r.listing.location?.lat, lng: r.listing.location?.lng }))
    .filter((p): p is { r: typeof results[number]; lat: number; lng: number } => p.lat != null && p.lng != null);

  // The asked-for area: the district regions the in-area results lie in.
  const askedRegions = useMemo(() => {
    const names = new Set(
      results
        .filter((r) => r.area_match?.status === "in_area")
        .map((r) => r.listing.location?.district_region)
        .filter(Boolean) as string[],
    );
    if (!shapes || !names.size) return null;
    return {
      type: "FeatureCollection",
      features: shapes.features.filter((f) => names.has(f.properties.name)),
    } as GeoJSON.FeatureCollection;
  }, [results, shapes]);

  const medians = useMemo(
    () => (allListings && on("median") ? areaMarkers(allListings, "neighbourhood") : []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [allListings, layers],
  );

  function toggle(l: Layer) {
    setLayers((prev) => {
      const next = new Set(prev);
      if (next.has(l)) next.delete(l);
      else next.add(l);
      return next;
    });
  }

  const note =
    on("transit") && zoom < TRANSIT_MIN_ZOOM
      ? "Zoom in to see stops."
      : on("green") && zoom < GREEN_MIN_ZOOM
        ? "Zoom in to see green spaces."
        : null;

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface" data-testid="results-map">
      <div className="relative">
        <MapContainer
          center={[52.52, 13.405]}
          zoom={12}
          zoomControl={false}
          scrollWheelZoom={false}
          style={{ height: 520, width: "100%" }}
        >
          <OfflineBasemap attributionSuffix="areas: LOR 2021" />
          <ZoomControl position="bottomright" />
          <FitResults points={placed.map((p) => [p.lat, p.lng])} />
          <ViewLayers
            transit={on("transit")}
            green={on("green")}
            onStops={setStops}
            onParks={setParks}
            onZoom={setZoom}
          />
          {parks && (
            <GeoJSON
              key={JSON.stringify(parks.features.map((f) => f.properties?.name))}
              data={parks}
              interactive={false}
              style={{ color: "#5E8F73", weight: 1, fillColor: "#9FCBB0", fillOpacity: 0.55 }}
            />
          )}
          {askedRegions && (
            <GeoJSON
              key={askedRegions.features.map((f) => f.properties?.name).join("|")}
              data={askedRegions}
              interactive={false}
              style={{ color: "#2747E6", weight: 2, dashArray: "6 6", fillColor: "#2747E6", fillOpacity: 0.07 }}
            />
          )}
          {medians.map((m) => (
            <Marker key={m.key} position={[m.lat, m.lng]} icon={areaIcon(m.name, m.median, m.count)} keyboard={false} />
          ))}
          {on("transit") &&
            stops.map((s) => (
              <Marker key={s.id} position={[s.lat, s.lng]} icon={stopIcon(s)} keyboard={false}>
                <Tooltip direction="top" offset={[0, -10]}>{s.name}</Tooltip>
              </Marker>
            ))}
          {on("listings") &&
            placed.map(({ r, lat, lng }) => (
              <Marker
                key={r.listing.id}
                position={[lat, lng]}
                icon={pillIcon(r.listing.warmmiete_eur, highlighted === r.listing.id)}
                zIndexOffset={highlighted === r.listing.id ? 1000 : 0}
                title={`${r.listing.title}: ${formatEuro(r.listing.warmmiete_eur)} warm`}
                eventHandlers={{
                  mouseover: () => onHighlight(r.listing.id),
                  mouseout: () => onHighlight(null),
                  click: () =>
                    document
                      .querySelector(`[data-testid=result-card][data-id="${r.listing.id}"]`)
                      ?.scrollIntoView({ behavior: "smooth", block: "center" }),
                }}
              />
            ))}
        </MapContainer>
        {areas.length > 0 && askedRegions && (
          <span className="pointer-events-none absolute left-3 top-3 z-[500] rounded-sm bg-surface px-2.5 py-1 text-[13px] font-medium text-accent shadow-sm">
            {areas.join(" / ")} · as you asked
          </span>
        )}
        {note && (
          <span className="pointer-events-none absolute bottom-3 left-3 z-[500] rounded-sm bg-surface px-2.5 py-1 text-[12.5px] text-text-body shadow-sm">
            {note}
          </span>
        )}
      </div>
      <div className="flex flex-wrap gap-2 p-3" role="group" aria-label="Map layers">
        {LAYERS.map((l) => (
          <button
            key={l.id}
            type="button"
            aria-pressed={on(l.id)}
            onClick={() => toggle(l.id)}
            className={`min-h-tap rounded-md px-3.5 text-[14px] font-medium ${
              on(l.id) ? "bg-ink text-white" : "border border-line-strong bg-surface text-text hover:bg-ground"
            }`}
          >
            {l.label}
          </button>
        ))}
      </div>
    </div>
  );
}
