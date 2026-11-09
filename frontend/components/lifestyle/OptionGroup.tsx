"use client";

import type { Answers, MultiQuestionId, QuestionOut, SingleQuestionId } from "@/lib/lifestyle/types";
import { chooseSingle, isChosen, optionEffect, toggleMulti } from "@/lib/lifestyle/logic";

interface Props {
  question: QuestionOut;
  answers: Answers;
  labels: Record<string, string>; // attribute id -> label, for the "sets …" tooltip
  onChange: (next: Answers) => void;
}

/**
 * One question as a group of pill-shaped choices. Native radio/checkbox inputs (visually
 * hidden) give keyboard navigation, focus handling and screen-reader semantics for free.
 */
export function OptionGroup({ question, answers, labels, onChange }: Props) {
  const name = `q-${question.id}`;
  const chosenCount = question.multi ? (answers[question.id as MultiQuestionId] ?? []).length : 0;
  const full = question.multi && chosenCount >= question.max_choices;

  return (
    <fieldset className="space-y-3">
      <legend className="text-base font-semibold text-gray-900">{question.prompt}</legend>
      {question.help && <p className="-mt-1 text-xs leading-relaxed text-gray-500">{question.help}</p>}
      <div className="flex flex-wrap gap-2">
        {question.options.map((option) => {
          const chosen = isChosen(answers, question, option.id);
          const disabled = full && !chosen;
          const id = `${name}-${option.id}`;
          return (
            <label
              key={option.id}
              htmlFor={id}
              title={optionEffect(option, labels)}
              className={`group relative cursor-pointer select-none ${disabled ? "cursor-not-allowed opacity-40" : ""}`}
            >
              <input
                id={id}
                name={name}
                type={question.multi ? "checkbox" : "radio"}
                className="peer sr-only"
                checked={chosen}
                disabled={disabled}
                onChange={() => {
                  if (question.multi) {
                    onChange(toggleMulti(answers, question.id as MultiQuestionId, option.id, question.max_choices));
                  } else if (!chosen) {
                    onChange(chooseSingle(answers, question.id as SingleQuestionId, option.id));
                  }
                }}
                onClick={() => {
                  // Clicking the chosen radio again clears it (radios can't do that natively).
                  if (!question.multi && chosen) {
                    onChange(chooseSingle(answers, question.id as SingleQuestionId, option.id));
                  }
                }}
              />
              <span
                className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition-all duration-200 peer-focus-visible:ring-2 peer-focus-visible:ring-indigo-500 peer-focus-visible:ring-offset-2 ${
                  chosen
                    ? "border-indigo-600 bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
                    : "border-gray-200 bg-white text-gray-700 hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-sm"
                }`}
              >
                {chosen && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden="true">
                    <path d="M5 12l5 5L20 7" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
                {option.label}
              </span>
            </label>
          );
        })}
      </div>
      {question.multi && (
        <p className="text-xs text-gray-400" aria-live="polite">
          {chosenCount}/{question.max_choices} chosen
        </p>
      )}
    </fieldset>
  );
}
