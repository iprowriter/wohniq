import type { SourceInfo } from "@/lib/neighborhoods/types";
import { sourceLabel } from "@/lib/neighborhoods/logic";

export function SourceTag({ source }: { source?: SourceInfo }) {
  return (
    <span
      className="ml-1 inline-flex items-center whitespace-nowrap rounded-full bg-chip px-2 py-0.5 align-middle text-[10px] font-medium text-text-muted"
      title={source ? `${source.title} — ${source.publisher}` : undefined}
    >
      {sourceLabel(source)}
    </span>
  );
}
