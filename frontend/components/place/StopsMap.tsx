"use client";

import dynamic from "next/dynamic";

export type StopsMapProps = {
  lat: number;
  lng: number;
  /** Dashed circle radius (m); the nearby-stops area. */
  radiusM?: number;
  height?: number;
  label?: string;
};

const Inner = dynamic(() => import("./StopsMapInner"), {
  ssr: false,
  loading: () => <div className="animate-pulse rounded-md bg-map-land" style={{ height: 240 }} />,
});

/** Small offline map of a point and the stops around it, with BVG icons. */
export function StopsMap(props: StopsMapProps) {
  return <Inner {...props} />;
}
