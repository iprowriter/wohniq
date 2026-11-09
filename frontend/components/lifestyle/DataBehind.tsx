import type { Evidence, SourceOut } from "@/lib/lifestyle/types";

/** "The data behind this": every figure used, with its publication, period and caveat. */
export function DataBehind({
  evidence,
  notes,
  sources,
}: {
  evidence: Evidence[];
  notes: string[];
  sources: Record<string, SourceOut>;
}) {
  const used = Array.from(new Set(evidence.map((e) => e.source_id)));
  return (
    <div className="space-y-4">
      <ul className="space-y-2 text-sm text-gray-700">
        {evidence.map((e) => (
          <li key={e.attribute}>
            <span className="font-medium text-gray-900">{e.label}:</span> {e.text}
          </li>
        ))}
      </ul>
      {notes.length > 0 && (
        <div>
          <p className="mb-2 text-[11px] uppercase tracking-wide text-gray-400">Good to know about this data</p>
          <ul className="space-y-1.5 text-xs leading-relaxed text-gray-600">
            {notes.map((n) => (
              <li key={n}>ℹ️ {n}</li>
            ))}
          </ul>
        </div>
      )}
      <div>
        <p className="mb-2 text-[11px] uppercase tracking-wide text-gray-400">Sources</p>
        <ul className="space-y-3">
          {used.map((id) => {
            const s = sources[id];
            if (!s) return null;
            return (
              <li key={id} className="rounded-xl bg-gray-50 p-3 text-xs leading-relaxed text-gray-600">
                <p className="font-semibold text-gray-800">{s.title}</p>
                <p>
                  {s.publisher} · data {s.data_year}
                  {s.licence ? ` · ${s.licence}` : ""}
                </p>
                {s.caveat && <p className="mt-1 text-amber-800">Note: {s.caveat}</p>}
                {s.url && (
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-block text-indigo-600 hover:underline">
                    {s.url.replace(/^https?:\/\//, "")} ↗
                  </a>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
