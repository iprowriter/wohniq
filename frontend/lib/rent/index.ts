/** /api/v1/rent/index: the Mietspiegel table and checklist the browser computes with. */

import type { ChecklistItem, Period, RentRow } from "./check.ts";

export interface RentIndex {
  source: string;
  periods: Record<string, Period>;
  rows: RentRow[];
  groups: Record<string, string>;
  checklist: (ChecklistItem & { label: string; text_de: string })[];
  insulation_items: string[];
  rent_brake_factor: number;
  group_step: number;
  new_build_from_year: number;
  no_heating_or_bath_deduction: number;
  exemptions: string;
  disclaimer: string;
  checklist_note: string;
}
