"""Pure selection logic for explanations (stdlib only, unit-testable).

Decides which ranking factors become positive "reasons" and which become honest
"caveats", purely from their scores — no LLM, no pydantic. The explanation layer
uses this for its deterministic fallback, and the same thresholds describe what the
LLM is asked to do. Operates on plain factor tuples: (name, score, weight, detail).

`relevance` is an internal retrieval signal, not a user-meaningful reason, so it's
excluded from explanations.
"""

from __future__ import annotations

REASON_THRESHOLD = 0.6
CAVEAT_THRESHOLD = 0.4
MAX_REASONS = 3
MAX_CAVEATS = 2

Factor = tuple[str, float, float, str]  # (name, score, weight, detail)


def _user_factors(factors: list[Factor]) -> list[Factor]:
    return [f for f in factors if f[0] != "relevance"]


def select_reasons_and_caveats(factors: list[Factor]) -> tuple[list[str], list[str]]:
    """Return (reasons, caveats) details. Reasons = strong factors (by score×weight);
    caveats = weak factors (honest trade-offs)."""
    user = _user_factors(factors)

    reasons = [
        detail
        for (_name, score, _weight, detail) in sorted(user, key=lambda f: -f[1] * f[2])
        if score >= REASON_THRESHOLD
    ][:MAX_REASONS]

    caveats = [detail for (_n, score, _w, detail) in user if score <= CAVEAT_THRESHOLD][:MAX_CAVEATS]

    # Always surface at least one reason if any user factor exists.
    if not reasons and user:
        best = max(user, key=lambda f: f[1])
        reasons = [best[3]]

    return reasons, caveats


def summary_lead(total: float) -> str:
    if total >= 0.75:
        return "A strong match"
    if total >= 0.5:
        return "A solid fit"
    return "A partial match"
