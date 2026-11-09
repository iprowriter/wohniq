"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import {
  MapContainer,
  TileLayer,
  Circle,
  CircleMarker,
  Popup,
  ScaleControl,
  useMap,
} from "react-leaflet";
import type { PoiOut } from "@/lib/types";

const CATEGORY_COLORS: Record<string, string> = {
  cafes: "#f97316",
  parks: "#22c55e",
  supermarket: "#6366f1",
  nightlife: "#ec4899",
  gym: "#ef4444",
  transit: "#3b82f6",
};

// If no map tile has loaded by then, assume the map background is unavailable (e.g. a
// network that hangs instead of failing). Tiles that arrive later switch back.
const TILE_TIMEOUT_MS = 4000;

/** Zoom out (once) so the whole amenity search area is visible; at the default zoom the
 * 1 km-wide circle is taller than the 300 px map. Runs when the offline view appears. */
function FitSearchArea({ lat, lng, radiusM }: { lat: number; lng: number; radiusM: number }) {
  const map = useMap();
  useEffect(() => {
    map.fitBounds(L.latLng(lat, lng).toBounds(radiusM * 2), { padding: [16, 16] });
  }, [map, lat, lng, radiusM]);
  return null;
}

interface Props {
  lat: number;
  lng: number;
  pois: PoiOut[];
  /** Radius the amenities were searched in; drawn when the map background is offline. */
  radiusM?: number;
}

export function NeighborhoodMap({ lat, lng, pois, radiusM = 500 }: Props) {
  // null = still loading, true = tiles load, false = map background unavailable
  const [tilesOk, setTilesOk] = useState<boolean | null>(null);
  const anyTileLoaded = useRef(false);
  const wasOffline = useRef(false);
  const tileLayer = useRef<L.TileLayer>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (!anyTileLoaded.current) setTilesOk(false);
    }, TILE_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, []);

  const offline = tilesOk === false;
  if (offline) wasOffline.current = true;

  return (
    // The offline look is applied via this wrapper: MapContainer ignores className/style
    // changes after its first render.
    <div className={offline ? "wohniq-map-offline" : undefined}>
      <MapContainer
        center={[lat, lng]}
        zoom={15}
        style={{ height: "300px", width: "100%", borderRadius: "12px" }}
        scrollWheelZoom={false}
      >
        <TileLayer
          ref={tileLayer}
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          eventHandlers={{
            tileload: () => {
              anyTileLoaded.current = true;
              setTilesOk(true);
              if (wasOffline.current) {
                // Connection is back: Leaflet never retries failed tiles, so re-request
                // everything in view instead of leaving grey gaps.
                wasOffline.current = false;
                tileLayer.current?.redraw();
              }
            },
            tileerror: () => {
              if (!anyTileLoaded.current) setTilesOk(false);
            },
          }}
        />
        {offline && (
          <>
            <Circle
              center={[lat, lng]}
              radius={radiusM}
              interactive={false}
              pathOptions={{
                color: "#6366f1",
                weight: 1.5,
                dashArray: "6 6",
                fillColor: "#6366f1",
                fillOpacity: 0.05,
              }}
            />
            <ScaleControl position="bottomleft" imperial={false} />
            <FitSearchArea lat={lat} lng={lng} radiusM={radiusM} />
          </>
        )}
        <CircleMarker
          center={[lat, lng]}
          radius={9}
          pathOptions={{ color: "white", fillColor: "#111827", fillOpacity: 1, weight: 2 }}
        >
          <Popup>This listing</Popup>
        </CircleMarker>
        {pois.map((poi, i) => (
          <CircleMarker
            key={i}
            center={[poi.lat, poi.lng]}
            radius={5}
            pathOptions={{
              color: "white",
              fillColor: CATEGORY_COLORS[poi.category] ?? "#6b7280",
              fillOpacity: 0.85,
              weight: 1,
            }}
          >
            <Popup>{poi.name || poi.category}</Popup>
          </CircleMarker>
        ))}
      </MapContainer>
      {offline && (
        // Caption below the map (not an overlay) so it never hides a marker.
        <p role="status" className="mt-1.5 text-xs text-gray-500">
          Map background needs an internet connection. Dashed circle: {radiusM} m amenity search
          area.
        </p>
      )}
    </div>
  );
}
