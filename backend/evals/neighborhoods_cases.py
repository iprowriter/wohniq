"""Ground-truth cases for the Berlin Neighbourhoods eval.

Each case states something that is well established about Berlin *independently of our
numbers* — police hotspots, the outer forest-and-lake districts, known large-estate
areas, the rent gap between Mitte and Marzahn-Hellersdorf — and checks the ranking
agrees. They guard against a parser/direction/weighting bug that would silently turn a
ranking upside down. (Cases were written before looking at the output; a failing case
means investigate the data, not edit the case.)

Tiers: "best" = Berlin's top 20% (rank ≤ 29 of 143), "worst" = bottom 20% (rank ≥ 115).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TierCase:
    name: str
    category: str
    best: tuple[str, ...] = ()  # every one of these must be in the top 20%
    worst: tuple[str, ...] = ()  # every one of these must be in the bottom 20%
    top_half: tuple[str, ...] = ()
    bottom_half: tuple[str, ...] = ()
    why: str = ""
    # A real-world fact our current data can't reproduce yet. Reported as a known gap
    # (not a pass, not a failure) with the reason — it should start passing once the
    # missing data arrives, and the eval says so when it does.
    known_gap: str | None = None


@dataclass(frozen=True)
class DistrictCase:
    """Mean category score of one district's areas beats another district's."""

    name: str
    category: str
    higher: str
    lower: str
    why: str = ""


@dataclass(frozen=True)
class AllAboveCase:
    """Every area of one district ranks above every area of another."""

    name: str
    category: str
    above: str
    below: str
    why: str = ""


@dataclass(frozen=True)
class Cases:
    tiers: list[TierCase] = field(default_factory=list)
    districts: list[DistrictCase] = field(default_factory=list)
    all_above: list[AllAboveCase] = field(default_factory=list)


CASES = Cases(
    tiers=[
        TierCase(
            "Safety: visitor hubs rank low, outer villages high",
            "safety",
            best=("Müggelheim", "Frohnau/Hermsdorf", "Gatow/Kladow"),
            worst=("Alexanderplatz", "Regierungsviertel", "Tiergarten Süd"),
            why="Police crime atlas: the centre's visitor hotspots have the highest rates; "
            "the outer villages among the lowest.",
        ),
        TierCase(
            "Road safety: busy inner-city streets vs. outer villages",
            "road_safety",
            best=("Müggelheim", "Rahnsdorf"),
            worst=("Südliche Friedrichstadt", "Nördliche Luisenstadt"),
            why="Accident density follows traffic: Kreuzberg/Mitte arterials vs. quiet outskirts.",
        ),
        TierCase(
            "Affluence: villa districts high, large estates low",
            "affluence",
            best=("Grunewald", "Zehlendorf Südwest", "Frohnau/Hermsdorf"),
            worst=("Märkisches Viertel Nord", "Marzahn Nord", "Köllnische Heide"),
            why="Grunewald, Wannsee/Nikolassee and Frohnau are classic high-status areas; "
            "Märkisches Viertel, Marzahn Nord and the Köllnische Heide estates are Senate "
            "focus areas. (Grunewald was a reported known gap until the land values arrived: "
            "the MSS index alone rates its planning areas 'mittel'.)",
        ),
        TierCase(
            "Healthcare: dense centre vs. forest-edge villages",
            "health",
            worst=("Müggelheim", "Schmöckwitz"),
            top_half=("Lietzenburger Straße", "Schöneberg Nordwest"),
            why="Doctors and pharmacies cluster in the dense inner city; Müggelheim and "
            "Schmöckwitz lie between forest and lakes, far from any hospital.",
        ),
        TierCase(
            "Amenities: Prenzlauer Berg and Kreuzkölln vs. outskirts",
            "amenities",
            best=("Helmholtzplatz", "Reuterstraße", "Prenzlauer Berg Südwest"),
            worst=("Müggelheim", "Schmöckwitz"),
            why="Café- and shop-dense Gründerzeit quarters vs. village-like edges.",
        ),
        TierCase(
            "Parks: under-supplied dense west vs. park-side areas",
            "green",
            worst=("Friedenau West", "Lietzenburger Straße"),
            top_half=("Schillerpromenade", "Alt-Treptow"),
            why="The Senate rates Friedenau/Wilmersdorf-City West poorly supplied with public "
            "green; Schillerpromenade borders Tempelhofer Feld, Alt-Treptow the Treptower Park.",
        ),
        TierCase(
            "Public transport: the centre vs. the far south-east and west",
            "transit",
            best=("Alexanderplatz", "Regierungsviertel"),
            worst=("Müggelheim", "Gatow/Kladow"),
            why="Alexanderplatz/Hauptbahnhof are the network's hubs; Müggelheim and Kladow "
            "have no S-/U-Bahn.",
        ),
        TierCase(
            "Quiet & clean air: Alexanderplatz vs. Kladow and Frohnau",
            "environment",
            best=("Gatow/Kladow", "Frohnau/Hermsdorf"),
            worst=("Alexanderplatz",),
            why="Traffic noise and NO₂ peak in the centre; the Havel villages and Frohnau are "
            "quiet and clean. (First draft used Müggelheim — wrong: it lies under the BER "
            "approach paths, and the atlas's noise class includes aircraft noise.)",
        ),
        TierCase(
            "Parking: Prenzlauer Berg is the hardest",
            "parking",
            worst=("Helmholtzplatz", "Prenzlauer Berg Süd"),
            top_half=("Marzahn Süd", "Gatow/Kladow"),
            why="Prenzlauer Berg is dense and fully paid-parking; Marzahn's estates have large "
            "car parks, Kladow is low density.",
        ),
    ],
    districts=[
        DistrictCase(
            "Education: Steglitz-Zehlendorf above Marzahn-Hellersdorf",
            "education",
            "Steglitz-Zehlendorf",
            "Marzahn-Hellersdorf",
            "Abitur share 60.1% vs. 28.5% (Blickpunkt Schule text).",
        ),
        DistrictCase(
            "Education: Charlottenburg-Wilmersdorf above Neukölln",
            "education",
            "Charlottenburg-Wilmersdorf",
            "Neukölln",
            "Abitur 57.2% vs. 33.5%; leavers without qualification 4.2% vs. 12.0%.",
        ),
        DistrictCase(
            "Safety: Treptow-Köpenick above Mitte",
            "safety",
            "Treptow-Köpenick",
            "Mitte",
            "Mitte has Berlin's highest district crime rate.",
        ),
    ],
    all_above=[
        AllAboveCase(
            "Affordability: every Marzahn-Hellersdorf area before every Mitte area",
            "affordability",
            "Marzahn-Hellersdorf",
            "Mitte",
            "IBB 2025: €11.56/m² vs. €20.00/m² median asking rent.",
        ),
    ],
)
