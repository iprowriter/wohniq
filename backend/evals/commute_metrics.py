"""Pure scoring for the commute eval (stdlib only, unit-tested).

Compares estimated door-to-door minutes with live BVG/VBB journeys. Errors are
`estimate - live` in minutes: positive means the estimate is too pessimistic.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence


def error_stats(estimates: Sequence[float], actuals: Sequence[float]) -> dict[str, float]:
    """MAE, median absolute error, bias, and share of estimates within 5/10 minutes."""
    if len(estimates) != len(actuals):
        raise ValueError("estimates and actuals must have the same length")
    if not estimates:
        return {"n": 0}
    errors = [e - a for e, a in zip(estimates, actuals, strict=True)]
    abs_errors = [abs(x) for x in errors]
    n = len(errors)
    return {
        "n": n,
        "mae": round(sum(abs_errors) / n, 2),
        "median_abs_error": round(statistics.median(abs_errors), 2),
        "bias": round(sum(errors) / n, 2),
        "within_5_min": round(sum(x <= 5 for x in abs_errors) / n, 3),
        "within_10_min": round(sum(x <= 10 for x in abs_errors) / n, 3),
    }


def changes_accuracy(estimates: Sequence[int], actuals: Sequence[int]) -> dict[str, float]:
    """Share of exact matches and of matches within one change."""
    if len(estimates) != len(actuals):
        raise ValueError("estimates and actuals must have the same length")
    if not estimates:
        return {"n": 0}
    diffs = [abs(e - a) for e, a in zip(estimates, actuals, strict=True)]
    n = len(diffs)
    return {
        "n": n,
        "exact": round(sum(d == 0 for d in diffs) / n, 3),
        "within_1": round(sum(d <= 1 for d in diffs) / n, 3),
    }


def order_agreement(estimates: Sequence[float], actuals: Sequence[float]) -> float | None:
    """Share of pairs (i, j) where the estimate orders i/j the same way as reality.

    This is what ranking cares about: does the faster listing *look* faster? Pairs whose
    live times are equal, or whose estimates tie, are skipped.
    """
    agree = total = 0
    for i in range(len(actuals)):
        for j in range(i + 1, len(actuals)):
            live = actuals[i] - actuals[j]
            est = estimates[i] - estimates[j]
            if live == 0 or est == 0:
                continue
            total += 1
            agree += (live > 0) == (est > 0)
    return round(agree / total, 3) if total else None


def verdict(methods: dict[str, dict]) -> str:
    """Which method has the lower MAE (needs both to have been scored)."""
    scored = {m: s for m, s in methods.items() if s.get("n")}
    if len(scored) < 2:
        return "not enough data to compare"
    best = min(scored, key=lambda m: scored[m]["mae"])
    others = ", ".join(f"{m} {s['mae']}" for m, s in scored.items() if m != best)
    return f"{best} is more accurate (MAE {scored[best]['mae']} min vs {others} min)"
