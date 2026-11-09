"""Lifestyle Match eval (T7.7) — offline, deterministic, runs in CI.

Two kinds of checks against the shipped region bundle:

1. **Scenarios** (evals/lifestyle_cases.py): realistic answer sets with expectations a
   good recommendation must meet — including the Definition of Done (student preset →
   an area near TU Berlin within a student budget, with reasons).
2. **Properties** that must hold for every preset:
   * determinism — same answers, same ranking and scores;
   * exclusion invariance — removing an area never changes any other area's score;
   * monotonicity — raising a weight never pushes down the best area for it;
   * budget ordering — every affordable area is ranked before any over-budget one;
   * grounded explanations — every evidence sentence quotes the number it is based on
     and cites a source that exists.
3. **Privacy by construction** (ADR-0012): answers reject unknown fields, every question
   is a fixed choice, destinations are a fixed list, and no protected characteristic is
   asked. (Log-leak and no-storage checks run against the API in
   tests/test_lifestyle_privacy.py.)

Usage:
    uv run python -m evals.lifestyle_eval
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from evals.lifestyle_cases import SCENARIOS
from lifestyle.explain import explain_match
from lifestyle.profiles import ProfileBundle, get_bundle
from lifestyle.questionnaire import PRESETS, Answers
from lifestyle.scoring import RegionMatch, match
from lifestyle.weights import apply_overrides, derive_weights

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_PATH = RESULTS_DIR / "lifestyle_eval.json"
MONOTONE_ATTRIBUTES = ("cafes", "green", "quiet", "safety", "transit", "family", "nightlife")


def _preset_answers() -> list[tuple[str, Answers]]:
    out = []
    for p in PRESETS:
        a = p.answers
        if p.id == "young_professional":
            a = a.model_copy(update={"destination": "alexanderplatz"})
        out.append((p.id, a))
    return out


def _grounded(m: RegionMatch, bundle: ProfileBundle, answers: Answers) -> list[str]:
    """Evidence sentences that don't quote their own number (or cite an unknown source)."""
    problems = []
    by_attr = {f.attribute: f for f in m.factors}
    for ev in explain_match(m, bundle, answers).evidence:
        f = by_attr[ev.attribute]
        if ev.source_id not in bundle.sources:
            problems.append(f"{ev.attribute}: unknown source {ev.source_id}")
        if f.attribute in ("quiet", "clean_air", "cool_summer", "green"):
            shares = m.region.measures[f.attribute].shares or {}
            expected = f"{shares.get('best', 0):.0f}%"
        elif f.attribute == "affordability":
            expected = f"€{m.warm_rent_eur:,.0f}"
        elif f.attribute == "commute":
            expected = f"{m.commute.minutes} min"
        elif f.attribute in ("water", "transit"):
            expected = f"{round(f.raw, -1):.0f} m" if f.raw < 1000 else f"{f.raw / 1000:.1f} km"
        elif f.attribute == "safety":
            expected = f"{f.raw:,.0f}"
        elif f.attribute in ("family", "young_crowd"):
            expected = f"{f.raw:.1f}%"
        else:
            expected = f"≈ {f.raw:.0f}"
        if expected not in ev.text:
            problems.append(f"{ev.attribute}: {expected!r} not in {ev.text!r}")
    return problems


def _privacy_checks(bundle: ProfileBundle) -> list[dict]:
    from pydantic import ValidationError

    from lifestyle.questionnaire import QUESTIONS

    try:
        Answers(budget_eur=700, size_m2=30, name="Alex", email="a@example.org")
        rejects_extra = False
    except ValidationError:
        rejects_extra = True
    text = " ".join([q.prompt for q in QUESTIONS] + [o.label for q in QUESTIONS for o in q.options])
    protected = [
        w
        for w in ("age", "gender", "religion", "nationality", "origin", "income", "health")
        if f" {w} " in f" {text.lower()} "
    ]
    return [
        {
            "name": "privacy: answers reject unknown fields",
            "kind": "privacy",
            "passed": rejects_extra,
        },
        {
            "name": "privacy: every question is a fixed choice (no free text)",
            "kind": "privacy",
            "passed": all(q.options for q in QUESTIONS),
        },
        {
            "name": "privacy: destinations are a fixed list",
            "kind": "privacy",
            "passed": len(bundle.destinations) > 0
            and all(d.derived_from for d in bundle.destinations),
        },
        {
            "name": "privacy: no protected characteristics asked",
            "kind": "privacy",
            "passed": not protected,
            "detail": ", ".join(protected),
        },
    ]


