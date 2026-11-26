/**
 * Verdict chips for listings: rent check and scam risk, in words (design: calm verdicts, two
 * states plus neutral, never red; chips always carry words). Pure, unit-tested.
 */

import type { RentOut, RiskOut } from "../types.ts";
import { euro, euro2 } from "../format.ts";

export type ChipTone = "ok" | "warn" | "neutral";
export type ChipSpec = { tone: ChipTone; text: string; short: string };

export function rentChip(rent: RentOut | null | undefined): ChipSpec | null {
  if (!rent) return null;
  const asked = rent.asked != null ? euro2(rent.asked) : null;
  // A bare verdict (map points) gets the short label only.
  const hasNumbers = asked != null && rent.low != null && rent.high != null;
  if (!hasNumbers && ["within_limit", "above_limit", "below_index"].includes(rent.verdict)) {
    const short = { within_limit: "Fair rent", above_limit: "Above limit", below_index: "Below index" }[
      rent.verdict as "within_limit" | "above_limit" | "below_index"
    ];
    return { tone: rent.verdict === "within_limit" ? "ok" : "warn", short, text: short };
  }
  switch (rent.verdict) {
    case "within_limit":
      return {
        tone: "ok",
        short: "Fair rent",
        text: `Fair rent · ${asked}/m² cold (index ${euro2(rent.low!)}–${euro2(rent.high!).slice(1)})`,
      };
    case "above_limit":
      return {
        tone: "warn",
        short: "Above limit",
        text: rent.limit != null ? `Above limit · ${asked}/m² vs limit ${euro2(rent.limit)}` : `Above limit · ${asked}/m²`,
      };
    case "below_index":
      return {
        tone: "warn",
        short: "Below index",
        text: `Below index · ${asked}/m² (index from ${euro2(rent.low!)})`,
      };
    case "new_build":
      return { tone: "neutral", short: "New build", text: "New build: no rent brake" };
    case "not_covered":
      return { tone: "neutral", short: "Not in index", text: "Not covered by the Mietspiegel" };
    default:
      return null;
  }
}

export function riskChip(risk: RiskOut | null | undefined): ChipSpec | null {
  if (!risk) return null;
  if (risk.band === "low") return { tone: "ok", short: "Low risk", text: "Low risk" };
  if (risk.band === "caution")
    return { tone: "warn", short: "Some signals", text: "Worth asking: some signals" };
  return { tone: "warn", short: "High risk", text: "High risk: read why" };
}

/** "Worth asking" line under a result: the concrete thing to ask, from data only. */
export function worthAsking(rent: RentOut | null | undefined, risk: RiskOut | null | undefined): string | null {
  if (risk && risk.band !== "low" && risk.signals.length) {
    return `Worth asking: ${risk.signals[0].evidence.replace(/^"|"$/g, "")}`;
  }
  if (rent?.verdict === "above_limit" && rent.over_per_month != null && rent.limit != null) {
    return (
      `Worth asking: the cold rent is about ${euro(rent.over_per_month)} a month over the ` +
      `rent-brake limit (${euro2(rent.limit)}/m², estimate). Exceptions can apply.`
    );
  }
  return null;
}

/** Results filter "Only fair rents": within the rent-brake limit. */
export function isFairRent(rent: RentOut | null | undefined): boolean {
  return rent?.verdict === "within_limit";
}
