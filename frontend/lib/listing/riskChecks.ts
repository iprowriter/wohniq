/**
 * "Why the risk is low" / "What to ask": the checks behind a listing's scam risk, in words,
 * built only from the risk signals and the listing's own data (golden rule 3). Pure.
 */

import type { RentOut, RiskOut } from "../types.ts";

const TEXT_SIGNALS = new Set([
  "off_platform_payment",
  "payment_before_viewing",
  "landlord_unavailable",
  "urgency_pressure",
]);

export interface RiskChecks {
  title: string;
  passed: string[];
  flagged: string[];
  checked: string;
}

export function riskChecks(
  risk: RiskOut | null | undefined,
  rent: RentOut | null | undefined,
  anmeldungPossible: boolean,
): RiskChecks {
  const names = new Set((risk?.signals ?? []).map((s) => s.name));
  const passed: string[] = [];
  if (!names.has("price_below_index") && !names.has("price_below_market")) {
    passed.push(
      rent?.verdict === "above_limit"
        ? "The rent isn't suspiciously low (it's above the rent-brake limit: ask about that separately)."
        : "The rent isn't suspiciously low for a flat like this.",
    );
  }
  if (!names.has("photo_reuse")) passed.push("The photos don't appear as a set on any other listing.");
  if (![...names].some((n) => TEXT_SIGNALS.has(n))) {
    passed.push("No pressure to pay before a viewing; no landlord-abroad story.");
  }
  if (!names.has("no_anmeldung") && anmeldungPossible) passed.push("Anmeldung (registration) is possible.");

  const flagged = (risk?.signals ?? []).map((s) => s.evidence.replace(/^"(.*)"$/, "“$1”"));
  const band = risk?.band ?? "low";
  return {
    title: band === "low" ? "Why the risk is low" : "What to ask before you go further",
    passed,
    flagged,
    checked:
      "Checked: price against the rent index, photos against every other listing, the " +
      `landlord's wording, registration. Score ${risk?.score ?? 0}/100.`,
  };
}
