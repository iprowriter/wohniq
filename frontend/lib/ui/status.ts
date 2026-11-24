/** Header badge text (components/layout/StatusBadge.tsx). Pure, so it's unit-tested. */

export type Status = { mode: "demo" | "live"; online: boolean };

export function statusText(s: Status | null, apiReachable: boolean): string {
  if (!apiReachable) return "Offline";
  if (!s) return "Demo data";
  if (s.mode === "live") return s.online ? "Live data" : "Live data · offline";
  return s.online ? "Demo data · online" : "Demo data · offline";
}
