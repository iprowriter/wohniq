/**
 * Plain-language result for the rent check page, built only from the result's numbers
 * (golden rule 3: every claim traces to a data point). Pure, unit-tested.
 */

import type { RentResult } from "./check.ts";
import { euro, euro2 } from "../format.ts";

export const VERDICT_TITLE: Record<RentResult["verdict"], string> = {
  within_limit: "Your rent is within the rent-brake limit",
  above_limit: "Your rent is above the rent-brake limit",
  below_index: "Your rent is below the rent index",
  new_build: "New build: the rent brake doesn't apply",
  not_covered: "Not covered by the Mietspiegel",
  unknown: "Your rent index",
};

export function verdictTone(v: RentResult["verdict"]): "ok" | "warn" | "neutral" {
  if (v === "within_limit" || v === "below_index") return "ok";
  if (v === "above_limit") return "warn";
  return "neutral";
}

function groupsSentence(r: RentResult): string {
  if (!r.used_checklist) return "With no features ticked, the comparable rent is the index mean";
  const up = r.groups.filter((g) => g.effect > 0).length;
  const down = r.groups.filter((g) => g.effect < 0).length;
  const parts = [];
  if (up) parts.push(`${up} feature group${up > 1 ? "s" : ""} raising the value`);
  if (down) parts.push(`${down} lowering it`);
  if (!parts.length) return "Your ticks balance out, so the comparable rent is the index mean";
  return `With ${parts.join(" and ")}, the comparable rent is`;
}

export function explainResult(r: RentResult, sizeM2: number): string {
  if (!r.covered) {
    return (
      "The Mietspiegel 2026 covers flats ready for occupancy up to 2024. Newer flats aren't " +
      "in the table, and new buildings first let after 1 October 2014 aren't covered by the rent brake."
    );
  }
  const you = r.asked != null ? `You pay ${euro2(r.asked)}/m² cold. ` : "";
  const comparable = `${groupsSentence(r)} ${euro2(r.comparable!)}/m²`;
  if (r.exempt) {
    return (
      `${you}${comparable}. New buildings first let after 1 October 2014 are exempt from the ` +
      "rent brake, so there is no legal maximum."
    );
  }
  const limitMonthly = euro(r.limit! * sizeM2);
  let tail = `; the rent brake allows up to ${euro2(r.limit!)}/m² (${limitMonthly} cold).`;
  if (r.verdict === "above_limit" && r.over_per_month != null) {
    tail += ` That is about ${euro(r.over_per_month)} a month over the limit.`;
  } else if (r.verdict === "within_limit" && r.asked != null) {
    const under = Math.round((r.limit! - r.asked) * sizeM2);
    tail += ` You are ${euro(under)} a month under the limit.`;
  } else if (r.verdict === "below_index") {
    tail += " Your rent is below even the lowest index value for a flat like this.";
  }
  return `${you}${comparable}${tail}`;
}
