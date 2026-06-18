import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "WohnIQ — AI apartment search for Berlin",
  description:
    "Describe the Berlin apartment you want in plain language. WohnIQ parses, ranks, explains, and flags risky listings.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
