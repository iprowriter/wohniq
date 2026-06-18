import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";
import "leaflet/dist/leaflet.css";

export const metadata: Metadata = {
  title: "WohnIQ — AI apartment search for Berlin",
  description:
    "Describe the Berlin apartment you want in plain language. WohnIQ parses, ranks, explains, and flags risky listings.",
};

function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-gray-100 bg-white/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-1.5">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M3 10.5L12 3l9 7.5V21a1 1 0 01-1 1H4a1 1 0 01-1-1V10.5z" fill="#1a1a18" />
            <path d="M9 21V13h6v8" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <span className="text-lg font-bold tracking-tight">
            Wohn<span className="text-indigo-600">IQ</span>
          </span>
        </Link>
        <nav className="flex items-center gap-5 text-sm">
          <Link href="/" className="text-gray-500 hover:text-gray-900">
            Search
          </Link>
          <a
            href="#how-it-works"
            className="hidden text-gray-500 hover:text-gray-900 sm:inline"
          >
            How it works
          </a>
          <Link
            href="/"
            className="rounded-full bg-gray-900 px-4 py-1.5 font-medium text-white hover:bg-gray-700"
          >
            Find a flat
          </Link>
        </nav>
      </div>
    </header>
  );
}

function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-20 border-t border-gray-100 bg-white">
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="flex flex-col gap-8 md:flex-row md:items-start md:justify-between">
          <div className="max-w-xs">
            <p className="text-lg font-bold">
              Wohn<span className="text-indigo-600">IQ</span>
            </p>
            <p className="mt-1.5 text-sm leading-relaxed text-gray-500">
              AI-assisted apartment search for Berlin. Describe what you need, we do the rest.
            </p>
          </div>
          <div className="flex gap-12 text-sm">
            <div className="space-y-2.5">
              <p className="font-semibold text-gray-800">Product</p>
              <Link href="/" className="block text-gray-500 hover:text-gray-900">
                Search
              </Link>
              <a href="#how-it-works" className="block text-gray-500 hover:text-gray-900">
                How it works
              </a>
            </div>
            <div className="space-y-2.5">
              <p className="font-semibold text-gray-800">Legal</p>
              <a href="#" className="block text-gray-500 hover:text-gray-900">
                Privacy
              </a>
              <a href="#" className="block text-gray-500 hover:text-gray-900">
                Terms
              </a>
            </div>
          </div>
        </div>
        <p className="mt-8 text-xs text-gray-400">
          © {year} WohnIQ. Not affiliated with ImmoScout24, WG-Gesucht, or Immowelt.
        </p>
      </div>
    </footer>
  );
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col">
        <Header />
        <div className="flex-1">{children}</div>
        <Footer />
      </body>
    </html>
  );
}
