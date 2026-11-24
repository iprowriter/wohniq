"use client";

import dynamic from "next/dynamic";
import type { DestinationOut, RegionCollection, RegionResult } from "@/lib/lifestyle/types";

export type ExplorerMapProps = {
  shapes: RegionCollection | null;
  scores: Map<string, number>;
  excluded: Set<string>;
  top: RegionResult[];
  mode: "top" | "all";
  hovered: string | null;
  selected: string | null;
  onHover: (key: string | null) => void;
  onSelect: (key: string) => void;
  destination: DestinationOut | null;
  height?: number;
};

const Inner = dynamic(() => import("./ExplorerMapInner"), { ssr: false });

/** All 143 areas shaded by match, the top 10 numbered, the destination marked. */
export function ExplorerMap(props: ExplorerMapProps) {
  return <Inner {...props} />;
}
