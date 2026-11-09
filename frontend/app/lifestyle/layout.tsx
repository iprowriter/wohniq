import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Lifestyle Match — find your Berlin neighbourhood · WohnIQ",
  description:
    "Answer a few questions about how you live. We match you to Berlin neighbourhoods using official data — and explain every suggestion.",
};

export default function LifestyleLayout({ children }: { children: ReactNode }) {
  return children;
}
