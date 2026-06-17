"""Hard-constraint filter spec (pure, stdlib only).

This is the single source of truth for *which* criteria are hard filters and their
semantics — budget is a ceiling on WARM rent, rooms/size are minimums. Retrieval
translates this spec into SQL WHERE clauses; keeping it here (not inline in the
query) means the rules are unit-testable without a database.
"""

from __future__ import annotations

# (column, operator, value). Operators are restricted to a known safe set that
# retrieval maps to SQLAlchemy comparisons.
Filter = tuple[str, str, float]


def build_hard_filters(
    max_warm_rent: int | None,
    min_rooms: float | None,
    min_size_m2: int | None,
) -> list[Filter]:
    """Return the hard filters implied by the criteria. Unset criteria add no filter."""
    filters: list[Filter] = []
    if max_warm_rent is not None:
        filters.append(("warmmiete_eur", "<=", max_warm_rent))
    if min_rooms is not None:
        filters.append(("rooms", ">=", min_rooms))
    if min_size_m2 is not None:
        filters.append(("size_m2", ">=", min_size_m2))
    return filters
