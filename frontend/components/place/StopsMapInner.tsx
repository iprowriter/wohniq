"use client";

import { useEffect, useMemo, useState } from "react";
import L from "leaflet";
import { renderToStaticMarkup } from "react-dom/server";
import { Circle, MapContainer, Marker, Tooltip } from "react-leaflet";
import { OfflineBasemap } from "@/components/map/OfflineBasemap";
import { StopModes } from "@/components/ui/TransitIcon";
import { getStopsInView } from "@/lib/api";
import type { MapStop } from "@/lib/types";
import type { StopsMapProps } from "./StopsMap";

const PIN = L.divIcon({
  className: "wq-marker",
  html: `<svg width="26" height="34" viewBox="0 0 26 34" style="transform:translate(-13px,-32px)" aria-hidden="true"><path d="M13 33s11-10.6 11-19.5C24 6.6 19.1 2 13 2S2 6.6 2 13.5C2 22.4 13 33 13 33z" fill="#0D1321" stroke="#fff" stroke-width="2"/><circle cx="13" cy="13.5" r="4" fill="#fff"/></svg>`,
  iconSize: [0, 0],
});

function stopIcon(s: MapStop): L.DivIcon {
  const icons = renderToStaticMarkup(<StopModes modes={s.modes} size={15} />);
  return L.divIcon({
    className: "wq-marker",
    html: `<span class="wq-stop" role="img" aria-label="${s.name.replace(/"/g, "")}">${icons}</span>`,
    iconSize: [0, 0],
  });
}

export default function StopsMapInner({ lat, lng, radiusM = 500, height = 240, label }: StopsMapProps) {
  const [stops, setStops] = useState<MapStop[]>([]);
  const box = useMemo(() => {
    const dLat = 700 / 111_320;
    const dLng = dLat / Math.cos((lat * Math.PI) / 180);
    return { south: lat - dLat, north: lat + dLat, west: lng - dLng, east: lng + dLng };
  }, [lat, lng]);

  useEffect(() => {
    getStopsInView(box).then(setStops).catch(() => setStops([]));
  }, [box]);

  return (
    <div data-testid="stops-map">
      <MapContainer
        center={[lat, lng]}
        zoom={15}
        scrollWheelZoom={false}
        style={{ height, width: "100%", borderRadius: 12 }}
      >
        <OfflineBasemap />
        <Circle
          center={[lat, lng]}
          radius={radiusM}
          interactive={false}
          pathOptions={{ color: "#2747E6", weight: 1.5, dashArray: "5 6", fillOpacity: 0.04 }}
        />
        {stops.map((s) => (
          <Marker key={s.id} position={[s.lat, s.lng]} icon={stopIcon(s)} keyboard={false}>
            <Tooltip direction="top" offset={[0, -10]}>
              {s.name}
            </Tooltip>
          </Marker>
        ))}
        <Marker position={[lat, lng]} icon={PIN} title={label ?? "This address"} />
      </MapContainer>
    </div>
  );
}
