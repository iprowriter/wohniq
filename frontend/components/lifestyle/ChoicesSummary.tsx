import type { Choice } from "@/lib/lifestyle/types";

interface Props {
  choices: Choice[];
  pageFor: (question: string) => string | null;
  pageTitle: (pageId: string) => string;
  onEdit: (pageId: string) => void;
}

export function ChoicesSummary({ choices, pageFor, pageTitle, onEdit }: Props) {
  return (
    <dl className="divide-y divide-line rounded-2xl border border-line bg-white">
      {choices.map((c) => {
        const page = pageFor(c.question);
        return (
          <div key={c.question} className="flex items-start justify-between gap-4 px-4 py-3">
            <div className="min-w-0">
              <dt className="text-xs text-text-muted">{c.question}</dt>
              <dd className="mt-0.5 text-sm font-medium text-text">{c.answer}</dd>
            </div>
            {page && (
              <button
                type="button"
                onClick={() => onEdit(page)}
                className="flex-shrink-0 rounded-full px-2 py-1 text-xs text-accent hover:bg-accent-tint"
                aria-label={`Change "${c.question}" (${pageTitle(page)})`}
              >
                Change
              </button>
            )}
          </div>
        );
      })}
    </dl>
  );
}
