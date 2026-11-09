import type { Choice } from "@/lib/lifestyle/types";

interface Props {
  choices: Choice[];
  pageFor: (question: string) => string | null;
  pageTitle: (pageId: string) => string;
  onEdit: (pageId: string) => void;
}

export function ChoicesSummary({ choices, pageFor, pageTitle, onEdit }: Props) {
  return (
    <dl className="divide-y divide-gray-100 rounded-2xl border border-gray-100 bg-white">
      {choices.map((c) => {
        const page = pageFor(c.question);
        return (
          <div key={c.question} className="flex items-start justify-between gap-4 px-4 py-3">
            <div className="min-w-0">
              <dt className="text-xs text-gray-500">{c.question}</dt>
              <dd className="mt-0.5 text-sm font-medium text-gray-900">{c.answer}</dd>
            </div>
            {page && (
              <button
                type="button"
                onClick={() => onEdit(page)}
                className="flex-shrink-0 rounded-full px-2 py-1 text-xs text-indigo-600 hover:bg-indigo-50"
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
