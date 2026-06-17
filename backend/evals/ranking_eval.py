"""Ranking sanity eval (T2.6).

Runs each scenario through the ranker and checks the hand-labeled listing lands
within its top_k. Deterministic and offline. Prints a report, writes JSON, and
exits non-zero if any scenario fails.

Usage:
    uv run python -m evals.ranking_eval
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from evals.ranking_cases import SCENARIOS
from search.ranking import rank

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_PATH = RESULTS_DIR / "ranking_eval.json"


def run() -> tuple[dict, list[dict]]:
    rows: list[dict] = []
    for scenario in SCENARIOS:
        ranked = rank(list(scenario.candidates), scenario.criteria)
        order = [item.listing_id for item, _ in ranked]
        position = order.index(scenario.expected_top_id) + 1  # 1-based
        rows.append(
            {
                "name": scenario.name,
                "expected_top": scenario.expected_top_id,
                "top_k": scenario.top_k,
                "position": position,
                "order": order,
                "passed": position <= scenario.top_k,
            }
        )
    passed = sum(1 for r in rows if r["passed"])
    summary = {
        "scenarios": len(rows),
        "passed": passed,
        "pass_rate": passed / len(rows) if rows else 0.0,
    }
    return summary, rows


def _print_report(summary: dict, rows: list[dict]) -> None:
    for row in rows:
        mark = "PASS" if row["passed"] else "FAIL"
        print(f"[{mark}] {row['name']}")
        if not row["passed"]:
            print(
                f"        expected {row['expected_top']!r} in top {row['top_k']}, "
                f"got position {row['position']} · order={row['order']}"
            )
    print(f"\nSummary: {summary['passed']}/{summary['scenarios']} scenarios passed")


def main() -> None:
    summary, rows = run()
    _print_report(summary, rows)

    RESULTS_DIR.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))

    if summary["pass_rate"] < 1.0:
        sys.exit("Ranking sanity eval failed — see failures above.")


if __name__ == "__main__":
    main()
