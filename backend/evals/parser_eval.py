"""Parser eval runner (T2.3) — measures parser.v1 against the 20 canonical cases.

Runs each query through the real parser (hits Gemini), scores the output field by
field, prints a report, writes a JSON summary, and exits non-zero if field accuracy
falls below the threshold (SPEC §9: ≥ 90%). A `transport` can be injected for tests.

Usage:
    uv run python -m evals.parser_eval            # run against Gemini
    uv run python -m evals.parser_eval --threshold 0.9
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.logging import configure_logging, get_logger
from evals.parser_cases import CASES
from evals.scoring import score_case, summarize

configure_logging()
logger = get_logger(__name__)

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_PATH = RESULTS_DIR / "parser_eval.json"


def run(*, transport=None) -> tuple[dict, list[dict]]:
    # Imported here so the module (and its data) load without pydantic/network.
    from search.parser import parse_query

    case_results: list[dict[str, bool]] = []
    rows: list[dict] = []
    for case in CASES:
        actual = parse_query(case.query, transport=transport).model_dump()
        result = score_case(case.expected, actual)
        case_results.append(result)
        rows.append(
            {
                "query": case.query,
                "expected": case.expected,
                "actual": {k: actual.get(k) for k in case.expected},
                "fields": result,
                "passed": all(result.values()),
            }
        )
    return summarize(case_results), rows


def _print_report(summary: dict, rows: list[dict]) -> None:
    for row in rows:
        mark = "PASS" if row["passed"] else "FAIL"
        print(f"[{mark}] {row['query'][:70]}")
        if not row["passed"]:
            for field, ok in row["fields"].items():
                if not ok:
                    print(
                        f"        {field}: expected {row['expected'][field]!r}, "
                        f"got {row['actual'][field]!r}"
                    )
    print(
        "\nSummary: "
        f"{summary['cases_fully_correct']}/{summary['cases']} cases fully correct · "
        f"field accuracy {summary['field_accuracy']:.0%} "
        f"({summary['fields_correct']}/{summary['fields_checked']})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the parser eval.")
    parser.add_argument("--threshold", type=float, default=0.9, help="Min field accuracy")
    args = parser.parse_args()

    summary, rows = run()
    _print_report(summary, rows)

    RESULTS_DIR.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    logger.info("Wrote %s", RESULTS_PATH)

    if summary["field_accuracy"] < args.threshold:
        sys.exit(
            f"Field accuracy {summary['field_accuracy']:.0%} below threshold "
            f"{args.threshold:.0%}"
        )


if __name__ == "__main__":
    main()
