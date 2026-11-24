import type { Metadata } from "next";
import type { ReactNode } from "react";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import "leaflet/dist/leaflet.css";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { SiteFooter } from "@/components/layout/SiteFooter";

export const metadata: Metadata = {
  title: "WohnIQ — Find your Berlin flat. Know it's fair before you call.",
  description:
    "Describe the Berlin flat you want in plain words. WohnIQ ranks the flats, checks each rent " +
    "against the official Mietspiegel, flags likely scams, and tells you why.",
};

// Geist is bundled with the app (the `geist` package, self-hosted by next/font), so the
// design's type works offline, with no Google Fonts request.
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="flex min-h-screen flex-col font-sans text-text antialiased">
        <a
          href="#main"
          className="sr-only z-[1200] rounded-md bg-accent px-4 py-3 font-semibold text-white focus:not-sr-only focus:fixed focus:left-4 focus:top-3"
        >
          Skip to content
        </a>
        <SiteHeader />
        <main id="main" className="flex-1">
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
