import { redirect } from "next/navigation";

/** The old results address: the ranking now lives in the explorer (T9.6). */
export default function LegacyLifestyleResults() {
  redirect("/lifestyle");
}
