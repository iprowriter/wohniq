"use client";

import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import type { PoiOut } from "@/lib/types";

const CATEGORY_COLORS: Record<string, string> = {
  cafes: "#f97316",
  parks: "#22c55e",
  supermarket: "#6366f1",
  nightlife: "#ec4899",
  gym: "#ef4444",
  transit: "#3b82f6",
};

interface Props {
  lat: number;
  lng: number;
  pois: PoiOut[];
}

export function NeighborhoodMap({ lat, lng, pois }: Props) {
  return (
    <MapContainer
      center={[lat, lng]}
      zoom={15}
      style={{ height: "300px", width: "100%", borderRadius: "12px" }}
      scrollWheelZoom={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
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
  );
}
