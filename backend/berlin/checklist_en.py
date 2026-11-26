"""English labels for the Mietspiegel 2026 checklist (Orientierungshilfe), and when items apply.

The German text parsed from the brochure stays the source of truth (shown as the original);
these are our plain-English renderings for the UI, keyed by the parsed item ids. A test checks
every parsed id has a label and no label is orphaned.

`NOT_APPLICABLE`: items the brochure itself excludes for some building ages
(e.g. "gilt nicht für die Baualtersklassen ab 2010"). They're shown greyed out and ignored.
"""

from __future__ import annotations

GROUP_LABELS = {
    1: "Bathroom and WC",
    2: "Kitchen",
    3: "Flat",
    4: "Building",
    5: "Surroundings",
}

LABELS: dict[str, str] = {
    # 1 Bathroom and WC — lowers the value
    "bath-minus-01": "No washbasin in bathroom or WC, or only a small one (50 cm or less)",
    "bath-minus-02": "WC with no way to air or ventilate it",
    "bath-minus-03": "Wooden floorboards in the bathroom (not suitable for wet rooms)",
    "bath-minus-04": "Bathroom not heated, or only wood/coal or an electric heater",
    "bath-minus-05": "No adequate hot water (no central supply, no instantaneous heater, "
    "no boiler over 60 litres)",
    "bath-minus-06": "Free-standing bathtub with no separate shower, in an unmodernised bathroom",
    "bath-minus-07": "Walls around washbasin, bath or shower not tiled or protected",
    "bath-minus-08": "Bathroom with WC has no window",
    "bath-minus-09": "No way to shower (no splash protection, no shower-head holder)",
    "bath-minus-10": "Small bathroom (under 4 m²)",
    # 1 Bathroom and WC — raises the value
    "bath-plus-01": "Very large washbasin (80 cm or wider), double basin or two basins",
    "bath-plus-02": "High-quality fittings (e.g. quality sanitaryware and furniture, corner or "
    "round bath, glass screen, rain shower)",
    "bath-plus-03": "Interior bathroom with modern controlled ventilation (e.g. humidity sensor)",
    "bath-plus-04": "Second WC in the flat, or bathroom and WC separate",
    "bath-plus-05": "At least one bathroom larger than 8 m²",
    "bath-plus-06": "Underfloor heating in the bathroom",
    "bath-plus-07": "High-quality wall and floor coverings",
    "bath-plus-08": "Wall-hung WC with concealed cistern, or a high-quality floor-standing WC",
    "bath-plus-09": "Towel-rail radiator (buildings up to 2001; any age if it also runs "
    "electrically)",
    "bath-plus-10": "Separate shower tray or cubicle in addition to the bathtub",
    "bath-plus-11": "Walk-in shower (or a shower tray no deeper than 3 cm)",
    # 2 Kitchen
    "kitchen-minus-01": "Kitchen with no window and no adequate ventilation",
    "kitchen-minus-02": "No cooker, or a gas/electric hob without oven",
    "kitchen-minus-03": "No sink",
    "kitchen-minus-04": "No adequate hot water (no central supply, no instantaneous heater, "
    "no boiler)",
    "kitchen-minus-05": "Kitchen not heated, or only wood/coal heating",
    "kitchen-minus-06": "No space or connection for a dishwasher",
    "kitchen-minus-07": "No wall tiles or similar protection at the worktop",
    "kitchen-plus-01": "High-quality floor (tiles, linoleum, wet-room laminate, parquet, "
    "terrazzo) in good condition",
    "kitchen-plus-02": "Separate kitchen of at least 14 m²",
    "kitchen-plus-03": "Fitted kitchen with wall and base units, cooker and sink",
    "kitchen-plus-04": "Ceramic or induction hob",
    "kitchen-plus-05": "Extractor hood",
    "kitchen-plus-06": "Fridge, freezer or dishwasher provided",
    "kitchen-plus-07": "Free-standing kitchen island with worktop and hob or sink",
    # 3 Flat
    "flat-minus-01": "Mostly single-glazed windows (box-type double windows don't count)",
    "flat-minus-02": "Inadequate wiring (e.g. no residual-current breaker or equipotential "
    "bonding)",
    "flat-minus-03": "Electric cables mostly run on the wall surface",
    "flat-minus-04": "Water and waste pipes mostly run on the wall surface",
    "flat-minus-05": "No space or connection for a washing machine in bathroom or kitchen",
    "flat-minus-06": "Poor layout (e.g. a room only reachable through another)",
    "flat-minus-07": "No balcony, terrace, loggia or winter garden (unless not possible or "
    "not allowed)",
    "flat-minus-08": "Ground-floor flat without burglary or privacy protection on all windows",
    "flat-plus-01": "Storage room in the flat (at least 1 m²) or built-in wardrobe",
    "flat-plus-02": "Large balcony, (roof) terrace, loggia or winter garden (4 m² or more)",
    "flat-plus-03": "Mostly underfloor heating",
    "flat-plus-04": "Elaborate ceiling or wall decoration (e.g. stucco, panelling) in good "
    "condition in most rooms",
    "flat-plus-05": "Heating pipes mostly hidden in the walls",
    "flat-plus-06": "External shutters or blinds on most living-room windows",
    "flat-plus-07": "One room larger than 40 m²",
    "flat-plus-08": "Low-barrier layout (no thresholds, step-free to balcony, enough room to "
    "move)",
    "flat-plus-09": "High-quality parquet, stone, tiles or similar in most rooms",
    "flat-plus-10": "Mostly thermal or soundproof glazing fitted in 2002 or later "
    "(buildings from before 2002)",
    "flat-plus-11": "Extra burglary protection on a reinforced front door (e.g. multi-point "
    "lock)",
    # 4 Building
    "building-minus-01": "Stairwell and entrance mostly in poor condition",
    "building-minus-02": "No storage outside the flat for your sole use at no extra cost "
    "(e.g. no lockable cellar)",
    "building-minus-03": "Front door and stairwell freely accessible from outside at all times",
    "building-minus-04": "Poor state of repair (e.g. permanently damp walls, large plaster or "
    "roof damage)",
    "building-minus-05": "In a side wing or rear building in a densely built block",
    "building-minus-06": "Fifth floor or higher with no lift",
    "building-minus-07": "No intercom with electric door opener",
    "building-minus-08": "Inadequate insulation or an inefficient heating system "
    "(installed before 1995)",
    "building-minus-energy-145": "Energy use above 145 kWh/(m²·a)",
    "building-minus-energy-195": "Energy use above 195 kWh/(m²·a)",
    "building-minus-energy-235": "Energy use above 235 kWh/(m²·a)",
    "building-plus-01": "Lockable, easy-to-reach bike room, or enough lockable bike stands on "
    "the property",
    "building-plus-02": "Extra shared rooms within walking distance (e.g. common room, guest "
    "flat, drying room)",
    "building-plus-03": "Impressive or high-quality renovated entrance and stairwell",
    "building-plus-04": "Building in above-average repair (e.g. renewed facade or roof)",
    "building-plus-05": "Video intercom with electric door opener",
    "building-plus-06": "Lift in a building with fewer than five upper floors",
    "building-plus-07": "Low-barrier access to the building and the flat (at most one step "
    "each)",
    "building-plus-08": "Extra insulation, or a modern heating system installed in 2009 or "
    "later (buildings from before 2009)",
    "building-plus-energy-120": "Energy use below 120 kWh/(m²·a)",
    "building-plus-energy-100": "Energy use below 100 kWh/(m²·a)",
    "building-plus-energy-80": "Energy use below 80 kWh/(m²·a)",
    # 5 Surroundings
    "surroundings-minus-01": "Particularly noisy location (e.g. main road, airport, industry, "
    "bars or clubs)",
    "surroundings-minus-02": "Particularly smelly location",
    "surroundings-minus-03": "No bike parking on the property",
    "surroundings-plus-01": "Particularly quiet location (e.g. traffic-calmed street, next to "
    "a park)",
    "surroundings-plus-02": "Well-designed grounds (e.g. playground, benches, paths with green "
    "and lighting)",
    "surroundings-plus-03": "Parking provided by the landlord nearby",
    "surroundings-plus-04": "Garden for your sole use at no charge, or with direct access "
    "from the flat",
}

