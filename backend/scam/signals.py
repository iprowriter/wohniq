"""Deterministic scam signals (T3.1) — pure, no API (ADR-0002, SPEC F7 AC1).

These are the cheap, crisp signals: a price far below the official rent index (or, where a
flat has no index row, below the Kiez median), and metadata red flags like
"no Anmeldung". Each returns a Signal carrying its severity and
verbatim-ish evidence, or None if it doesn't fire. The fuzzy text signals (LLM) and
photo-duplicate signal (pHash) live elsewhere; risk fusion (T3.4) combines all three
sources.

The `Signal` shape here is the shared contract for every source.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

PRICE_PCT_THRESHOLD = 0.30  # >= 30% below median trips the price signal
PRICE_SEVERITY_FULL = 0.50  # 50%+ below median → full severity
# Against the Mietspiegel (ADR-0017): the lowest index value for this flat is already a
# cheap but real rent, so a smaller margin below it is suspicious.
INDEX_PCT_THRESHOLD = 0.15  # >= 15% below the index's lower end trips the signal
INDEX_SEVERITY_FULL = 0.45  # 45%+ below → full severity
ANMELDUNG_SEVERITY = 0.6


@dataclass
class Signal:
    name: str
    severity: float  # 0..1 — strength of this signal's contribution
    source: str  # "rule" | "image" | "llm"
    evidence: str


def _clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, x))


def kiez_price_stats(values_eur_per_m2: list[float]) -> tuple[float, float]:
    """Robust center/spread for a Kiez's €/m²: (median, median absolute deviation)."""
    if not values_eur_per_m2:
        return 0.0, 0.0
    median = statistics.median(values_eur_per_m2)
    mad = statistics.median([abs(v - median) for v in values_eur_per_m2])
    return median, mad


def price_below_market(
    kiez: str,
    eur_per_m2: float,
    median_eur_per_m2: float,
    mad_eur_per_m2: float,
) -> Signal | None:
    """Fire when €/m² is far below the Kiez median (classic price-bait scam)."""
    if median_eur_per_m2 <= 0:
        return None
    pct_below = (median_eur_per_m2 - eur_per_m2) / median_eur_per_m2
    if pct_below < PRICE_PCT_THRESHOLD:
        return None

    severity = _clamp(pct_below / PRICE_SEVERITY_FULL)
    # Robust z-score for the evidence (how many MADs below the median).
    z = (eur_per_m2 - median_eur_per_m2) / (1.4826 * mad_eur_per_m2) if mad_eur_per_m2 else float("-inf")
    z_text = f", z={z:.1f}" if mad_eur_per_m2 else ""
    evidence = (
        f"{pct_below * 100:.0f}% below the {kiez} median "
        f"(€{eur_per_m2:.0f}/m² vs €{median_eur_per_m2:.0f}/m²{z_text})"
    )
    return Signal(name="price_below_market", severity=severity, source="rule", evidence=evidence)


def price_below_index(eur_per_m2: float, index_low: float, index_row: int) -> Signal | None:
    """Fire when €/m² cold is far below the lowest Mietspiegel value for this flat."""
    if index_low <= 0:
        return None
    pct_below = (index_low - eur_per_m2) / index_low
    if pct_below < INDEX_PCT_THRESHOLD:
        return None
    severity = _clamp(pct_below / INDEX_SEVERITY_FULL)
    evidence = (
        f"€{eur_per_m2:.2f}/m² cold is {pct_below * 100:.0f}% below the lowest rent-index "
        f"value for this flat (€{index_low:.2f}/m², Mietspiegel 2026, row {index_row})"
    )
    return Signal(name="price_below_index", severity=severity, source="rule", evidence=evidence)


def no_anmeldung(anmeldung_possible: bool) -> Signal | None:
    """Fire when registration isn't possible — a strong German-rental red flag."""
    if anmeldung_possible:
        return None
    return Signal(
        name="no_anmeldung",
        severity=ANMELDUNG_SEVERITY,
        source="rule",
        evidence="Anmeldung (legal residence registration) not possible at this address",
    )


def rule_signals(
    *,
    kiez: str,
    eur_per_m2: float,
    anmeldung_possible: bool,
    median_eur_per_m2: float,
    mad_eur_per_m2: float,
    index_low: float | None = None,
    index_row: int | None = None,
) -> list[Signal]:
    """All deterministic signals that fire for one listing.

    With a rent-index row the price is judged against the Mietspiegel; without one (no
    Berlin data, or a flat the table doesn't cover) against the Kiez median, as before.
    """
    price = (
        price_below_index(eur_per_m2, index_low, index_row)
        if index_low is not None and index_row is not None
        else price_below_market(kiez, eur_per_m2, median_eur_per_m2, mad_eur_per_m2)
    )
    candidates = [price, no_anmeldung(anmeldung_possible)]
    return [s for s in candidates if s is not None]
