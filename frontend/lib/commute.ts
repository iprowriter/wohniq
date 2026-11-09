import type { CommuteOut } from "./types";

const TOOLTIPS: Record<string, string> = {
  network:
    "Estimated from the VBB timetable (weekday peak, 7–9 am): walking, waiting, riding and changes. Live transit data unavailable.",
  distance:
    "Estimated from straight-line distance and average transit speeds; live transit data unavailable.",
};

/** Tooltip explaining how an estimated commute was computed (none for live journeys). */
export function commuteTooltip(c: CommuteOut): string | undefined {
  return c.estimated ? TOOLTIPS[c.source ?? "distance"] ?? TOOLTIPS.distance : undefined;
}

/** "≈25 min" for offline estimates, "23 min" for live journeys. */
export function commuteMinutes(c: CommuteOut): string {
  return `${c.estimated ? "≈" : ""}${c.minutes} min`;
}

function changesText(changes: number): string {
  return changes === 0 ? "direct" : `${changes} change${changes > 1 ? "s" : ""}`;
}

/**
 * Secondary line:
 *   live      → "direct" / "1 change"
 *   network   → "direct · estimated" / "1 change · estimated" / "on foot · estimated"
 *   distance  → "estimated" (changes unknown, so not shown)
 */
export function commuteDetail(c: CommuteOut): string | null {
  if (!c.estimated) return c.changes == null ? null : changesText(c.changes);
  if (c.source === "network" && c.changes != null) {
    const onFoot = c.walk_minutes != null && c.walk_minutes >= c.minutes;
    return `${onFoot ? "on foot" : changesText(c.changes)} · estimated`;
  }
  return "estimated";
}
