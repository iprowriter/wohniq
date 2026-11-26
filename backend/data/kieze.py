"""Berlin neighborhood (Kiez) reference data.

Static, stdlib-only data used by the synthetic generator to produce realistic
listings: each Kiez has an approximate center, a base asking *cold* rent per m²,
and a nightlife profile (which drives the "quiet" signal). Figures are plausible
2025/26 asking-rent levels, not official statistics — this is synthetic data.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Kiez:
    name: str
    district: str  # Bezirk
    lat: float
    lng: float
    cold_eur_per_m2: float  # base asking cold rent per m²
    nightlife: str  # "low" | "medium" | "high"


# ~14 well-known Kieze spanning the price and vibe range.
KIEZE: list[Kiez] = [
    Kiez("Prenzlauer Berg", "Pankow", 52.540, 13.420, 18.5, "low"),
    Kiez("Mitte", "Mitte", 52.525, 13.402, 19.5, "high"),
    Kiez("Friedrichshain", "Friedrichshain-Kreuzberg", 52.515, 13.454, 17.0, "high"),
    Kiez("Kreuzberg", "Friedrichshain-Kreuzberg", 52.499, 13.403, 18.0, "high"),
    Kiez("Neukölln", "Neukölln", 52.481, 13.435, 15.5, "high"),
    Kiez("Charlottenburg", "Charlottenburg-Wilmersdorf", 52.505, 13.305, 16.5, "medium"),
    Kiez("Schöneberg", "Tempelhof-Schöneberg", 52.483, 13.355, 16.0, "medium"),
    Kiez("Moabit", "Mitte", 52.530, 13.342, 15.0, "medium"),
    Kiez("Wedding", "Mitte", 52.550, 13.365, 13.5, "medium"),
    Kiez("Lichtenberg", "Lichtenberg", 52.515, 13.500, 12.5, "low"),
    Kiez("Pankow", "Pankow", 52.567, 13.402, 14.0, "low"),
    Kiez("Steglitz", "Steglitz-Zehlendorf", 52.456, 13.332, 14.0, "low"),
    Kiez("Treptow", "Treptow-Köpenick", 52.493, 13.460, 14.5, "low"),
    Kiez("Spandau", "Spandau", 52.535, 13.200, 11.5, "low"),
]

# Outer districts the first catalogue missed (Marzahn-Hellersdorf, Reinickendorf), used only
# by the district batch in data.synthetic. A separate list on purpose: the generator draws
# from KIEZE with its rng, so extending KIEZE would reshuffle every existing listing, and
# the Lifestyle bundle maps its regions onto exactly these 14.
OUTER_KIEZE: list[Kiez] = [
    Kiez("Marzahn", "Marzahn-Hellersdorf", 52.545, 13.545, 10.5, "low"),
    Kiez("Hellersdorf", "Marzahn-Hellersdorf", 52.535, 13.605, 10.0, "low"),
    Kiez("Reinickendorf", "Reinickendorf", 52.575, 13.335, 12.0, "low"),
    Kiez("Tegel", "Reinickendorf", 52.585, 13.285, 12.5, "low"),
]

# Every Kiez a listing can be in.
ALL_KIEZE: list[Kiez] = KIEZE + OUTER_KIEZE

# Berlin bounding box — used by tests to assert generated coords are sane.
BERLIN_BBOX = {"lat_min": 52.30, "lat_max": 52.70, "lng_min": 13.05, "lng_max": 13.80}
