"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Header menu entry for Berlin Neighborhoods (highlighted while on the page). */
export function NeighborhoodsNavLink() {
  const active = usePathname()?.startsWith("/neighborhoods");
  return (
    <Link
      href="/neighborhoods"
      aria-current={active ? "page" : undefined}
      className={`inline-flex items-center gap-1.5 font-medium transition ${
        active ? "text-indigo-700" : "text-gray-600 hover:text-gray-900"
      }`}
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true" className="hidden sm:block">
        <path
          d="M9 4 3 6.5v13.5l6-2.5 6 2.5 6-2.5V4l-6 2.5L9 4Z"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path d="M9 4v13.5M15 6.5V20" stroke="currentColor" strokeWidth="1.8" />
      </svg>
      <span className="sm:hidden">Neighborhoods</span>
      <span className="hidden sm:inline">Berlin Neighborhoods</span>
    </Link>
  );
}
