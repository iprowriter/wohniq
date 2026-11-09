"use client";

import { useState } from "react";
import { photoSrc } from "@/lib/api";

interface Props {
  url: string;
  alt: string;
  className?: string;
  /** Sizing for the placeholder when the image can't load (defaults to `className`). */
  placeholderClassName?: string;
}

/** Listing photo that degrades to a neutral placeholder instead of a broken-image icon
 * (e.g. offline demo without local photo copies). */
export function ListingPhoto({ url, alt, className = "", placeholderClassName }: Props) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);

  if (failedUrl === url) {
    return (
      <div
        role="img"
        aria-label={alt}
        className={`flex items-center justify-center bg-gray-100 text-gray-300 ${placeholderClassName ?? className}`}
      >
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <path d="M3 10.5L12 3l9 7.5V21a1 1 0 01-1 1H4a1 1 0 01-1-1V10.5z" strokeLinejoin="round" />
          <path d="M9 22v-8h6v8" strokeLinejoin="round" />
        </svg>
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={photoSrc(url)} alt={alt} className={className} onError={() => setFailedUrl(url)} />
  );
}
