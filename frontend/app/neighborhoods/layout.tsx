import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Berlin Neighborhoods — compare all 143 areas · WohnIQ",
  description:
    "Berlin's neighborhoods ranked on official data: crime, road safety, schools, healthcare, parks, transport, parking and rent. Every number shows its source.",
};

export default function NeighborhoodsLayout({ children }: { children: ReactNode }) {
  return children;
}
