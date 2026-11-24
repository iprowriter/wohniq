"use client";

// Homepage "See on the map": every listing on the OSM map. Zooming switches between the
// Berlin median, district medians, neighbourhood medians and individual price pills
// (tiers and thresholds: lib/map/listingsMap.ts). Clicking a pill opens a card above it.

import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import {
  GeoJSON,
  MapContainer,
  Marker,
  Popup,
  ZoomControl,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { getAreaShapes } from "@/lib/neighborhoods/api";
import type { AreaCollection } from "@/lib/neighborhoods/types";
import {
  INITIAL_CENTER,
  TIERS,
  TIER_LABEL,
  TIER_ZOOM,
  ZOOM,
  formatEuro,
  markersForZoom,
  tierForZoom,
  tierStatus,
  zoomIntoCluster,
  type Bounds,
  type MapListing,
  type MapMarker,
  type MapTier,
} from "@/lib/map/listingsMap";
import { ListingMapCard } from "./ListingMapCard";
import { OfflineBasemap } from "@/components/map/OfflineBasemap";

const TILE_TIMEOUT_MS = 4000; // no tile by then → clean background + Berlin outlines

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

type PillState = "default" | "visited" | "selected";

function markerHtml(m: MapMarker, state: PillState): string {
  if (m.kind === "listing") {
    return `<div class="wq-pill wq-pill--${state}" data-testid="map-pill" data-id="${m.listing.id}">${formatEuro(
      m.listing.warmmiete_eur,
    )}</div>`;
  }
  if (m.kind === "stack") {
    return `<div class="wq-stack" data-testid="map-stack">${m.count} flats</div>`;
  }
  if (m.tier === "city") {
    return `<div class="wq-area wq-area--city" data-testid="map-area" data-tier="city" data-name="Berlin"><span class="wq-area__name">Berlin median rent</span><span class="wq-area__price">${formatEuro(
      m.median,
    )}</span><span class="wq-area__meta">warm / month · ${m.count} listings</span></div>`;
  }
  return `<div class="wq-area" data-testid="map-area" data-tier="${m.tier}" data-name="${escapeHtml(m.name)}"><span class="wq-area__name">${escapeHtml(
    m.name,
  )} · ${m.count}</span><span class="wq-area__price">${formatEuro(m.median)} <small>median</small></span></div>`;
}

function markerTitle(m: MapMarker): string {
  if (m.kind === "listing") return `${formatEuro(m.listing.warmmiete_eur)} · ${m.listing.title}`;
  if (m.kind === "stack") return `${m.count} flats here, median ${formatEuro(m.median)}. Click to zoom in`;
  if (m.tier === "city") return `Berlin: median warm rent ${formatEuro(m.median)} across ${m.count} listings`;
  return `${m.name}: median warm rent ${formatEuro(m.median)} across ${m.count} listings. Click to zoom in`;
}

function toLatLngBounds(b: Bounds): L.LatLngBounds {
  return L.latLngBounds([b.south, b.west], [b.north, b.east]);
}

// Explore Berlin follows the map once it settles after a user move.
const USER_VIEW_DEBOUNCE_MS = 300;
const ARROW_KEYS = new Set(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"]);

/**
 * Tracks zoom (for tiers) and the visible area (for "Showing N of M"). Also tells which
 * moves the user made: dragging, any zoom (wheel, buttons, bubbles, pinch) or arrow-key
 * panning. A popup's auto-pan is none of these, so opening a card doesn't count.
 */
function ViewTracker({
  onView,
  onUserMove,
  onMoveStart,
}: {
  onView: (zoom: number, bounds: L.LatLngBounds) => void;
  onUserMove: () => void;
  onMoveStart: () => void;
}) {
  const map = useMapEvents({
    zoomend: () => onView(map.getZoom(), map.getBounds()),
    moveend: () => onView(map.getZoom(), map.getBounds()),
    movestart: () => onMoveStart(),
    dragstart: () => onUserMove(),
    zoomstart: () => onUserMove(),
    keydown: (e) => {
      if (ARROW_KEYS.has((e.originalEvent as KeyboardEvent).key)) onUserMove();
    },
    // Don't hijack page scrolling: the wheel zooms only after the user clicks the map.
    click: () => map.scrollWheelZoom.enable(),
    mouseout: () => map.scrollWheelZoom.disable(),
  });
  useEffect(() => {
    map.invalidateSize();
    onView(map.getZoom(), map.getBounds());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);
  return null;
}

function MapRef({ onMap }: { onMap: (map: L.Map) => void }) {
  const map = useMap();
  useEffect(() => onMap(map), [map, onMap]);
  return null;
}

interface Props {
  listings: MapListing[];
  /** Called (debounced) with the visible area and zoom after the user moved the map. */
  onUserViewChange?: (bounds: Bounds, zoom: number) => void;
}

export function ListingsMap({ listings, onUserViewChange }: Props) {
  const [map, setMap] = useState<L.Map | null>(null);
  const [zoom, setZoom] = useState<number>(ZOOM.initial);
  const [view, setView] = useState<L.LatLngBounds | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [visited, setVisited] = useState<Set<string>>(new Set());
  const [tilesOk, setTilesOk] = useState<boolean | null>(null);
  const [shapes, setShapes] = useState<AreaCollection | null>(null);
  const anyTileLoaded = useRef(false);
  const icons = useRef(new Map<string, L.DivIcon>());

  const userMoved = useRef(false);
  const onUserViewChangeRef = useRef(onUserViewChange);
  onUserViewChangeRef.current = onUserViewChange; // the debounced call uses the latest
  const userViewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => {
    if (userViewTimer.current) clearTimeout(userViewTimer.current);
  }, []);

  /** A new movement supersedes a pending report: only the final, settled view counts. */
  function cancelPendingUserView() {
    if (userViewTimer.current) clearTimeout(userViewTimer.current);
    userViewTimer.current = null;
  }

  /** After a user move, report the settled view (debounced) — never for auto-pans. */
  function handleView(z: number, b: L.LatLngBounds) {
    setZoom(z);
    setView(b);
    if (!userMoved.current || !onUserViewChangeRef.current) return;
    if (userViewTimer.current) clearTimeout(userViewTimer.current);
    userViewTimer.current = setTimeout(() => {
      userMoved.current = false;
      onUserViewChangeRef.current?.(
        { south: b.getSouth(), west: b.getWest(), north: b.getNorth(), east: b.getEast() },
        z,
      );
    }, USER_VIEW_DEBOUNCE_MS);
  }

  const tier = tierForZoom(zoom);
  const selected = listings.find((l) => l.id === selectedId) ?? null;

  // Map background: same offline handling as the listing-page map.
  useEffect(() => {
    const timer = setTimeout(() => {
      if (!anyTileLoaded.current) setTilesOk(false);
    }, TILE_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, []);
  const offline = tilesOk === false;
  useEffect(() => {
    if (offline && !shapes) getAreaShapes().then(setShapes).catch(() => {});
  }, [offline, shapes]);

  const markers = useMemo(() => {
    if (!map) return [];
    const z = Math.round(zoom);
    const project = (lat: number, lng: number) => map.project([lat, lng], z);
    return markersForZoom(listings, z, project, selectedId);
  }, [map, listings, zoom, selectedId]);

  const inView = useMemo(
    () => (view ? listings.filter((l) => view.contains([l.lat, l.lng])).length : listings.length),
    [view, listings],
  );

  function iconFor(m: MapMarker): L.DivIcon {
    const state: PillState =
      m.kind === "listing" && m.listing.id === selectedId
        ? "selected"
        : m.kind === "listing" && visited.has(m.listing.id)
          ? "visited"
          : "default";
    const html = markerHtml(m, state);
    let icon = icons.current.get(html);
    if (!icon) {
      icon = L.divIcon({ className: "wq-marker", html, iconSize: [0, 0], iconAnchor: [0, 0] });
      icons.current.set(html, icon);
    }
    return icon;
  }

  function select(id: string) {
    setSelectedId(id);
    setVisited((prev) => new Set(prev).add(id));
  }

  function activate(m: MapMarker) {
    if (m.kind === "listing") select(m.listing.id);
    else zoomInto(m);
  }

  function zoomInto(m: MapMarker) {
    if (!map || m.kind === "listing") return;
    if (m.kind === "area") {
      map.flyTo([m.lat, m.lng], zoomIntoCluster(m.tier, zoom), { duration: 0.6 });
      return;
    }
    // Zoom in just enough to separate the stacked flats (1–2 levels), keeping context.
    const bounds = toLatLngBounds(m.bounds);
    const fit = map.getBoundsZoom(bounds.pad(0.3), false, L.point(24, 24));
    const target = zoomIntoCluster("listing", Math.min(Math.max(fit, zoom + 1), zoom + 2));
    map.flyTo(bounds.getCenter(), target, { duration: 0.6 });
  }

  function goToTier(t: MapTier) {
    if (!map) return;
    userMoved.current = true; // may be a pure pan (same zoom): still the user's choice
    const center = t === "city" || t === "district" ? L.latLng(52.515, 13.4) : map.getCenter();
    map.flyTo(center, TIER_ZOOM[t], { duration: 0.6 });
  }

  return (
    <div className="relative" data-testid="listings-map" data-tier={tier} data-zoom={Math.round(zoom)}>
      <div className={offline ? "wohniq-map-offline" : undefined}>
        <MapContainer
          center={INITIAL_CENTER}
          zoom={ZOOM.initial}
          minZoom={ZOOM.min}
          maxZoom={ZOOM.max}
          scrollWheelZoom={false}
          zoomControl={false}
          className="wq-listings-map"
          style={{ height: "560px", width: "100%", borderRadius: "16px" }}
        >
          <MapRef onMap={setMap} />
          {/* Bottom-right: the top edge belongs to the tier switcher (fits a phone). */}
          <ZoomControl position="bottomright" />
          <ViewTracker
            onView={handleView}
            onUserMove={() => {
              userMoved.current = true;
            }}
            onMoveStart={cancelPendingUserView}
          />
          <OfflineBasemap
            onStatus={(ok) => {
              anyTileLoaded.current = ok;
              setTilesOk(ok);
            }}
          />
          {offline && shapes && (
            <GeoJSON
              data={shapes as GeoJSON.FeatureCollection}
              interactive={false}
              style={{ color: "#c4b5fd", weight: 1, fillColor: "#ede9fe", fillOpacity: 0.35 }}
            />
          )}

          {markers.map((m) => (
            <Marker
              key={m.key}
              position={[m.lat, m.lng]}
              icon={iconFor(m)}
              title={markerTitle(m)}
              riseOnHover
              zIndexOffset={
                m.kind === "listing" && m.listing.id === selectedId ? 2000 : m.kind === "area" ? 500 : 0
              }
              eventHandlers={{
                click: () => activate(m),
                // Leaflet only wires Enter for markers with a bound popup; ours is standalone.
                keydown: (e) => {
                  const key = (e.originalEvent as KeyboardEvent).key;
                  if (key === "Enter" || key === " ") {
                    e.originalEvent.preventDefault();
                    activate(m);
                  }
                },
              }}
            />
          ))}

          {selected && (
            <Popup
              key={selected.id}
              position={[selected.lat, selected.lng]}
              offset={[0, -12]}
              closeButton={false}
              className="wq-popup"
              minWidth={264}
              maxWidth={264}
              // Keep the card clear of the overlays: tier switcher (top) and status (bottom).
              autoPanPaddingTopLeft={[16, 64]}
              autoPanPaddingBottomRight={[16, 52]}
              eventHandlers={{
                // Map click / Escape closes the popup: clear the selection, unless the user
                // already picked another pill (this popup is then the one being replaced).
                remove: () => setSelectedId((cur) => (cur === selected.id ? null : cur)),
              }}
            >
              <ListingMapCard listing={selected} onClose={() => setSelectedId(null)} />
            </Popup>
          )}
        </MapContainer>
      </div>

      {/* Overlays live outside the Leaflet container, so clicks never pan the map. */}
      <div
        className="absolute right-3 top-3 z-[1000] flex overflow-hidden rounded-full border border-gray-200 bg-white/95 p-0.5 text-xs shadow-md backdrop-blur"
        role="group"
        aria-label="Map detail"
      >
        {TIERS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => goToTier(t)}
            aria-pressed={t === tier}
            className={`rounded-full px-3 py-1.5 font-medium transition-colors ${
              t === tier ? "bg-ink text-white" : "text-text-body hover:bg-accent-tint hover:text-accent"
            }`}
          >
            {TIER_LABEL[t]}
          </button>
        ))}
      </div>
      {/* Caption row below the map (not an overlay, so it never hides a marker). */}
      <div className="mt-2.5 flex flex-wrap items-center justify-between gap-x-5 gap-y-2 text-xs text-gray-600">
        <p role="status" data-testid="map-status" className="font-medium text-gray-700">
          {tierStatus(tier, listings.length, inView)}
        </p>
        <ul className="flex flex-wrap items-center gap-x-4 gap-y-1.5" aria-label="Legend">
          <li className="flex items-center gap-1.5">
            <span className="wq-legend wq-legend--pill">€</span> Warm rent of one flat
          </li>
          <li className="flex items-center gap-1.5">
            <span className="wq-legend wq-legend--stack">2</span> Several flats, click to zoom in
          </li>
          <li className="flex items-center gap-1.5">
            <span className="wq-legend wq-legend--area">€</span> Median rent of an area
          </li>
        </ul>
      </div>
      {offline && (
        <p className="mt-1.5 text-xs text-gray-500">
          The offline map file isn't available on this server. Outlines show Berlin&apos;s areas.
        </p>
      )}
    </div>
  );
}