def run() -> tuple[dict, list[dict]]:
    bundle = get_bundle()
    rows: list[dict] = []

    for sc in SCENARIOS:
        results = match(bundle, sc.answers, derive_weights(sc.answers)).results
        passed, detail = sc.check(results, bundle, sc.answers)
        rows.append({"name": sc.name, "kind": "scenario", "passed": passed, "detail": detail})

    for pid, answers in _preset_answers():
        weights = derive_weights(answers)
        first = match(bundle, answers, weights)
        second = match(bundle, answers, weights)
        same = [(m.region.key, m.total) for m in first.results] == [
            (m.region.key, m.total) for m in second.results
        ]
        rows.append({"name": f"determinism: {pid}", "kind": "property", "passed": same})

        totals = {m.region.key: m.total for m in first.results}
        drop = [m.region.key for m in first.results[:3]]
        rest = match(bundle, answers, weights, excluded=drop).results
        invariant = all(totals[m.region.key] == m.total for m in rest) and not (
            set(drop) & {m.region.key for m in rest}
        )
        rows.append(
            {"name": f"exclusion invariance: {pid}", "kind": "property", "passed": invariant}
        )

        fits = [m.fits_budget for m in first.results]
        rows.append(
            {
                "name": f"affordable before over-budget: {pid}",
                "kind": "property",
                "passed": fits == sorted(fits, reverse=True),
            }
        )

        problems = [p for m in first.results[:10] for p in _grounded(m, bundle, answers)]
        rows.append(
            {
                "name": f"grounded explanations (top 10): {pid}",
                "kind": "property",
                "passed": not problems,
                "detail": "; ".join(problems[:3]),
            }
        )

    neutral = Answers(budget_eur=1200, size_m2=50)
    base = {"nightlife": 2, "water": 2, "everyday": 2}
    for attribute in MONOTONE_ATTRIBUTES:
        best = max(bundle.regions, key=lambda r: bundle.score(attribute, r.measures[attribute].raw))
        ranks = []
        for level in range(6):
            weights = apply_overrides(derive_weights(neutral), {**base, attribute: level})
            ranks.append(
                next(m.rank for m in match(bundle, neutral, weights).results if m.region == best)
            )
        rows.append(
            {
                "name": f"monotonicity: {attribute}",
                "kind": "property",
                "passed": ranks == sorted(ranks, reverse=True),
                "detail": f"{best.name}: ranks {ranks}",
            }
        )

    rows.extend(_privacy_checks(bundle))

    passed = sum(r["passed"] for r in rows)
    summary = {
        "checks": len(rows),
        "passed": passed,
        "pass_rate": passed / len(rows) if rows else 0.0,
        "scenarios": sum(r["kind"] == "scenario" for r in rows),
    }
    return summary, rows


def _print_report(summary: dict, rows: list[dict]) -> None:
    for row in rows:
        mark = "PASS" if row["passed"] else "FAIL"
        print(f"[{mark}] {row['name']}")
        if row.get("detail") and (row["kind"] == "scenario" or not row["passed"]):
            print(f"        {row['detail']}")
    print(f"\nSummary: {summary['passed']}/{summary['checks']} checks passed")


def main() -> None:
    summary, rows = run()
    _print_report(summary, rows)
    RESULTS_DIR.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    if summary["pass_rate"] < 1.0:
        sys.exit("Lifestyle eval failed — see failures above.")


if __name__ == "__main__":
    main()
