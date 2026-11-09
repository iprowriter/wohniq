"""Hand-curated metadata for the 143 LOR Bezirksregionen (stdlib only).

Two things the official tables don't give us:

1. LISTING_KIEZ — which regions lie in the Ortsteil one of our 14 listing Kieze
   (data/kieze.py) is named after, so "See flats here" can hand off to listings. Mapping
   is by Ortsteil and deliberately strict: a region in a different Ortsteil (e.g.
   Gesundbrunnen, Friedenau, Weißensee) gets no Kiez even if it's next door, and then
   the UI says "no WohnIQ listings here yet" rather than showing flats from elsewhere.
   Once region boundaries are available this becomes an exact point-in-polygon
   assignment of each listing.

2. DISPLAY_NAMES — readable names where the official one is an internal code
   ("MV Nord", "Ost 1 - Reginhardstraße") or ambiguous.
"""

from __future__ import annotations

LISTING_KIEZ: dict[str, str] = {
    # Mitte (Ortsteil Mitte; Tiergarten Süd is Ortsteil Tiergarten -> no Kiez)
    "011002": "Mitte",  # Regierungsviertel
    "011003": "Mitte",  # Alexanderplatz
    "011004": "Mitte",  # Brunnenstraße Süd
    # Moabit
    "012005": "Moabit",
    "012006": "Moabit",
    # Wedding (Ortsteil Wedding; Osloer Str./Brunnenstr. Nord are Gesundbrunnen)
    "014009": "Wedding",  # Parkviertel
    "014010": "Wedding",  # Wedding Zentrum
    # Kreuzberg
    "021001": "Kreuzberg",  # Südliche Friedrichstadt
    "022002": "Kreuzberg",  # Tempelhofer Vorstadt
    "023003": "Kreuzberg",  # Nördliche Luisenstadt
    "023004": "Kreuzberg",  # Südliche Luisenstadt
    # Friedrichshain
    "024005": "Friedrichshain",  # Karl-Marx-Allee Nord
    "024006": "Friedrichshain",  # Karl-Marx-Allee Süd
    "025007": "Friedrichshain",  # Frankfurter Allee Nord
    "025008": "Friedrichshain",  # Frankfurter Allee Süd FK
    # Prenzlauer Berg
    "036011": "Prenzlauer Berg",
    "036012": "Prenzlauer Berg",
    "036013": "Prenzlauer Berg",  # Helmholtzplatz
    "036014": "Prenzlauer Berg",
    "037015": "Prenzlauer Berg",
    "037016": "Prenzlauer Berg",
    # Pankow (Ortsteil Pankow)
    "034007": "Pankow",  # Pankow Zentrum
    "034008": "Pankow",  # Pankow Süd
    # Charlottenburg (Ortsteil Charlottenburg; Westend/Charlottenburg-Nord are separate)
    "043004": "Charlottenburg",  # Schloss Charlottenburg
    "043005": "Charlottenburg",  # Mierendorffplatz
    "043006": "Charlottenburg",  # Otto-Suhr-Allee/Kantstraße
    # Spandau (Ortsteil Spandau, old town)
    "051003": "Spandau",  # Spandau Mitte
    # Steglitz
    "061001": "Steglitz",  # Schloßstraße
    "061002": "Steglitz",  # Albrechtstraße
    # Schöneberg (Friedenau is a separate Ortsteil)
    "071001": "Schöneberg",
    "071002": "Schöneberg",
    "072003": "Schöneberg",
    "072004": "Schöneberg",
    # Neukölln (Ortsteil Neukölln = the northern part of the district)
    "081001": "Neukölln",  # Schillerpromenade
    "081002": "Neukölln",  # Neuköllner Mitte/Zentrum
    "081003": "Neukölln",  # Reuterstraße
    "081004": "Neukölln",  # Rixdorf
    "081005": "Neukölln",  # Köllnische Heide
    # Treptow (listing Kiez centre is Alt-Treptow)
    "091001": "Treptow",  # Alt-Treptow
    # Lichtenberg (Ortsteil Lichtenberg)
    "113007": "Lichtenberg",  # Alt-Lichtenberg
    "113008": "Lichtenberg",  # Frankfurter Allee Süd
    "114009": "Lichtenberg",  # Neu-Lichtenberg
}

DISPLAY_NAMES: dict[str, str] = {
    "025008": "Frankfurter Allee Süd (Friedrichshain)",
    "113008": "Frankfurter Allee Süd (Lichtenberg)",
    "042002": "Heerstraße (Charlottenburg)",
    "052005": "Heerstraße (Spandau)",
    "121001": "Reginhardstraße",
    "121002": "Alt-Reinickendorf",
    "122003": "Auguste-Viktoria-Allee",
    "122004": "Tegel-Süd/Flughafensee",
    "122005": "Tegel",
    "124006": "Heiligensee/Konradshöhe",
    "124007": "Frohnau/Hermsdorf",
    "125008": "Borsigwalde/Freie Scholle",
    "125009": "Waidmannslust/Wittenau/Lübars",
    "126011": "Märkisches Viertel Nord",
    "126012": "Märkisches Viertel Süd",
}


def display_name(key: str, official: str) -> str:
    """Readable name: curated override, else the official name with whitespace normalised."""
    return DISPLAY_NAMES.get(key) or " ".join(official.split())
