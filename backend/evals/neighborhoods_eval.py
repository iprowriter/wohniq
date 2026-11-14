"""Berlin Neighbourhoods eval — offline, deterministic, runs in CI (via pytest).

1. **Ground truth** (evals/neighborhoods_cases.py): well-known facts about Berlin the
   rankings must agree with — catches a flipped direction, a shifted parser column or a
   broken weight.
2. **Properties** for every category and area:
   * determinism — same request, same ranking and scores;
   * direction — within every metric, a better raw value never gets a lower score;
   * dominance — an area at least as good on every metric of a category never scores
     below the other;
   * overall monotonicity — raising a category's weight never pushes down that
     category's best area in the overall ranking;
   * single focus — the overall ranking with only one category weighted equals that
     category's ranking;
   * tiers — the "best" and "worst" badges go to ~20% of areas each;
   * grounded explanations — every highlight quotes the stored number and the true rank,
     and cites a source in the bundle;
   * provenance — every value cites a registered source with a method; every Berlin
     reference lies within the areas' range;
   * wording (ADR-0013) — no label or explanation tells users to "avoid" an area or
     describes residents.
3. **Known gaps**: real-world facts the current data can't reproduce (e.g. Grunewald's
   affluence, which needs income or land-value data). Reported with the reason, not
   counted as pass or failure, and flagged when they start passing.

Usage:
    uv run python -m evals.neighborhoods_eval        # or: make eval-neighborhoods
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from evals.neighborhoods_cases import CASES
from neighborhoods.bundle import NeighbourhoodBundle, get_bundle
from neighborhoods.catalog import CATEGORIES, MAX_WEIGHT, METRICS_BY_ID, OVERALL, metrics_of
from neighborhoods.explain import format_value, headline_metric, highlights
from neighborhoods.scoring import (
    category_table,
    default_weights,
    metric_score,
    rank_areas,
    ranks_by_category,
)

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_PATH = RESULTS_DIR / "neighborhoods_eval.json"
BANNED_WORDS = (
    "avoid",
    "poor people",
    "rich people",
    "deprived",
    "ghetto",
    "dangerous",
    "bad area",
)


def _row(name: str, kind: str, passed: bool, detail: str = "") -> dict:
    return {"name": name, "kind": kind, "passed": bool(passed), "detail": detail}


def _ground_truth(bundle: NeighbourhoodBundle) -> list[dict]:
    rows = []
    ranks = ranks_by_category(bundle)
    by_name = {a.name: a.key for a in bundle.regions}
    n = len(bundle.regions)
    for case in CASES.tiers:
        r = ranks[case.category]
        problems = []
        for name in case.best:
            if r[by_name[name]].tier != "best":
                problems.append(f"{name} #{r[by_name[name]].rank} not in top 20%")
        for name in case.worst:
            if r[by_name[name]].tier != "worst":
                problems.append(f"{name} #{r[by_name[name]].rank} not in bottom 20%")
        for name in case.top_half:
            if r[by_name[name]].rank > n // 2:
                problems.append(f"{name} #{r[by_name[name]].rank} not in top half")
        for name in case.bottom_half:
            if r[by_name[name]].rank <= n // 2:
                problems.append(f"{name} #{r[by_name[name]].rank} not in bottom half")
        if case.known_gap:
            row = _row(case.name, "known gap", not problems, case.known_gap)
            row["now_passes"] = not problems  # flag it: the gap may be closed
            rows.append(row)
            continue
        rows.append(_row(case.name, "ground truth", not problems, "; ".join(problems)))

    table = category_table(bundle)
    for case in CASES.districts:

        def mean(district: str, cat: str = case.category) -> float:
            return statistics.fmean(
                table[a.key][cat].score for a in bundle.regions if a.district == district
            )

        hi, lo = mean(case.higher), mean(case.lower)
        rows.append(_row(case.name, "ground truth", hi > lo, f"{hi:.1f} vs {lo:.1f}"))

    for case in CASES.all_above:
        r = ranks[case.category]
        worst_above = max(r[a.key].rank for a in bundle.regions if a.district == case.above)
        best_below = min(r[a.key].rank for a in bundle.regions if a.district == case.below)
        rows.append(
            _row(
                case.name,
                "ground truth",
                worst_above < best_below,
                f"lowest {case.above} #{worst_above}, highest {case.below} #{best_below}",
            )
        )
    return rows


def _properties(bundle: NeighbourhoodBundle) -> list[dict]:
    rows = []
    n = len(bundle.regions)

    # Determinism
    for cat in (OVERALL, *(c.id for c in CATEGORIES)):
        a = [(r.area.key, r.rank, r.score) for r in rank_areas(bundle, cat)]
        b = [(r.area.key, r.rank, r.score) for r in rank_areas(bundle, cat)]
        rows.append(_row(f"determinism: {cat}", "property", a == b))

    # Direction: within a metric, better raw value → score at least as high
    bad = []
    for m in bundle.available():
        scored = sorted(
            (
                (a.values[m.id].raw, metric_score(bundle, m, a.values[m.id]).score)
                for a in bundle.regions
            ),
            key=lambda x: x[0],
        )
        scores = [s for _, s in scored]
        expected = sorted(scores) if m.higher_is_better else sorted(scores, reverse=True)
        if scores != expected:
            bad.append(m.id)
    rows.append(
        _row(
            "direction: every metric's score follows its raw value",
            "property",
            not bad,
            ", ".join(bad),
        )
    )

    # Dominance within categories
    table = category_table(bundle)
    violations = []
    for c in CATEGORIES:
        mets = [m for m in metrics_of(c.id) if m.weight > 0 and m.id in bundle.references]
        for a in bundle.regions:
            for b in bundle.regions:
                if a.key == b.key:
                    continue
                dominates = all(
                    (
                        (a.values[m.id].raw >= b.values[m.id].raw)
                        if m.higher_is_better
                        else (a.values[m.id].raw <= b.values[m.id].raw)
                    )
                    for m in mets
                )
                if dominates and table[a.key][c.id].score < table[b.key][c.id].score - 1e-9:
                    violations.append(f"{c.id}: {a.name} < {b.name}")
    rows.append(
        _row(
            "dominance: better on every metric → never a lower category score",
            "property",
            not violations,
            "; ".join(violations[:5]),
        )
    )

    # Overall monotonicity + single focus
    ranks = ranks_by_category(bundle)
    for c in CATEGORIES:
        best_key = min(ranks[c.id].values(), key=lambda r: (r.rank, r.area.name)).area.key
        low = {**default_weights(), c.id: 1}
        high = {**default_weights(), c.id: MAX_WEIGHT}
        r_low = next(r.rank for r in rank_areas(bundle, OVERALL, low) if r.area.key == best_key)
        r_high = next(r.rank for r in rank_areas(bundle, OVERALL, high) if r.area.key == best_key)
        rows.append(
            _row(
                f"monotonicity: more weight on {c.id} never demotes its best area",
                "property",
                r_high <= r_low,
                f"#{r_low} → #{r_high}",
            )
        )

        only = {cid: 0 for cid in default_weights()} | {c.id: 1}
        focused = [(r.area.key, r.rank) for r in rank_areas(bundle, OVERALL, only)]
        direct = [(r.area.key, r.rank) for r in rank_areas(bundle, c.id)]
        rows.append(
            _row(
                f"single focus: overall with only {c.id} = {c.id} ranking",
                "property",
                focused == direct,
            )
        )

    # Tiers
    for cat in (OVERALL, *(c.id for c in CATEGORIES)):
        ranked = rank_areas(bundle, cat)
        best = sum(r.tier == "best" for r in ranked)
        worst = sum(r.tier == "worst" for r in ranked)
        ok = 0.1 * n <= best <= 0.35 * n and 0.1 * n <= worst <= 0.35 * n
        rows.append(
            _row(
                f"tiers: ~20% best / worst in {cat}", "property", ok, f"{best} best, {worst} worst"
            )
        )

    # Grounded highlights (every area)
    problems = []
    for a in bundle.regions:
        strengths, watch = highlights(bundle, a.key)
        for h in strengths + watch:
            m = METRICS_BY_ID[h.metric]
            expected = format_value(m, a.values[m.id].raw)
            if expected not in h.text:
                problems.append(f"{a.name}/{h.category}: {expected!r} missing")
            if f"#{ranks[h.category][a.key].rank} of {n}" not in h.text:
                problems.append(f"{a.name}/{h.category}: wrong rank")
            if h.source_id not in bundle.sources:
                problems.append(f"{a.name}/{h.category}: unknown source")
            if h.metric != headline_metric(next(c for c in CATEGORIES if c.id == h.category)).id:
                problems.append(f"{a.name}/{h.category}: not the headline metric")
    rows.append(
        _row(
            "grounded: every highlight quotes its number, rank and source",
            "property",
            not problems,
            "; ".join(problems[:5]),
        )
    )

    # Provenance
    missing = [
        f"{a.key}/{mid}"
        for a in bundle.regions
        for mid, v in a.values.items()
        if v.source_id not in bundle.sources or not v.method.strip()
    ]
    rows.append(
        _row(
            "provenance: every value has a registered source and a method",
            "property",
            not missing,
            ", ".join(missing[:5]),
        )
    )
    outside = [
        mid
        for mid, ref in bundle.references.items()
        if not ref.distribution[0] <= ref.berlin <= ref.distribution[-1]
    ]
    rows.append(
        _row(
            "provenance: Berlin reference within the areas' range",
            "property",
            not outside,
            ", ".join(outside),
        )
    )

    # Wording
    texts = [
        c.label + " " + c.best_label + " " + c.worst_label + " " + c.caveat for c in CATEGORIES
    ]
    for a in bundle.regions:
        s, w = highlights(bundle, a.key)
        texts += [h.text for h in s + w]
    flagged = sorted({word for t in texts for word in BANNED_WORDS if word in t.lower()})
    rows.append(
        _row(
            "wording: no 'avoid' and nothing describing residents",
            "property",
            not flagged,
            ", ".join(flagged),
        )
    )
    return rows


def run() -> tuple[dict, list[dict]]:
    bundle = get_bundle()
    rows = _ground_truth(bundle) + _properties(bundle)
    gated = [r for r in rows if r["kind"] != "known gap"]
    summary = {
        "checks": len(gated),
        "passed": sum(r["passed"] for r in gated),
        "ground_truth": sum(r["kind"] == "ground truth" for r in rows),
        "properties": sum(r["kind"] == "property" for r in rows),
        "known_gaps": [r["name"] for r in rows if r["kind"] == "known gap"],
    }
    return summary, rows


def main() -> None:
    summary, rows = run()
    for r in rows:
        if r["kind"] == "known gap":
            state = "now passes — the gap may be closed" if r["passed"] else r["detail"]
            print(f"⚠️  [known gap] {r['name']}  — {state}")
            continue
        mark = "✅" if r["passed"] else "❌"
        detail = f"  — {r['detail']}" if r["detail"] and not r["passed"] else ""
        print(f"{mark} [{r['kind']}] {r['name']}{detail}")
    print(
        f"\n{summary['passed']} / {summary['checks']} checks pass"
        f" · {len(summary['known_gaps'])} known data gap(s) reported"
    )
    RESULTS_DIR.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n")
    sys.exit(0 if summary["passed"] == summary["checks"] else 1)


if __name__ == "__main__":
    main()
