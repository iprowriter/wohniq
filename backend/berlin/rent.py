"""Rent check: Berliner Mietspiegel 2026 + the rent brake (ADR-0017). Pure functions.

Steps, as the brochure describes them (No. 8–10):
  1. Pick the table row: location class (from the address), building-age period (East/West
     matters for 1973–1990), living space.
  2. Optional checklist (Orientierungshilfe): in each of the 5 groups the side with more ticks
     wins; the groups are netted against each other, and each net group moves the comparable
     rent 20 % of the way from the mean to the top (or bottom) of the range.
  3. Rent-brake limit = comparable rent + 10 % (§ 556d BGB). Without a checklist, the
     comparable rent is the index mean — that's what listings use, labelled an estimate.
  4. Exemptions that can be read from the data: new builds (first occupied after
     1 Oct 2014; we can only see the year, so 2014 or later). Others (comprehensive
     modernisation, the previous tenant's rent, modernisation surcharges) are always listed
     next to the verdict.

This module never ranks or scores listings; it only states where a rent sits (golden rule 1).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from berlin.checklist_en import INSULATION_ITEMS, applies

RENT_BRAKE_FACTOR = 1.10
GROUP_STEP = 0.20  # each net feature group moves 20 % of the way to the range edge
NEW_BUILD_FROM_YEAR = 2014  # first occupied after 1 Oct 2014 → rent brake doesn't apply
NO_HEATING_OR_BATH_DEDUCTION = 0.33  # €/m², flats ready by 1949 without heating and/or bath
# Energy: demand certificates (Bedarf) use limits 20 % higher; values without hot water get
# +20 kWh before comparing (Orientierungshilfe, group 4 notes).
DEMAND_FACTOR = 1.20
NO_HOT_WATER_SURCHARGE_KWH = 20

EXEMPTIONS_TEXT = (
    "New buildings first let after 1 October 2014 aren't covered by the rent brake. Nor is "
    "the first letting after a comprehensive modernisation. A landlord may keep a previous "
    "tenant's rent if it was already higher. Modernisation in the last three years can "
    "justify a surcharge. Furnished flats may add a furniture surcharge, which the "
    "Mietspiegel doesn't cover."
)
DISCLAIMER_TEXT = (
    "Estimate from the official rent index, not legal advice. For a binding check, contact a "
    "tenants' association or the Mietpreisprüfstelle."
)


@dataclass(frozen=True)
class RentInput:
    location_class: str  # simple | medium | good
    east: bool
    year_built: int
    size_m2: float
    cold_rent_eur: float | None = None  # net cold rent per month; None = just the index
    features: frozenset[str] = frozenset()  # ticked checklist ids
    energy_kwh: float | None = None  # (end-)energy value from the certificate
    energy_is_demand: bool = False  # demand (Bedarf) instead of consumption (Verbrauch)
    energy_without_hot_water: bool = False
    no_central_heating_or_bath: bool = False  # only counts for flats ready by 1949


@dataclass
class GroupResult:
    group: int
    plus: int
    minus: int
    effect: int  # +1, 0, -1


@dataclass
class RentResult:
    covered: bool  # False: the Mietspiegel has no row (built after 2024)
    period: str | None
    row: dict | None
    low: float | None = None  # €/m² (after the 1949 deduction, if any)
    mean: float | None = None
    high: float | None = None
    groups: list[GroupResult] = field(default_factory=list)
    net_groups: int = 0
    used_checklist: bool = False
    comparable: float | None = None  # ortsübliche Vergleichsmiete, €/m²
    limit: float | None = None  # rent-brake limit, €/m²; None when exempt
    exempt: str | None = None  # "new_build"
    asked: float | None = None  # €/m² net cold
    verdict: str = "unknown"  # within_limit | above_limit | below_index | new_build | not_covered
    over_per_m2: float | None = None
    over_per_month: float | None = None
    ignored_features: list[str] = field(default_factory=list)  # don't apply to this age

    def to_dict(self) -> dict:
        return asdict(self)


def period_for(year: int, east: bool, periods: dict[str, dict]) -> str | None:
    side = "east" if east else "west"
    for key, p in periods.items():
        lo = p["from"] if p["from"] is not None else -math.inf
        if lo <= year <= p["to"] and p["side"] in (None, side):
            return key
    return None


def find_row(rows: list[dict], location_class: str, period: str, size_m2: float) -> dict | None:
    for r in rows:
        if r["location"] != location_class or r["period"] != period:
            continue
        if r["size_min"] <= size_m2 and (r["size_max"] is None or size_m2 < r["size_max"]):
            return r
    return None


def energy_features(
    kwh: float, *, is_demand: bool = False, without_hot_water: bool = False
) -> set[str]:
    """Checklist ids the energy value ticks (one, two or three boxes on either side)."""
    value = kwh + (NO_HOT_WATER_SURCHARGE_KWH if without_hot_water else 0)
    scale = DEMAND_FACTOR if is_demand else 1.0
    out = set()
    for limit in (145, 195, 235):
        if value > limit * scale:
            out.add(f"building-minus-energy-{limit}")
    for limit in (120, 100, 80):
        if value < limit * scale:
            out.add(f"building-plus-energy-{limit}")
    return out


def _r2(x: float) -> float:
    return round(x + 1e-9, 2)


def check_rent(
    inp: RentInput, rows: list[dict], periods: dict[str, dict], checklist: list[dict]
) -> RentResult:
    period = period_for(inp.year_built, inp.east, periods)
    if period is None:
        return RentResult(
            covered=False,
            period=None,
            row=None,
            verdict="not_covered",
            asked=_asked(inp),
            exempt="new_build",
        )
    row = find_row(rows, inp.location_class, period, inp.size_m2)
    if row is None:  # can't happen for a valid class: every period's bands are open-ended
        return RentResult(
            covered=False, period=period, row=None, verdict="not_covered", asked=_asked(inp)
        )

    deduction = (
        NO_HEATING_OR_BATH_DEDUCTION
        if inp.no_central_heating_or_bath and period in ("pre1918", "1919-1949")
        else 0.0
    )
    low, mean, high = row["low"] - deduction, row["mean"] - deduction, row["high"] - deduction

    # Checklist: drop items that don't apply to this building age, and the insulation items
    # when an energy value is given (either one or the other counts).
    features = set(inp.features)
    if inp.energy_kwh is not None:
        features -= {i for i in features if "-energy-" in i or i in INSULATION_ITEMS}
        features |= energy_features(
            inp.energy_kwh,
            is_demand=inp.energy_is_demand,
            without_hot_water=inp.energy_without_hot_water,
        )
    ignored = sorted(i for i in features if not applies(i, period))
    features -= set(ignored)
    known = {it["id"]: it for it in checklist}
    groups = []
    for g in range(1, 6):
        plus = sum(
            1 for i in features if i in known and known[i]["group"] == g and known[i]["sign"] == "+"
        )
        minus = sum(
            1 for i in features if i in known and known[i]["group"] == g and known[i]["sign"] == "-"
        )
        groups.append(GroupResult(g, plus, minus, (plus > minus) - (plus < minus)))
    net = sum(gr.effect for gr in groups)
    if net > 0:
        comparable = mean + GROUP_STEP * net * (high - mean)
    elif net < 0:
        comparable = mean + GROUP_STEP * net * (mean - low)
    else:
        comparable = mean

    exempt = "new_build" if inp.year_built >= NEW_BUILD_FROM_YEAR else None
    limit = None if exempt else comparable * RENT_BRAKE_FACTOR
    asked = _asked(inp)
    result = RentResult(
        covered=True,
        period=period,
        row=row,
        low=_r2(low),
        mean=_r2(mean),
        high=_r2(high),
        groups=groups,
        net_groups=net,
        used_checklist=bool(features),
        comparable=_r2(comparable),
        limit=_r2(limit) if limit is not None else None,
        exempt=exempt,
        asked=asked,
        ignored_features=ignored,
    )
    if asked is None:
        result.verdict = "new_build" if exempt else "unknown"
    elif exempt:
        result.verdict = "new_build"
    elif asked < result.low:
        result.verdict = "below_index"
    elif asked <= result.limit:
        result.verdict = "within_limit"
    else:
        result.verdict = "above_limit"
        result.over_per_m2 = _r2(asked - result.limit)
        result.over_per_month = round((asked - result.limit) * inp.size_m2)
    return result


def _asked(inp: RentInput) -> float | None:
    if inp.cold_rent_eur is None or inp.size_m2 <= 0:
        return None
    return _r2(inp.cold_rent_eur / inp.size_m2)


def rent_by_period(
    rows: list[dict], location_class: str, east: bool, size_m2: float, periods: dict[str, dict]
) -> list[dict]:
    """Index mean for every building age at this location and size (the bar chart)."""
    side = "east" if east else "west"
    out = []
    for key, p in periods.items():
        if p["side"] not in (None, side):
            continue
        r = find_row(rows, location_class, key, size_m2)
        if r is not None:
            out.append({"period": key, "label": p["label"], "mean": r["mean"], "row": r["row"]})
    return out


VERDICT_TEXT = {
    "within_limit": "Within the rent-brake limit",
    "above_limit": "Above the rent-brake limit",
    "below_index": "Below the rent index",
    "new_build": "New build: the rent brake doesn't apply",
    "not_covered": "Not covered by the Mietspiegel",
    "unknown": "Rent index",
}


def explain(
    result: RentResult, *, size_m2: float, year_built: int, location_class: str, estimate: bool
) -> str:
    """One plain paragraph built only from the result's numbers (golden rule 3)."""
    if not result.covered:
        return (
            f"Built in {year_built}: the Mietspiegel 2026 only covers flats ready for "
            "occupancy up to 2024, and new buildings aren't covered by the rent brake."
        )
    parts = [
        f"Location class {location_class}, {size_m2:g} m², built {year_built}. The Mietspiegel "
        f"2026 range for this flat is €{result.low:.2f}–{result.high:.2f}/m², mean "
        f"€{result.mean:.2f}."
    ]
    if result.exempt:
        parts.append(
            "Buildings first let after 1 October 2014 aren't covered by the rent "
            "brake, so there is no legal maximum."
        )
    else:
        basis = "index mean" if not result.used_checklist else "comparable rent"
        parts.append(
            f"With the rent brake ({basis} + 10 %) the cold rent may be at most "
            f"{'about ' if estimate else ''}€{result.limit:.2f}/m²."
        )
    if result.asked is not None:
        if result.verdict == "above_limit":
            parts.append(
                f"This flat asks €{result.asked:.2f}. That is about "
                f"€{result.over_per_month:,} a month over the limit: worth asking why."
            )
        elif result.verdict == "within_limit":
            parts.append(f"This flat asks €{result.asked:.2f}, within the limit.")
        elif result.verdict == "below_index":
            parts.append(
                f"This flat asks €{result.asked:.2f}, below the lowest index value "
                "for a flat like this."
            )
        elif result.verdict == "new_build":
            parts.append(f"This flat asks €{result.asked:.2f}.")
    return " ".join(parts)
