import type { SourceOut } from "@/lib/lifestyle/types";
import { sourceChip } from "@/lib/lifestyle/results";

export function SourceChip({ source }: { source?: SourceOut }) {
  return (
    <span
      className="ml-1 inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 align-middle text-[10px] font-medium text-gray-500"
      title={source ? `${source.title} — ${source.publisher}` : undefined}
    >
      {sourceChip(source)}
    </span>
  );
}