# Period keys (data/berlin/mietspiegel.py PERIODS) in table order.
_ORDER = (
    "pre1918",
    "1919-1949",
    "1950-1964",
    "1965-1972",
    "1973-1985-west",
    "1986-1990-west",
    "1973-1990-east",
    "1991-2001",
    "2002-2009",
    "2010-2015",
    "2016-2019",
    "2020-2024",
)
_FROM = {
    "2002": {"2002-2009", "2010-2015", "2016-2019", "2020-2024"},
    "2010": {"2010-2015", "2016-2019", "2020-2024"},
}
_UP_TO = {
    "1949": {"pre1918", "1919-1949"},
    "1990": set(_ORDER[:7]),
    "2001": set(_ORDER[:8]),
    "2009": set(_ORDER[:9]),
    "2015": set(_ORDER[:10]),
}
_ALL = set(_ORDER)

# item id → building-age periods in which the brochure says the item doesn't count.
NOT_APPLICABLE: dict[str, set[str]] = {
    "bath-minus-08": {"1973-1990-east"},
    "bath-minus-10": {"1973-1990-east"},
    "bath-plus-07": _FROM["2010"],
    "kitchen-plus-01": _ALL - _UP_TO["2009"],
    "kitchen-plus-04": _ALL - _UP_TO["2001"],
    "flat-plus-05": _ALL - _UP_TO["1990"],
    "flat-plus-10": _FROM["2002"],
    "building-minus-06": _UP_TO["1949"],
    "building-plus-04": _ALL - _UP_TO["2015"],
    "building-plus-06": _FROM["2010"],
}

# Either the insulation/heating item or the energy items count, never both (No. 10.4 A).
INSULATION_ITEMS = ("building-minus-08", "building-plus-08")


def applies(item_id: str, period: str) -> bool:
    return period not in NOT_APPLICABLE.get(item_id, set())
