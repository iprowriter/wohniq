import Link from "next/link";
import { LIFESTYLE_PATH } from "@/lib/lifestyle/marketing";

/** Glowing pill under the homepage search box that invites users into Lifestyle Match. */
export function LifestyleEntryBar() {
  return (
    <Link
      href={LIFESTYLE_PATH}
      className="group mx-auto mt-7 inline-flex max-w-full rounded-full bg-gradient-to-r from-indigo-500 via-fuchsia-500 to-indigo-500 bg-[length:200%_auto] p-px shadow-lg shadow-indigo-900/40 transition-transform duration-200 animate-shimmer hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-fuchsia-300 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-950"
    >
      <span className="flex items-center gap-3 whitespace-nowrap rounded-full bg-gray-950/95 px-3 py-2 pr-4 text-left sm:px-4">
        <span className="flex -space-x-2" aria-hidden="true">
          {["🎓", "🌳", "🎨"].map((e) => (
            <span
              key={e}
              className="flex h-7 w-7 items-center justify-center rounded-full border border-gray-800 bg-gray-900 text-sm transition-transform duration-200 group-hover:translate-y-[-2px]"
            >
              {e}
            </span>
          ))}
        </span>
        <span className="text-sm leading-snug text-gray-300">
          <span className="hidden sm:inline">Not sure where to look? </span>
          <span className="font-semibold text-white">Try Lifestyle Match</span>
          <span className="hidden text-gray-400 lg:inline"> — match by how you live</span>
        </span>
        <span className="text-fuchsia-300 transition-transform duration-200 group-hover:translate-x-1" aria-hidden="true">
          →
        </span>
      </span>
    </Link>
  );
}
