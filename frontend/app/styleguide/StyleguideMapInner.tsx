"use client";

import { useState } from "react";
import { MapContainer } from "react-leaflet";
import { OfflineBasemap } from "@/components/map/OfflineBasemap";

export default function StyleguideMapInner() {
  const [ok, setOk] = useState<boolean | null>(null);
  return (
    <div>
      <MapContainer
        center={[52.5297, 13.4015]}
        zoom={14}
        style={{ height: 360, width: "100%", borderRadius: 16 }}
        scrollWheelZoom={false}
      >
        <OfflineBasemap onStatus={setOk} />
      </MapContainer>
      <p className="mt-2 text-[13px] text-text-muted" data-testid="basemap-status">
        {ok === null ? "Checking the map file…" : ok ? "Offline map file loaded." : "The offline map file isn't available on this server."}
      </p>
    </div>
  );
}
