"use client";

import dynamic from "next/dynamic";

const Map = dynamic(() => import("./StyleguideMapInner"), {
  ssr: false,
  loading: () => <div className="h-[360px] rounded-lg bg-map-land" />,
});

export function StyleguideMap() {
  return <Map />;
}
