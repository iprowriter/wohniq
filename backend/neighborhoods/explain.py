"""Grounded explanations for Berlin Neighbourhoods (templates, no LLM).

Every sentence quotes the figure it is based on and the Berlin-wide comparison, and
carries the id of the source it comes from — the eval checks that the quoted number is
the stored one (evals/neighborhoods_eval.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from neighborhoods.bundle import NeighbourhoodBundle
from neighborhoods.catalog import CATEGORIES, Category, Metric, metrics_of
from neighborhoods.scoring import category_table, ranks_by_category

MAX_HIGHLIGHTS = 3


def format_value(metric: Metric, raw: float) -> str:
    """A metric value as users read it: '3,198', '2.4', '44.0%', '350 m', '1.2 km', …"""
    f = metric.fmt
    if f == "int":
        return f"{raw:,.0f}"
    if f == "dec1":
        return f"{raw:,.1f}"
    if f == "dec2":
        return f"{raw:.2f}"
    if f == "pct":
        return f"{raw:.1f}%"
    if f == "metres":
        return f"{round(raw, -1):,.0f} m" if raw < 1000 else f"{raw / 1000:.1f} km"
    if f == "minutes":
        return f"{raw:.0f} min"
    if f == "eur_m2":
        return f"€{raw:.2f}/m²"
    if f == "class":
        return f"{raw:.2f}"
    raise ValueError(f"unknown format {f!r}")


def with_unit(metric: Metric, raw: float) -> str:
    """Value plus unit, unless the unit is already in the formatted value."""
    text = format_value(metric, raw)
    if metric.fmt in ("metres", "minutes", "eur_m2", "pct"):
        return text
    return f"{text} {metric.unit}"


def headline_metric(category: Category) -> Metric:
    """The metric that best represents a category (highest weight; first if tied)."""
    scored = [m for m in metrics_of(category.id) if m.weight > 0 and not m.requires]
    return max(scored, key=lambda m: m.weight)


@dataclass(frozen=True)
class Highlight:
    category: str
    label: str  # "Lowest crime"
    rank: int
    text: str
    source_id: str
    metric: str  # the metric quoted


def _sentence(bundle: NeighbourhoodBundle, key: str, category: Category, label: str) -> Highlight:
    area = bundle.area(key)
    assert area is not None
    m = headline_metric(category)
    v = area.values[m.id]
    rank = ranks_by_category(bundle)[category.id][key].rank
    berlin = bundle.references[m.id].berlin
    where = " (district figure)" if m.level == "district" else ""
    text = (
        f"{label} — #{rank} of {len(bundle.regions)}. {m.label}: {with_unit(m, v.raw)}{where}, "
        f"Berlin {format_value(m, berlin)}."
    )
    return Highlight(category.id, label, rank, text, v.source_id, m.id)


def highlights(bundle: NeighbourhoodBundle, key: str) -> tuple[list[Highlight], list[Highlight]]:
    """(strengths, watch-outs): categories where the area is in Berlin's top / bottom 20%."""
    ranks = ranks_by_category(bundle)
    strengths, watch = [], []
    for c in CATEGORIES:
        if c.id not in ranks:
            continue
        r = ranks[c.id][key]
        if r.tier == "best":
            strengths.append((r.rank, c))
        elif r.tier == "worst":
            watch.append((-r.rank, c))
    strengths.sort(key=lambda x: x[0])
    watch.sort(key=lambda x: x[0])
    return (
        [_sentence(bundle, key, c, c.best_label) for _, c in strengths[:MAX_HIGHLIGHTS]],
        [_sentence(bundle, key, c, c.worst_label) for _, c in watch[:MAX_HIGHLIGHTS]],
    )


def summary(bundle: NeighbourhoodBundle, key: str, overall_rank: int) -> str:
    """One line: overall rank plus the strongest and weakest category."""
    ranks = ranks_by_category(bundle)
    table = category_table(bundle)[key]
    ordered = sorted(
        (ranks[c.id][key].rank, c.label)
        for c in CATEGORIES
        if c.id in ranks and table[c.id].score is not None
    )
    n = len(bundle.regions)
    best, worst = ordered[0], ordered[-1]
    return (
        f"#{overall_rank} of {n} overall. Strongest: {best[1]} (#{best[0]}); "
        f"weakest: {worst[1]} (#{worst[0]})."
    )
