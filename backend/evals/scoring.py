"""Pure scoring for the parser eval (stdlib only, unit-testable offline).

Compares an expected partial criteria dict against the parser's actual output dict.
Only the fields named in `expected` are checked — so a case can assert "budget is
1500 and quiet is true" without caring about the rest. Matching is lenient where it
should be: amenities compare as case-insensitive sets, place names by containment.
"""

from __future__ import annotations


def match_field(expected, actual) -> bool:
    """True if `actual` satisfies `expected` for one field."""
    if isinstance(expected, list):
        exp = {str(x).lower() for x in expected}
        act = {str(x).lower() for x in (actual or [])}
        return exp == act
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.lower() in actual.lower()
    return expected == actual


def score_case(expected: dict, actual: dict) -> dict[str, bool]:
    """Return {field: passed} for every field named in `expected`."""
    return {field: match_field(value, actual.get(field)) for field, value in expected.items()}


def summarize(case_results: list[dict[str, bool]]) -> dict:
    """Aggregate per-case field results into headline metrics."""
    n_cases = len(case_results)
    total_fields = sum(len(r) for r in case_results)
    correct_fields = sum(sum(r.values()) for r in case_results)
    fully_correct = sum(1 for r in case_results if r and all(r.values()))
    return {
        "cases": n_cases,
        "cases_fully_correct": fully_correct,
        "case_accuracy": fully_correct / n_cases if n_cases else 0.0,
        "fields_checked": total_fields,
        "fields_correct": correct_fields,
        "field_accuracy": correct_fields / total_fields if total_fields else 0.0,
    }
