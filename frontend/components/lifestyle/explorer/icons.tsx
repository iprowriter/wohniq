/**
 * Line icons for Lifestyle profiles and Neighbourhood categories (no emoji: the owner's
 * decision; emoji read as decoration and vary by platform). 24×24, stroke = currentColor.
 */

import type { ReactNode } from "react";

function Svg({ size = 18, children }: { size?: number; children: ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0">
      {children}
    </svg>
  );
}

const PROFILE: Record<string, ReactNode> = {
  // mortarboard
  student: <><path d="M2 9l10-5 10 5-10 5-10-5z" /><path d="M6 11v5c3 2 9 2 12 0v-5" /></>,
  // briefcase
  young_professional: <><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 13h18" /></>,
  // two adults and a child
  family: <><circle cx="8" cy="6" r="2.5" /><circle cx="16" cy="6" r="2.5" /><circle cx="12" cy="12" r="1.8" /><path d="M4 20v-5a4 4 0 0 1 8 0M12 20v-3M20 20v-5a4 4 0 0 0-6-3.5" /></>,
  // laptop
  remote_creative: <><rect x="4" y="5" width="16" height="11" rx="1.5" /><path d="M2 19h20" /></>,
  // tree
  calm_green: <><path d="M12 3l6 8h-3l4 5H5l4-5H6l6-8z" /><path d="M12 16v5" /></>,
};

export function ProfileIcon({ id, size }: { id: string; size?: number }) {
  return <Svg size={size}>{PROFILE[id] ?? <circle cx="12" cy="12" r="8" />}</Svg>;
}

const CATEGORY: Record<string, ReactNode> = {
  overall: <path d="M12 3l2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.4 6.7 19.4l1.2-6L3.4 9.3l6-.7L12 3z" />,
  safety: <path d="M12 3l8 3v6c0 4.5-3.4 8.2-8 9-4.6-.8-8-4.5-8-9V6l8-3z" />,
  road_safety: <><path d="M9 3l-3 18M15 3l3 18" /><path d="M12 5v2M12 11v2M12 17v2" /></>,
  affluence: <><path d="M4 21V10l8-6 8 6v11" /><path d="M9 21v-6h6v6" /></>,
  education: <><path d="M2 9l10-5 10 5-10 5-10-5z" /><path d="M6 11v5c3 2 9 2 12 0v-5" /></>,
  health: <><rect x="4" y="4" width="16" height="16" rx="3" /><path d="M12 8v8M8 12h8" /></>,
  amenities: <><path d="M5 8h14l-1.5 12h-11L5 8z" /><path d="M9 8V6a3 3 0 0 1 6 0v2" /></>,
  green: <><path d="M12 3l6 8h-3l4 5H5l4-5H6l6-8z" /><path d="M12 16v5" /></>,
  transit: <><rect x="5" y="3" width="14" height="14" rx="3" /><path d="M5 11h14M8 21l2-4M16 21l-2-4" /><circle cx="9" cy="14" r=".6" /><circle cx="15" cy="14" r=".6" /></>,
  environment: <><path d="M4 14c0-6 5-10 16-10 0 11-4 16-10 16-3.3 0-6-2.7-6-6z" /><path d="M4 20c4-4 7-7 11-10" /></>,
  parking: <><rect x="4" y="3" width="16" height="18" rx="3" /><path d="M10 17V7h3a3 3 0 0 1 0 6h-3" /></>,
  affordability: <><path d="M15.5 7.5a5 5 0 1 0 0 9M6 10.5h7M6 13.5h7" /></>,
};

export function CategoryIcon({ id, size }: { id: string; size?: number }) {
  return <Svg size={size}>{CATEGORY[id] ?? <circle cx="12" cy="12" r="7" />}</Svg>;
}
